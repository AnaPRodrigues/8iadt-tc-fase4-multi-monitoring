# Treino do detector de estruturas cirúrgicas

Esta pasta contém tudo que é preciso para treinar, do zero, o modelo que reconhece
estruturas anatômicas e instrumentos em imagens de cirurgia laparoscópica. É um mundo
totalmente separado do resto do sistema: nada aqui depende do código de `backend/` ou
`frontend/`, e nada em `backend/`/`frontend/` depende do código daqui — a única coisa
que os conecta é o arquivo de peso treinado (`models/best.pt`), que o sistema carrega
para fazer a detecção.

## Por que treinar separado

O treino de uma rede neural é muito mais rápido numa GPU do que num processador comum
(CPU) — pode ser a diferença entre minutos e horas. O restante do sistema (a parte que
roda a demonstração, analisa vídeo/áudio/sinais vitais/prescrições) foi propositalmente
desenhado para rodar inteiro em CPU, sem depender de GPU nem de custo de nuvem. Por
isso o treino do modelo de detecção fica isolado aqui, pensado para rodar no
[Google Colab](https://colab.research.google.com/), que oferece uma GPU gratuita — o
sistema em produção só carrega o resultado (o arquivo de pesos), nunca treina nada
sozinho.

## Passo 1 — preparar as imagens (na sua máquina, antes do Colab)

O dataset de imagens cirúrgicas usado aqui (Endoscapes2023, aberto e gratuito) tem
dezenas de milhares de imagens no total, mas só um subconjunto delas tem anotação
(rótulo de onde está cada estrutura anatômica) — é só esse subconjunto que serve para
treinar. Baixe o dataset completo e depois separe só o que interessa:

```bash
make data                                   # baixa os datasets, se ainda não baixou
python3 training/prepare_dataset_subset.py
```

Isso copia só as ~1900 imagens anotadas (cerca de 200 MB) para
`training/staging/{train,val,test}/`, junto com o arquivo de anotação de cada grupo —
bem menor que subir o dataset inteiro (vários gigabytes) para o Google Drive.

Depois, compacte e suba ao Google Drive:

```bash
cd training && zip -r endoscapes_staging.zip staging/ && cd ..
```

Suba `endoscapes_staging.zip` para o seu Google Drive (qualquer pasta — o notebook vai
pedir o caminho).

## Passo 2 — rodar o notebook no Colab

1. Abra `train_yolo_endoscapes.ipynb` em [colab.research.google.com](https://colab.research.google.com/).
2. No menu, escolha **Ambiente de execução → Alterar tipo de ambiente de execução → GPU**.
3. Envie também o arquivo `finetune.py` (desta mesma pasta) para o Colab — arraste-o
   para o painel de arquivos à esquerda, na raiz de `/content/`.
4. Rode as células em ordem. O notebook:
   - monta o seu Google Drive e descompacta o zip preparado no passo 1;
   - instala a biblioteca de treino (`ultralytics`);
   - treina **duas variantes** de modelo base, YOLOv8n e depois YOLOv8s, uma de cada
     vez (a GPU grátis do Colab só roda um treino por vez), sempre com as mesmas
     imagens de treino e validação, salvando o resultado de cada uma **direto no
     Drive** (a sessão do Colab pode cair a qualquer momento — nunca conte com o que
     fica só no disco temporário do Colab);
   - avalia as duas variantes treinadas contra as imagens de teste, que elas nunca
     viram durante o treino — essa é a métrica de qualidade que importa de verdade,
     não o desempenho durante o treino em si — e escolhe a vencedora pelo mAP50-95
     (métrica mais rigorosa: também pune caixas mal localizadas, não só classificação
     errada), gravando o resultado da comparação em `metrics_test.json`.

O treino usa por padrão 50 repetições sobre os dados (épocas) e imagens em 640x640
pixels — ajustável nas primeiras linhas da célula de treino do notebook. YOLOv8n é
menor e mais rápido para treinar/inferir; YOLOv8s tem mais capacidade e tende a
generalizar melhor com mais dados, ao custo de treino/inferência mais lentos — o
notebook deixa a comparação real decidir em vez de assumir qual variante é melhor
para este dataset.

## Passo 3 — publicar o peso treinado

1. Confira em `metrics_test.json` (no Drive) o campo `melhor_variante` — diz qual das
   duas (`yolov8n` ou `yolov8s`) venceu a comparação. Baixe **só o `best.pt` dessa
   variante** (em `runs/finetune_<melhor_variante>/weights/best.pt`), junto com
   `results_<melhor_variante>.csv` e `metrics_test.json`, para a pasta `models/` deste
   repositório, na sua máquina.
2. Preencha `models/README.md` com a data do treino, os parâmetros usados, qual
   variante venceu e as métricas obtidas.
3. Publique `best.pt` no repositório de modelo público do
   [Hugging Face Hub](https://huggingface.co/AnaPRodrigues/endoscapes-surgical-detector)
   (crie o repo em huggingface.co/new, tipo "Model", se ainda não existir). Duas formas
   de subir o arquivo:
   - pela interface web: aba "Files and versions" → "Add file" → "Upload files";
   - ou via linha de comando (`pip install huggingface_hub` e depois
     `huggingface-cli upload AnaPRodrigues/endoscapes-surgical-detector best.pt`).
4. A partir daí, qualquer pessoa que só queira usar o modelo (sem retreinar) roda
   `make models-fetch` e baixa o peso pronto automaticamente — o `Makefile` já aponta
   para esse repositório, não precisa configurar nada.

## Sobre os dados

O dataset já vem oficialmente dividido em três grupos — treino, validação e teste — e
essa divisão nunca deve ser embaralhada: imagens vizinhas de um mesmo vídeo cirúrgico
são quase idênticas entre si, então misturar imagens dos três grupos faria o modelo
"decorar" em vez de aprender, e a métrica final pareceria melhor do que realmente é.

| Grupo | Imagens | Estruturas anotadas |
| --- | --- | --- |
| Treino | 1212 | 5566 |
| Validação | 409 | 1733 |
| Teste | 312 | 1485 |
