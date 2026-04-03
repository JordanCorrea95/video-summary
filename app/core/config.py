from pathlib import Path


STORAGE_DIR = Path("storage")
RESULTS_DIR = STORAGE_DIR / "results"
QUEUE_DIR = STORAGE_DIR / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
PROCESSING_DIR = QUEUE_DIR / "processing"
DONE_DIR = QUEUE_DIR / "done"
FAILED_DIR = QUEUE_DIR / "failed"

TMP_INPUT_DIR = Path("/tmp/video-summary-inputs")

YOLO_MODEL = "yolo26m.pt"
TRACKER_CONFIG = "botsort.yaml"

OLLAMA_URL = "http://localhost:11434"
OLLAMA_VL_MODEL = "qwen3-vl:8b"
OLLAMA_TEXT_MODEL = "llama3.2:3b"

MAX_EVENT_GAP_SECONDS = 3.0
MIN_EVENT_DURATION_SECONDS = 1.0
