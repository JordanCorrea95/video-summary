# Arquitectura escalable aplicada

## Decisiones de estructura

- `api/`: capa HTTP pura (routers y contratos de entrada/salida).
- `application/`: casos de uso (orquesta upload, consulta, ejecución de worker).
- `infrastructure/`: detalles técnicos (storage JSON, cola por archivos, visión, Ollama).
- `core/`: configuración compartida.
- `workers/`: procesos batch desacoplados del ciclo HTTP.

Esta separación evita acoplar rutas FastAPI con lógica de visión o E/S de archivos, y facilita escalar workers y reemplazar infraestructura sin tocar la capa API.

## Referencias usadas para la estructura (SOTA/industry)

- FastAPI recomienda separar aplicaciones grandes por routers y módulos:
  - https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI en despliegues productivos sugiere procesos separados (API/worker):
  - https://fastapi.tiangolo.com/deployment/concepts/
- Organización de proyectos de datos/ML en capas y artefactos reproducibles:
  - https://cookiecutter-data-science.drivendata.org/
- Principios de configuración y aislamiento por procesos (12-factor):
  - https://12factor.net/

