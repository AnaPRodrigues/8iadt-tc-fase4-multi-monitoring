# Backend

Python — FastAPI + pipelines + fusão + integração AWS. Fonte única de lógica de
processamento; o `frontend/` apenas consome a API (AD-029).

## Layout

| Pasta | Papel |
| --- | --- |
| `app/` | FastAPI: rotas, schemas, `main`. Contrato REST versionado: `/patients/{id}/timeline`, `/analyze`, `/alerts`, `/evidence/{id}` |
| `common/` | Código compartilhado por todos os pipelines: formato de evidência, métricas, config, logging (o antigo `src/core/`). **Nome a confirmar** (AD-030) |
| `pipelines/vitals/` | F3 — CTU-UHB/MIT-BIH + detectores. **A migrar de `src/vitals/`** (AD-032) |
| `pipelines/audio/` | F2 — faster-whisper + librosa + termos críticos |
| `pipelines/video/` | F1 — YOLOv8 + cliente Rekognition |
| `pipelines/prescription/` | F4 — cliente Textract + parser + regras |
| `fusion/` | F5 — late fusion, score de risco, níveis |
| `aws/` | `clients.py` (factory boto3 por `ENV`, AD-034), `adapters/` (`TextExtractor`/`ImageAnalyzer` cloud+local, AD-035), `lambdas/` (handlers). Perfis local (LocalStack) / cloud (Learner Lab) |
| `scripts/` | `download_datasets` (F0) e outros utilitários |
| `tests/` | Testes do backend (os 165 de F3 migram para cá) |

## Estado atual

F3 ainda vive em `src/` na raiz do repositório (165 testes passando). A migração
para esta estrutura é a primeira etapa de execução após aprovação do STATE.md.
