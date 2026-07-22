# training/

Pasta de topo, irmã de `backend/` e `frontend/`, para a etapa de treino que precisa de
GPU (AD-042). O sistema em operação (`backend/`) continua 100% CPU (AD-012) — só este
treino offline do YOLOv8 usa GPU, via Google Colab.

**Não reimplementa nada de F1.** O notebook importa e chama o código já testado de
`backend/pipelines/video/object_finetune.py`, `object_loader.py`, `object_detector.py` e
`object_evaluate.py` (362 testes verdes, Verifier PASS) — F1 não é modificada por esta
pasta.

## Por que isto existe

`object_finetune.finetune()` (F1) já treina o YOLOv8n sobre o Endoscapes-BBox201 real,
mas foi validado com um treino curto (`epochs=1`) em CPU — suficiente para provar o
pipeline (AC de F1), insuficiente para produzir pesos com boa precisão. Rodar mais
épocas em CPU é inviável no prazo; a GPU gratuita do Colab resolve isso sem violar
AD-012 (a inferência do sistema em produção continua CPU-only — só o treino usa GPU).

## Passo 1 — preparar o subconjunto de dados (local, antes do Colab)

O diretório `data/endoscapes/endoscapes/train/` tem 36694 `.jpg`, mas cada
`annotation_coco.json` (train/val/test) só referencia um subconjunto anotado (1212 +
409 + 312 = 1933 imagens, ~207 MB). Subir os 36694 arquivos brutos (~6 GB) ao Drive
violaria o requisito de não subir o dataset inteiro. Em vez disso:

```bash
make data                                    # se ainda não baixou data/endoscapes/
PYTHONPATH=backend .venv/bin/python training/prepare_dataset_subset.py
```

Isso reusa `pipelines.video.object_loader.load_annotated_frames` (mesmo parser de F1,
não reimplementado) para copiar só as imagens referenciadas em cada split para
`training/staging/{train,val,test}/`, junto com o `annotation_coco.json` de cada um.

Depois, zipe e suba ao Google Drive:

```bash
cd training && zip -r endoscapes_staging.zip staging/ && cd ..
```

Suba `endoscapes_staging.zip` para o seu Google Drive (qualquer pasta — o notebook pede
o caminho).

## Passo 2 — rodar o notebook no Colab

Abra `train_yolo_endoscapes.ipynb` no [Google Colab](https://colab.research.google.com/),
selecione **Ambiente de execução → Alterar tipo de ambiente de execução → GPU**, e rode
as células em ordem. O notebook:

1. Monta o Drive e descompacta `endoscapes_staging.zip`.
2. Clona o repositório (só para importar o código de F1 — nenhum dado vem daqui).
3. Instala `requirements-training.txt`.
4. Chama `object_finetune.finetune()` real, com épocas/tamanho de imagem completos
   (seed fixa, `epochs=50`, `imgsz=640` — ajustável no notebook), salvando `best.pt` e
   `results.csv` **diretamente no Drive** (a sessão do Colab cai por inatividade — nunca
   depender do disco efêmero `/content`).
5. Avalia o `best.pt` recém-treinado contra o split `test/` oficial do Endoscapes — que o
   treino **nunca viu** — usando `object_loader` + `object_detector.YoloDetector` +
   `object_evaluate.evaluate` (todos já existentes em F1). Essa é a métrica honesta
   reportada, não a validação interna do treino.

**Nota de metodologia**: `object_finetune.finetune()` (código de F1, não alterado aqui)
usa o próprio split de treino como validação interna durante o treino — F1 não foi
desenhada com um split de validação separado. Como não modificamos F1, a métrica que de
fato importa (e que vai para o relatório técnico) é a avaliação pós-treino contra
`test/`, no passo 5, nunca a validação interna do `finetune()`.

## Passo 3 — publicar o peso

```bash
# baixe do Drive: best.pt, results.csv, metrics_test.json → coloque em models/
```

1. Preencha `models/README.md` com proveniência (notebook, hiperparâmetros, seed, data,
   métricas de `metrics_test.json`).
2. Publique `best.pt` como asset de um [GitHub Release](https://github.com/AnaPRodrigues/8iadt-tc-fase4-multi-monitoring/releases)
   do repositório.
3. Atualize `MODEL_RELEASE_URL` no `Makefile` com a URL do asset publicado.
4. Quem só quer rodar a demo (sem retreinar) roda `make models-fetch`.

## Splits oficiais do Endoscapes (medido nesta sessão)

| Split | Imagens | Anotações |
| --- | --- | --- |
| `train/` | 1212 | 5566 |
| `val/` | 409 | 1733 |
| `test/` | 312 | 1485 |

Nunca embaralhar frames soltos entre splits — frames vizinhos de um mesmo vídeo
cirúrgico são quase idênticos; misturar treino/teste vazaria a métrica.
