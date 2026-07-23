# models/

Pasta para os modelos já treinados. **Não é versionada no Git** — só este README fica
no repositório; o arquivo de peso em si é grande demais para um repositório de código
e fica publicado como anexo de uma versão ("Release") do projeto no GitHub.

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

> ⚠️ **Ainda não preenchido** — nenhum treino completo rodou ainda. Preencher esta
> seção depois de rodar `training/train_yolo_endoscapes.ipynb` e antes de publicar o
> Release.

### `best.pt` — detector de estruturas cirúrgicas

| Campo | Valor |
| --- | --- |
| Como foi gerado | `training/train_yolo_endoscapes.ipynb` |
| Data do treino | _pendente_ |
| Número de repetições sobre os dados (épocas) | _pendente_ |
| Resolução de imagem usada no treino | _pendente_ |
| Semente aleatória (para reprodutibilidade) | _pendente_ |
| Imagens de treino | 1212, com 5566 estruturas anotadas |
| Imagens de avaliação (nunca vistas no treino) | 312, com 1485 estruturas anotadas |
| Precisão/revocação por estrutura | _pendente — ver `metrics_test.json` gerado pelo notebook de treino_ |
| Versão publicada no GitHub | _pendente_ |
