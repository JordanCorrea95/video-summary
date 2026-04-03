# video-summary

Servicio FastAPI para resumir videos largos (batch, no realtime) con:

- YOLO (`yolo26m.pt`) + tracking (`BoT-SORT`) con fallback GPU -> CPU.
- OpenCV para prefiltrado temporal eficiente.
- Ollama (`qwen3-vl:8b`, `llama3.2:3b`) para enriquecimiento y resumen textual.

## Estructura del proyecto

La estructura sigue un enfoque por capas (API / aplicación / infraestructura), recomendado para servicios escalables:

```text
app/
  api/
    app.py
    routers/
    schemas/
  application/
    services/
  core/
    config.py
  infrastructure/
    ai/
    queue/
    storage/
    vision/
  workers/
    runner.py
  main.py        # compat wrapper
  worker.py      # compat wrapper
```

## Flujo

1. `POST /videos` guarda el video y crea job en cola por archivos.
2. Worker consume la cola y ejecuta pipeline por etapas.
3. Resultados se persisten en JSON bajo `storage/{job_id}/`.
4. `GET /videos/{job_id}/status|events|summary` expone el estado y resultado.

## Salidas por job

- `storage/results/{job_id}/status.json`
- `storage/results/{job_id}/shots.json`
- `storage/results/{job_id}/tracks.json`
- `storage/results/{job_id}/objects_timeline.json`
- `storage/results/{job_id}/events_raw.json`
- `storage/results/{job_id}/events_enriched.json`
- `storage/results/{job_id}/summary.json`

Nota: el video de entrada se guarda temporalmente en `/tmp` y se elimina al terminar el job.
Nota: `storage/queue/*` solo contiene marcadores operativos de cola, sin datos de resultados.

## Ejecución

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

En otra terminal:

```bash
python -m app.worker
```

Modo manual (sin daemon):

```bash
curl -X POST http://localhost:8000/workers/run-once
```
