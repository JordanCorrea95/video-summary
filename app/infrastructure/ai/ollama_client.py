import base64
from pathlib import Path
from typing import Any

import requests

from app.core.config import OLLAMA_TEXT_MODEL, OLLAMA_URL, OLLAMA_VL_MODEL


def _post_chat(model: str, messages: list[dict[str, Any]], timeout: int = 120) -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"].strip()


def describe_event_from_image(image_path: Path, event: dict[str, Any]) -> str:
    if not image_path.exists():
        return ""
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    prompt = (
        "Describe briefly the key event in this frame. "
        f"Objects detected: {event.get('objects_involved', [])}. "
        "Return one short sentence in Spanish."
    )
    messages = [
        {
            "role": "user",
            "content": prompt,
            "images": [encoded],
        }
    ]
    return _post_chat(OLLAMA_VL_MODEL, messages, timeout=180)


def summarize_events(events: list[dict[str, Any]]) -> str:
    prompt = (
        "Genera un resumen ejecutivo en español de los eventos detectados.\n"
        "Debe incluir: eventos más importantes, objetos involucrados y sus rangos temporales.\n"
        "Manténlo conciso y claro.\n"
        f"Eventos:\n{events}"
    )
    messages = [{"role": "user", "content": prompt}]
    return _post_chat(OLLAMA_TEXT_MODEL, messages)
