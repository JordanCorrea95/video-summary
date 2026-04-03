from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.config import (
    MAX_EVENT_GAP_SECONDS,
    MIN_EVENT_DURATION_SECONDS,
    TRACKER_CONFIG,
    YOLO_MODEL,
)
from app.infrastructure.ai.ollama_client import describe_event_from_image, summarize_events
from app.infrastructure.storage.file_store import write_json

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None  # type: ignore


@dataclass
class TrackState:
    track_id: int
    class_id: int
    class_name: str
    start_ts: float
    end_ts: float
    max_conf: float
    frames: int


def _video_info(video_path: Path) -> tuple[float, int]:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    return float(fps), total_frames


def stage_a_candidate_windows(video_path: Path) -> list[dict[str, float | bool]]:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    stride = max(1, int(round(fps)))

    last_gray = None
    windows: list[dict[str, float | bool]] = []
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % stride != 0:
            frame_idx += 1
            continue

        ts = frame_idx / fps
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        is_active = True
        if last_gray is not None:
            delta = cv2.absdiff(gray, last_gray)
            motion_score = float(np.mean(delta))
            is_active = motion_score >= 6.0
        windows.append(
            {
                "start_ts": max(0.0, ts - 0.5),
                "end_ts": ts + 0.5,
                "active": is_active,
                "sample_fps": 10.0 if is_active else 2.0,
            }
        )
        last_gray = gray
        frame_idx += 1

    cap.release()
    return _merge_windows(windows, gap_seconds=1.5)


def _merge_windows(windows: list[dict[str, float | bool]], gap_seconds: float) -> list[dict[str, float | bool]]:
    if not windows:
        return []
    sorted_windows = sorted(windows, key=lambda w: float(w["start_ts"]))
    merged: list[dict[str, float | bool]] = []
    current = dict(sorted_windows[0])

    for w in sorted_windows[1:]:
        if float(w["start_ts"]) <= float(current["end_ts"]) + gap_seconds:
            current["end_ts"] = max(float(current["end_ts"]), float(w["end_ts"]))
            current["active"] = bool(current["active"]) or bool(w["active"])
            current["sample_fps"] = max(float(current["sample_fps"]), float(w["sample_fps"]))
            continue
        merged.append(current)
        current = dict(w)
    merged.append(current)
    return merged


def _pick_device() -> str:
    if torch is not None and torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def stage_b_tracking(video_path: Path, windows: list[dict[str, float | bool]]) -> tuple[list[dict[str, Any]], str]:
    if YOLO is None:
        return [], "cpu"

    device = _pick_device()
    try:
        model = YOLO(YOLO_MODEL)
    except Exception:
        return [], device

    fps, _ = _video_info(video_path)
    cap = cv2.VideoCapture(str(video_path))
    tracks: dict[int, TrackState] = {}
    frame_idx = 0
    names = model.names if hasattr(model, "names") else {}

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        ts = frame_idx / fps
        window = _window_for_timestamp(windows, ts)
        if not window:
            frame_idx += 1
            continue
        target_sample_fps = float(window["sample_fps"])
        stride = max(1, int(round(fps / target_sample_fps)))
        if frame_idx % stride != 0:
            frame_idx += 1
            continue

        try:
            results = model.track(
                frame,
                tracker=TRACKER_CONFIG,
                persist=True,
                conf=0.35,
                iou=0.5,
                device=device,
                verbose=False,
            )
        except Exception:
            frame_idx += 1
            continue

        if not results:
            frame_idx += 1
            continue
        boxes = results[0].boxes
        if boxes is None or boxes.id is None:
            frame_idx += 1
            continue

        ids = boxes.id.cpu().numpy().astype(int).tolist()
        classes = boxes.cls.cpu().numpy().astype(int).tolist()
        confs = boxes.conf.cpu().numpy().astype(float).tolist()

        for track_id, class_id, conf in zip(ids, classes, confs):
            if track_id not in tracks:
                class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
                tracks[track_id] = TrackState(
                    track_id=track_id,
                    class_id=class_id,
                    class_name=class_name,
                    start_ts=ts,
                    end_ts=ts,
                    max_conf=conf,
                    frames=1,
                )
            else:
                state = tracks[track_id]
                state.end_ts = ts
                state.max_conf = max(state.max_conf, conf)
                state.frames += 1

        frame_idx += 1

    cap.release()

    serialized = [
        {
            "track_id": t.track_id,
            "class_id": t.class_id,
            "class_name": t.class_name,
            "start_ts": round(t.start_ts, 3),
            "end_ts": round(t.end_ts, 3),
            "max_conf": round(t.max_conf, 4),
            "frames": t.frames,
            "duration_s": round(t.end_ts - t.start_ts, 3),
        }
        for t in tracks.values()
        if (t.end_ts - t.start_ts) >= MIN_EVENT_DURATION_SECONDS
    ]
    serialized.sort(key=lambda x: x["start_ts"])
    return serialized, device


def _window_for_timestamp(windows: list[dict[str, float | bool]], ts: float) -> dict[str, float | bool] | None:
    for w in windows:
        if float(w["start_ts"]) <= ts <= float(w["end_ts"]):
            return w
    return None


def stage_c_event_mining(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not tracks:
        return []
    tracks_sorted = sorted(tracks, key=lambda t: float(t["start_ts"]))
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = [tracks_sorted[0]]
    current_end = float(tracks_sorted[0]["end_ts"])

    for t in tracks_sorted[1:]:
        if float(t["start_ts"]) <= current_end + MAX_EVENT_GAP_SECONDS:
            current.append(t)
            current_end = max(current_end, float(t["end_ts"]))
        else:
            groups.append(current)
            current = [t]
            current_end = float(t["end_ts"])
    groups.append(current)

    events = []
    for idx, group in enumerate(groups, start=1):
        start_ts = min(float(t["start_ts"]) for t in group)
        end_ts = max(float(t["end_ts"]) for t in group)
        objects = sorted({str(t["class_name"]) for t in group})
        avg_conf = float(np.mean([float(t["max_conf"]) for t in group]))
        duration = end_ts - start_ts
        importance = round(duration * max(1, len(objects)) * avg_conf, 3)
        events.append(
            {
                "event_id": f"event_{idx:04d}",
                "start_ts": round(start_ts, 3),
                "end_ts": round(end_ts, 3),
                "duration_s": round(duration, 3),
                "objects_involved": objects,
                "track_ids": [int(t["track_id"]) for t in group],
                "confidence": round(avg_conf, 4),
                "importance_score": importance,
            }
        )
    events.sort(key=lambda e: e["importance_score"], reverse=True)
    return events


def _extract_event_keyframe(video_path: Path, event: dict[str, Any], out_path: Path) -> Path | None:
    mid_ts = (float(event["start_ts"]) + float(event["end_ts"])) / 2
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_idx = int(mid_ts * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), frame)
    return out_path


def stage_d_enrichment_and_summary(
    video_path: Path,
    job_path: Path,
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    enriched = []
    for idx, event in enumerate(events, start=1):
        image_path = _extract_event_keyframe(
            video_path,
            event,
            job_path / "artifacts" / f"event_{idx:04d}.jpg",
        )
        vl_description = ""
        if image_path is not None:
            try:
                vl_description = describe_event_from_image(image_path, event)
            except Exception:
                vl_description = ""
        item = dict(event)
        item["vl_description"] = vl_description
        enriched.append(item)

    try:
        summary_text = summarize_events(enriched)
    except Exception:
        summary_text = _fallback_summary(enriched)
    return enriched, summary_text


def _fallback_summary(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No se detectaron eventos relevantes."
    top = events[:5]
    lines = ["Resumen de eventos detectados:"]
    for event in top:
        lines.append(
            f"- {event['start_ts']}s a {event['end_ts']}s: "
            f"{', '.join(event['objects_involved']) or 'sin objetos'}."
        )
    return "\n".join(lines)


def process_video_job(job_id: str, video_path: Path, job_path: Path) -> dict[str, Any]:
    windows = stage_a_candidate_windows(video_path)
    write_json(job_path / "shots.json", windows)

    tracks, device = stage_b_tracking(video_path, windows)
    write_json(job_path / "tracks.json", tracks)

    class_timeline = defaultdict(lambda: {"count": 0, "total_duration_s": 0.0})
    for t in tracks:
        name = str(t["class_name"])
        class_timeline[name]["count"] += 1
        class_timeline[name]["total_duration_s"] += float(t["duration_s"])
    timeline = {
        k: {
            "count": v["count"],
            "total_duration_s": round(v["total_duration_s"], 3),
        }
        for k, v in class_timeline.items()
    }
    write_json(job_path / "objects_timeline.json", timeline)

    events = stage_c_event_mining(tracks)
    write_json(job_path / "events_raw.json", events)

    enriched, summary_text = stage_d_enrichment_and_summary(video_path, job_path, events)
    write_json(job_path / "events_enriched.json", enriched)

    summary_payload = {
        "job_id": job_id,
        "device_used": device,
        "events_count": len(enriched),
        "top_events": sorted(enriched, key=lambda e: e["importance_score"], reverse=True)[:10],
        "summary_text": summary_text,
    }
    write_json(job_path / "summary.json", summary_payload)

    return {
        "device_used": device,
        "shots_count": len(windows),
        "tracks_count": len(tracks),
        "events_count": len(enriched),
    }
