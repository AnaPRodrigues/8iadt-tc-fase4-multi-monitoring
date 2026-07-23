# models/

Pasta para os modelos já treinados. **Não é versionada no Git** — só este README fica
no repositório; o arquivo de peso em si é grande demais para um repositório de código
e fica publicado num repositório de modelo público no
[Hugging Face Hub](https://huggingface.co/AnaPRodrigues/endoscapes-surgical-detector).

## Como obter o modelo treinado

```bash
make models-fetch
```

Baixa o peso do detector de estruturas cirúrgicas para `models/best.pt` — o caminho
que o sistema espera encontrar ao carregar o modelo para fazer detecções.

## Como treinar do zero

O detector de estruturas cirúrgicas é treinado separadamente, numa GPU (ver
`training/README.md`) — o sistema em si nunca treina, só carrega o resultado.

O classificador que identifica dificuldade respiratória em áudio é diferente: ele é
rápido o bastante para treinar em segundos, num processador comum, então é treinado
automaticamente toda vez que a análise de áudio roda — não existe um arquivo de peso
salvo para ele.

---

## Proveniência do modelo publicado

Preenchido a partir do treino real rodado em `training/train_yolo_endoscapes.ipynb`
(saída completa arquivada em `training/endoscapes_training_output/` — `metrics_test.json`,
`results_yolov8n.csv`, `results_yolov8s.csv`).

### Detector de estruturas cirúrgicas — dois modelos treinados e validados, `yolov8s` publicado

O notebook treina **duas variantes completas** (YOLOv8n e YOLOv8s, mesmo dataset,
mesmos hiperparâmetros) e escolhe a vencedora pelo desempenho real contra o split de
teste — nenhuma das duas é descartada sem avaliação, e ambas ficam documentadas aqui
para rastreabilidade, mesmo só a vencedora sendo publicada.

**Hiperparâmetros e dados (idênticos para as duas variantes)**

| Campo | Valor |
| --- | --- |
| Como foi gerado | `training/train_yolo_endoscapes.ipynb` |
| Data do treino | 2026-07-23 |
| Número de repetições sobre os dados (épocas) | 100 |
| Resolução de imagem usada no treino | 640×640 |
| Semente aleatória (para reprodutibilidade) | 42 |
| Imagens de treino | 1212, com 5566 estruturas anotadas |
| Imagens de avaliação (nunca vistas no treino) | 312, com 1485 estruturas anotadas |

**Comparação entre as duas variantes validadas contra o split de teste** (de `metrics_test.json`):

| Variante | Precisão média | Recall médio | mAP50 | mAP50-95 | Histórico completo (por época) |
| --- | --- | --- | --- | --- | --- |
| `yolov8n` | 0.7010 | 0.5787 | 0.5820 | 0.3622 | `training/endoscapes_training_output/results_yolov8n.csv` |
| **`yolov8s`** — **vencedora, publicada** | **0.7147** | **0.5982** | **0.6046** | **0.3837** | `training/endoscapes_training_output/results_yolov8s.csv` |

`yolov8s` venceu nas 4 métricas — margem modesta (~2 p.p. de mAP50-95), mas
consistente. O critério de desempate foi o mAP50-95 (mAP médio sobre vários limiares
de IoU — mais rigoroso que o mAP50 porque também pune caixas mal localizadas, não só
classificação errada), conforme documentado em `training/README.md`. Só o peso da
`yolov8s` foi publicado (é o que `make models-fetch` baixa como `models/best.pt`); o
peso da `yolov8n` fica arquivado em
`training/endoscapes_training_output/runs/finetune_yolov8n/weights/best.pt` (não
versionado, mesma regra de `models/` — só existe localmente).

| Campo | Valor |
| --- | --- |
| Versão publicada no Hugging Face | [AnaPRodrigues/endoscapes-surgical-detector](https://huggingface.co/AnaPRodrigues/endoscapes-surgical-detector) — `best.pt` (pesos da `yolov8s`), 22,5 MB (verificado publicado) |
