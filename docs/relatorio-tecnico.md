# Relatório Técnico — Monitoramento Hospitalar Multimodal

**Tech Challenge — Fase 4 · POSTECH 8IADT**

Sistema de monitoramento contínuo de pacientes por dados multimodais (vídeo, áudio,
sinais vitais e texto), com fusão de risco e alerta automático à equipe médica.

---

## 1. Visão geral

O sistema recebe quatro fontes de dados de um paciente e as transforma num único
indicador de risco ao longo do tempo, disparando um alerta explicável quando o risco
cruza um limiar. As quatro análises são independentes entre si e só se comunicam por um
contrato comum de **evidência** (um artefato visual + um descritor JSON gravados em
disco). Uma camada de **fusão** lê essas evidências, calcula um risk score ponderado com
decaimento temporal, classifica em verde/amarelo/vermelho com histerese e publica o
alerta. Uma **API REST** expõe o resultado e um **painel** o apresenta.

Decisão de projeto transversal: **toda anomalia é reproduzível**. Nenhuma análise
reporta um risco sem gravar a evidência que o justifica (imagem anotada, gráfico da
janela anômala, trecho de áudio, PDF marcado). Isso torna o sistema auditável e é o que
permite o drill-down por evento no painel.

---

## 2. Fluxo multimodal

```
Dados brutos          Análise (independente)        Evidência           Fusão              Saída
────────────          ──────────────────────        ─────────           ─────              ─────
vídeo (URFD/         → pose (MediaPipe) +          → output/video_*/  ┐
 Endoscapes)           objetos (YOLOv8)                                │
áudio (ICBHI/        → respiração + transcrição   → output/audio/    ┤   loader →
 consulta)             + termos + fadiga vocal                        ├   risk_engine →   → risk score
vitais (CTU-UHB)     → anomalia em série temporal → output/vitals/   ┤   hysteresis →      (verde/
prescrição (PDF)     → extração + regras de dose  → output/prescr./  ┘   alert            amarelo/
                                                                                           vermelho)
                                                                          │
                                                                          └→ alerta explicável (gerado localmente) → equipe médica
                                                                          └→ API REST → painel Streamlit
```

Cada análise roda isoladamente (pode rodar em máquinas/momentos diferentes) e grava sua
evidência. A fusão é orientada por uma **config curada do paciente-demo**
(`backend/pipelines/fusion/configs/demo.yaml`), que referencia uma evidência real de
cada modalidade e atribui a cada uma um instante na linha do tempo da demonstração.

### Por que a linha do tempo é curada manualmente

Os quatro datasets usados são reais, públicos e **de pacientes diferentes** — não existe
um paciente real que apareça simultaneamente no vídeo, no áudio, nos vitais e nas
prescrições. Além disso, os formatos de tempo de cada fonte são incompatíveis entre si.
Portanto, o *paciente-demo* é uma **composição didática documentada** (decisão AD-024):
ele demonstra o **mecanismo** de fusão multimodal — peso por modalidade, decaimento
temporal, histerese e explicabilidade — não uma correlação clínica real entre as quatro
fontes. Cada evento referenciado é, ainda assim, uma anomalia **real** detectada pela
sua análise de origem sobre dado real.

---

## 3. Modelos aplicados em cada tipo de dado

### 3.1 Vídeo

Duas raias independentes, cobrindo os dois modelos pedidos no enunciado:

| Raia | Modelo | Dataset | O que detecta |
| --- | --- | --- | --- |
| Postura / movimentação | **MediaPipe Pose** (33 keypoints) | UR Fall Detection (URFD) | Quedas e padrões de movimentação, por métricas de movimento por janela (amplitude, velocidade, assimetria do centro de massa) classificadas contra um limiar |
| Objetos / áreas críticas | **YOLOv8 fine-tuned** | Endoscapes2023 | Estruturas anatômicas e instrumentos em cirurgia laparoscópica (ex.: artéria/ducto cístico como estruturas críticas) |

**Substituição do OpenPose:** o enunciado sugere OpenPose para análise postural; usamos
**MediaPipe Pose** como equivalente moderno (mesma finalidade — extração de esqueleto 2D
— porém CPU-friendly e sem a barreira de build do OpenPose). A saída (keypoints por
frame) e a lógica de detecção de queda são próprias e testadas.

**Treino do YOLOv8:** o detector foi fine-tunado à parte (Google Colab, GPU gratuita) —
ver seção 5.1 para os resultados. O sistema em produção nunca treina; só carrega o peso
publicado.

### 3.2 Áudio

| Etapa | Técnica | Dataset |
| --- | --- | --- |
| Dificuldade respiratória | Random Forest sobre features acústicas, 4 classes (normal / crackle / wheeze / both) | ICBHI 2017 (sons respiratórios anotados) |
| Transcrição | **faster-whisper** local (pt-BR), com flag de confiabilidade | áudio de consulta |
| Termos clínicos críticos | Léxico curado sobre o transcript | áudio de consulta |
| Sentimento | Léxico curado (positivo/negativo) | áudio de consulta |
| Fadiga vocal | Score heurístico (jitter/shimmer/HNR via Parselmouth), marcado explicitamente como heurística não validada clinicamente | áudio de consulta |

**Substituição do Azure:** o enunciado pede Azure Speech to Text e Azure Text Analytics.
Substituímos por equivalentes **locais** (faster-whisper para transcrição; léxicos
próprios para termos críticos e sentimento) — mesma capacidade funcional, sem
dependência de serviço pago/credenciado e roda 100% em CPU (decisão AD-003).

### 3.3 Sinais vitais

Detecção de anomalia em séries temporais por dois detectores complementares:

- **z-score móvel** (outlier estatístico contra a janela local);
- **Isolation Forest** (anomalia multivariada sobre features de janela).

O rótulo de referência (*ground truth*) é **clínico e real** — o pH do cordão umbilical
registrado no header do próprio registro CTU-UHB (pH < 7.05 ≈ acidose/sofrimento fetal),
não uma anomalia injetada artificialmente. Features de domínio de cardiotocografia
(baseline, variabilidade de curto prazo, decelerações segundo convenção NICHD) dão
significado clínico às anomalias estatísticas.

### 3.4 Prescrições

Leitura de receita em PDF → estruturação em registro → regras clínicas:

- **Extração de texto**: `pdfplumber` (modo local) ou **AWS Textract** `analyze_document`
  (modo aws), intercambiáveis pelo mesmo adapter;
- **Regras**: dose fora da faixa segura do fármaco; variação abrupta de dose contra a
  prescrição anterior do paciente (o histórico é uma fonte de dados local injetada no
  processamento).

Campo ausente ou não numérico é **sinalizado**, nunca inferido por suposição.

### 3.5 Fusão e alerta

- **Risk score por janela**: `score(t) = Σ_modalidade  peso · severidade · decay(Δt)`,
  com `decay(Δt) = 2^(−Δt / meia-vida)` (meia-vida default 600 s). Sinais antigos perdem
  peso gradualmente, evitando um nível "preso" por um evento já resolvido.
- **Classificação com histerese**: verde < 0.3, amarelo 0.3–0.7, vermelho > 0.7, com
  banda de ±0.05. O classificador mantém estado entre janelas: só muda de nível ao
  cruzar `limiar ± histerese`, o que impede oscilação na fronteira.
- **Modalidade ausente é explícita**: uma modalidade sem dado na janela entra em
  `missing_modalities` — nunca contribui como "risco zero" silencioso.
- **Alerta explicável**: ao cruzar o nível de disparo, o sistema gera **localmente** um
  alerta com o nível, as modalidades contribuintes e os links da evidência, exibido pela
  interface (não há envio por serviço de notificação). Uma chave determinística a partir
  das evidências contribuintes identifica o conjunto de eventos, evitando alertas
  duplicados para o mesmo conjunto.

---

## 4. Exemplo de anomalias detectadas (paciente-demo)

A config curada compõe uma narrativa de deterioração com **quatro anomalias reais**, uma
por modalidade:

| Tempo | Modalidade | Evidência real | Anomalia detectada |
| --- | --- | --- | --- |
| t = 0 s | Vídeo (URFD `fall-01`) | frame anotado da queda | Queda detectada pela raia de pose (score de movimento 0.31) |
| t = 300 s | Vitais (CTU-UHB reg. 1001) | gráfico da janela anômala | Janela anômala pelo Isolation Forest; pH real do registro = 7.14 (acidose fetal) |
| t = 600 s | Prescrição (paciente p3) | PDF anotado | Mudança abrupta de dose de losartana (50 mg → 100 mg, +100%) |
| t = 900 s | Áudio (ICBHI) | trecho do ciclo respiratório | Sibilo (wheeze) detectado em ciclo respiratório real |

Ao alimentar a fusão com essa sequência, o risk score sobe a cada evento, o nível
escala de verde a vermelho, e o cruzamento do limiar de disparo gera o alerta explicável
à equipe. Esse é exatamente o cenário reproduzido no painel (replay controlado) e no
vídeo de demonstração.

---

## 5. Resultados obtidos

### 5.1 Detector de estruturas cirúrgicas (YOLOv8)

Treinamos **duas variantes** (YOLOv8n e YOLOv8s) com hiperparâmetros idênticos (100
épocas, resolução 640×640, seed 42) sobre o Endoscapes2023 (1212 imagens de treino /
5566 estruturas anotadas), e comparamos ambas contra o split de teste oficial (312
imagens / 1485 estruturas, **nunca vistas no treino**):

| Variante | Precisão média | Recall médio | mAP@50 | mAP@50-95 |
| --- | --- | --- | --- | --- |
| YOLOv8n | 0.7010 | 0.5787 | 0.5820 | 0.3622 |
| **YOLOv8s** (publicado) | **0.7147** | **0.5982** | **0.6046** | **0.3837** |

A **YOLOv8s venceu nas quatro métricas**; o critério de desempate foi o mAP@50-95 (mais
rigoroso, pune caixas mal localizadas). Só o peso vencedor foi publicado no Hugging Face
Hub e é o que o sistema carrega. Detalhes em [`models/README.md`](../models/README.md).

### 5.2 Verificação por funcionalidade

Cada funcionalidade fechada passou por uma verificação independente (author ≠ verifier)
com cobertura por critério de aceite e **sensor de discriminação** (injeta defeitos e
confirma que os testes os detectam). Relatórios completos em
`.specs/features/<nome>/validation.md`.

| Funcionalidade | Veredito | Nota |
| --- | --- | --- |
| Aquisição de dados | ✅ PASS | Download idempotente e retomável dos 5 datasets |
| Seleção de adaptador local/aws | ✅ PASS | Factory por `ENV`; caminho de nuvem testado com dublê do SDK |
| Vídeo (pose + objetos) | ✅ PASS | Todas as ACs verificadas |
| Áudio | ✅ PASS | Fechado na 2ª iteração de verificação |
| Sinais vitais | ✅ PASS | 165/165 testes; 16/17 mutações mortas |
| Prescrições | ✅ PASS | 2 lacunas menores de precisão de teste, documentadas |
| Fusão e alerta | ✅ PASS | Fechado após corrigir 2 lacunas de cobertura apontadas pelo verificador |

**Suíte de testes**: 435 testes passando (unitários + integração), zero falhas, sem
depender de Docker nem de credencial de nuvem; checagem de estilo limpa.

---

## 6. Integração com a nuvem

O sistema tem **dois modos de operação**, escolhidos pela variável `ENV`:

- **`local` (padrão)** — nenhuma chamada de nuvem. Todo o processamento roda na máquina
  (pdfplumber para PDF, YOLOv8 para imagem, e o resto das análises em CPU). É o modo
  usado para desenvolver, testar e rodar a demonstração — sem Docker, sem conta na nuvem.
- **`aws`** — usa **exatamente dois** serviços gerenciados, chamados de forma síncrona
  com o arquivo embutido na requisição (sem bucket intermediário): **Amazon Textract**
  (`analyze_document`, `Document={'Bytes': ...}`) para texto/campos de prescrições e
  **Amazon Rekognition** (`detect_labels`, `Image={'Bytes': ...}`) para rótulos de
  objetos em quadros de vídeo. O resultado volta para o processamento local.

Nenhum outro serviço de nuvem é usado — sem S3, sem DynamoDB, sem SNS, sem filas, sem
funções serverless. A seleção local/aws é feita por adaptadores intercambiáveis; o
restante do código é idêntico nos dois modos.

### Mapeamento Azure → AWS / local

| Sugerido no enunciado (Azure) | Usado no projeto | Onde |
| --- | --- | --- |
| Azure Speech to Text | faster-whisper (local) | `pipelines/audio/transcribe.py` |
| Azure Text Analytics (termos/sentimento) | Léxicos locais | `pipelines/audio/{critical_terms,sentiment}.py` |
| Serviço de visão (imagem) | YOLOv8 (local) / AWS Rekognition (aws) | `aws/adapters/cloud.py` |
| Serviço de documento (OCR/PDF) | pdfplumber (local) / AWS Textract (aws) | `aws/adapters/cloud.py`, `pipelines/prescription/` |

**Justificativa da troca**: o ambiente de curso disponível é a AWS, que oferece o
conjunto gerenciado equivalente ao Azure para visão e documentos (Rekognition,
Textract). A troca é uma decisão consciente e documentada — a arquitetura por adapter
torna cada serviço substituível, e o modo local garante que qualquer pessoa reproduza
tudo sem nenhuma dependência de nuvem.

---

## 7. Limitações e trabalho futuro

Registradas com transparência (nada foi mascarado como "coberto" sem código real):

- **Oxigenação (SpO₂) e batimentos de UTI adulta**: o dataset BIDMC (HR/SpO₂ de UTI) já
  é baixado, mas o pipeline de vitais processa apenas o CTU-UHB (cardiotocografia
  fetal). A técnica de detecção de anomalia (z-score + Isolation Forest sobre janelas) é
  geral e se aplicaria ao BIDMC, mas o loader/features específicos ainda não foram
  escritos. **Batimentos** estão cobertos via FHR; **SpO₂** fica como trabalho futuro.
- **Pressão arterial**: sem fonte aberta em waveform sem credenciamento (a fonte
  identificada, VitalDB, fica como trabalho futuro).
- **Disartria (áudio)**: sem dataset aberto rotulado; deferido com justificativa.
- **Áudio de consulta real**: o caminho de transcrição/termos/sentimento/fadiga está
  validado estruturalmente (com áudio real do ICBHI, que não contém fala), mas ainda não
  foi exercitado ponta a ponta com uma gravação de consulta com fala real — pendente da
  gravação pelo grupo.
- **Inspeção visual do painel**: o dashboard foi validado por execução headless (zero
  exceções em toda a narrativa); uma revisão visual final no navegador é recomendada
  antes da gravação do vídeo.

Nenhuma dessas lacunas é bloqueadora: o enunciado trata "batimentos, pressão arterial,
oxigenação" como exemplos de um mesmo requisito (detecção de anomalia em série temporal
de sinais vitais), que está demonstrado com sinal real.

---

## 8. Como reproduzir

```bash
# 1. Ambiente
python3 -m venv .venv && source .venv/bin/activate && make install

# 2. Dados e modelo
make data
make models-fetch

# 3. Rodar as análises (produzem evidência real em output/) — modo local, sem nuvem
make demo                                                   # sinais vitais
PYTHONPATH=backend .venv/bin/python -m pipelines.video.cli --config <config>   # vídeo
PYTHONPATH=backend .venv/bin/python -m pipelines.audio.cli --config <config>   # áudio

# 4. Subir o painel (dois terminais)
make serve-api      # http://localhost:8000
make serve-front    # http://localhost:8501

# 5. Testes
make test
```

O painel abre no paciente-demo já configurado; o replay percorre a narrativa da seção 4,
com drill-down para a evidência real de cada evento.

---

## 9. Referências do repositório

| Documento | Conteúdo |
| --- | --- |
| [`README.md`](../README.md) | Visão geral, arquitetura e comandos |
| [`docs/8IADT-Fase-4-Tech-challenge.md`](8IADT-Fase-4-Tech-challenge.md) | Enunciado original do desafio |
| [`backend/README.md`](../backend/README.md) | Estrutura do backend |
| [`data/README.md`](../data/README.md) | Origem exata de cada dataset |
| [`models/README.md`](../models/README.md) | Proveniência do modelo treinado |
| [`training/README.md`](../training/README.md) | Passo a passo do treino do YOLOv8 |
| `.specs/STATE.md` | Decisões de arquitetura (AD-NNN) e estado do projeto |
| `.specs/features/<nome>/validation.md` | Relatórios de verificação por funcionalidade |
