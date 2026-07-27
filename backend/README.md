# backend/

Código em Python — API, pipelines de análise, motor de fusão de risco e integração com
serviços de nuvem. É a única parte do sistema que processa dados; o `frontend/` apenas
consome a API e não tem lógica própria.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `app/` | API (FastAPI) e o **banco local de pacientes** (SQLite): `db.py`/`repositorio.py` (pacientes, envios, análises, alertas), `armazenamento.py` (arquivos enviados), `analise.py` (dispara a análise da modalidade reusando os pipelines), `servico.py` (monta a linha do tempo de risco e registra alertas), `routes.py` (endpoints). Endpoints: pacientes (CRUD), envio de arquivo, disparo/consulta de análise, timeline consolidada, alertas, evidência por id |
| `common/` | Código compartilhado por todas as análises: formato de evidência (como cada anomalia detectada é registrada com seu artefato visual), métricas, configuração, log |
| `pipelines/vitals/` | Análise de sinais vitais em séries temporais: cardiotocografia (frequência cardíaca fetal, CTU-UHB) e internação adulta (frequência cardíaca e oxigenação/SpO2, BIDMC — `bidmc.py`), com detecção de anomalias |
| `pipelines/audio/` | Análise de áudio: dificuldade respiratória, transcrição, termos clínicos críticos, sinais de fadiga vocal. Transcrição/termos/sentimento/fadiga precisam de áudio de consulta real (roteiro de gravação em [`docs/roteiro-audio-consulta.md`](../docs/roteiro-audio-consulta.md)) |
| `pipelines/video/` | Análise de vídeo: duas raias — pose/movimentação (quedas com filtro dinâmico $V_y$ e rastreamento persistente de identidade multi-pessoa, ângulos articulares, inclinação de tronco, detector de pessoas configurável: YOLOv8n ou YOLO-NAS via ONNX/SuperGradients) e objeto/cirúrgica (YOLOv8 fine-tuned com evidência anotada) |
| `pipelines/audio/` | Análise de áudio: dispatch automático — com `.txt` (ICBHI respiratório) ou sem `.txt` (consulta: transcrição + acústica + termos críticos + fadiga vocal) |
| `pipelines/prescription/` | Leitura de prescrições (PDF) + checagem de dose/variação anômala + **gerador standalone** (`make gen-presc`) |
| `fusion/` | Combinação dos sinais das quatro análises acima num único indicador de risco, com alerta automático |
| `aws/` | Modo `aws`: chama só dois serviços gerenciados — Amazon Textract (texto de documentos) e Amazon Rekognition (rótulos de imagem). No modo `local` (padrão) nada aqui é usado. A seleção local/aws é feita por adaptadores intercambiáveis, escolhidos pela variável `ENV` |
| `scripts/` | Utilitários, incluindo o download dos conjuntos de dados públicos |
| `tests/` | Testes automatizados de tudo acima |

## Pipeline de vídeo — detectores de pessoas

A raia de postura/quedas suporta três backends de detecção de pessoas,
selecionáveis pela variável de ambiente `POSE_DETECTOR_BACKEND`:

| Backend | `POSE_DETECTOR_BACKEND` | Dependência | Peso |
| --- | --- | --- | --- |
| **YOLOv8n** *(default)* | `yolov8n` | `ultralytics` | ~6 MB |
| **YOLO-NAS S (ONNX)** | `yolo_nas_s` | `onnxruntime` | ~47 MB |
| **YOLO-NAS M (ONNX)** | `yolo_nas_m` | `onnxruntime` | ~80 MB |
| **YOLO-NAS (SuperGradients)** | `yolo_nas_s` ou `yolo_nas_m` | `super-gradients` | gerido pelo pacote |

O modelo ONNX é descarregado automaticamente de
`media.axelera.ai` na primeira utilização e cached em `models/`. Se o download
falhar, coloque o `.onnx` manualmente nesse diretório.

```bash
# YOLO-NAS S via ONNX (recomendado)
POSE_DETECTOR_BACKEND=yolo_nas_s PYTHONPATH=backend .venv/bin/python \
  -m pipelines.video.cli --config backend/pipelines/video/configs/demo.yaml

# YOLOv8n (default)
PYTHONPATH=backend .venv/bin/python -m pipelines.video.cli --config ...
```

### Rastreamento de identidade (multi-pessoa)

O tracker IoU entre frames consecutivos atribui um `track_id` estável a cada
pessoa detetada. Quando uma queda é confirmada, a evidência visual usa
**exclusivamente** o esqueleto da pessoa com o `track_id` que disparou o evento
— resolvendo o problema de a ordem da lista de poses mudar entre frames.

O tracking está sempre ativo; o estado é reiniciado entre sequências via
`reset_person_tracker()`.

## Como rodar os testes

```bash
make test         # suíte completa
make test-unit    # só os testes rápidos (sem tocar em serviços externos)
make lint         # checagem de estilo
```
