# models/

Diretório para pesos treinados — **não versionado** (só este README entra no Git,
mesmo padrão de `data/`, AD-043). Pesos grandes não pertencem ao Git; ficam publicados
como asset de um GitHub Release e são baixados sob demanda com `make models-fetch`.

## Como obter os pesos

```bash
make models-fetch
```

Baixa `best.pt` (YOLOv8, F1) do GitHub Release configurado em `MODEL_RELEASE_URL` no
`Makefile`, para `models/best.pt` — o caminho que `object_detector.py`/`adapters.py`
esperam.

## Como (re)treinar

Ver `training/README.md` — o YOLOv8 treina no Google Colab (GPU); o classificador de
áudio de F2 treina em CPU, em memória, a cada execução do CLI (`icbhi_classifier.py`,
sem artefato persistido — AD-008, ver `.specs/STATE.md` § Decisões).

---

## Proveniência dos pesos

> ⚠️ **Ainda não preenchido** — nenhum treino real (fora do smoke test de F1) rodou
> ainda. Preencher esta seção depois de rodar `training/train_yolo_endoscapes.ipynb` e
> antes de publicar o Release.

### `best.pt` (YOLOv8n, detecção de objeto/área crítica — Endoscapes-BBox201)

| Campo | Valor |
| --- | --- |
| Notebook | `training/train_yolo_endoscapes.ipynb` |
| Data do treino | _pendente_ |
| Épocas | _pendente_ |
| `imgsz` | _pendente_ |
| Seed | _pendente_ |
| Split de treino | `data/endoscapes/endoscapes/train/` (1212 imagens, 5566 anotações) |
| Split de avaliação (nunca visto no treino) | `data/endoscapes/endoscapes/test/` (312 imagens, 1485 anotações) |
| Precision/recall/F1 por classe (IoU ≥ 0.5) | _pendente — ver `metrics_test.json` gerado pelo notebook_ |
| GitHub Release | _pendente_ |
