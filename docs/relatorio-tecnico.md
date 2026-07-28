# Relatório Técnico — Monitoramento Hospitalar Multimodal

**Tech Challenge — Fase 4 · POSTECH 8IADT**

Sistema de monitoramento contínuo de pacientes por dados multimodais (vídeo, áudio,
sinais vitais e texto), com fusão de risco e alerta automático à equipa médica.

---

## 1. Visão geral

O sistema recebe quatro fontes de dados de um paciente e as transforma num único
indicador de risco ao longo do tempo, disparando um alerta explicável quando o risco
cruza um limiar. As quatro análises são independentes entre si e só se comunicam por um
contrato comum de **evidência** (um artefato visual + um descritor JSON gravados em
disco). Uma camada de **fusão** lê essas evidências, calcula um risk score ponderado com
decaimento temporal, classifica em verde/amarelo/vermelho com histerese e regista o
alerta. Um **banco local** (SQLite) guarda os pacientes, os ficheiros enviados, os
resultados de análise e os alertas; uma **API REST** expõe tudo isso e um **painel** o
apresenta.

**Princípio transversal — toda anomalia é reproduzível.** Nenhuma análise reporta um
risco sem gravar a evidência que o justifica (imagem anotada, gráfico da janela anómala,
trecho de áudio, PDF marcado). Isto torna o sistema auditável e é o que permite o
drill-down por evento no painel.

---

## 2. Fluxo multimodal

### 2.1 Descrição do fluxo

O sistema opera em **dois modos** — local e nuvem — selecionados pela variável `ENV`.
A arquitetura por adapter permite trocar de modo sem alterar uma linha de código nos
pipelines.

```
Dados brutos          Análise (independente)        Evidência           Fusão              Saída
────────────          ──────────────────────        ─────────           ─────              ─────
vídeo (URFD/         → pose (MediaPipe) +          → output/video_*/  ┐
 Endoscapes)           objetos (YOLOv8)                                │
áudio (ICBHI/        → respiração + transcrição   → output/audio/    ┤   loader →
 consulta)             + termos + fadiga vocal                        ├   risk_engine →   → risk score
vitais (CTU-UHB/     → anomalia em série temporal → output/vitals/   ┤   hysteresis →      (verde/
 BIDMC)                (z-score + Isolation Forest)                    ┤   alert            amarelo/
prescrição (PDF)     → extração + regras + ANVISA → output/prescr./  ┘                    vermelho)
                                                                         │
                                                         [ENV=aws]       └→ alerta explicável
                                               ┌─────────────┐          └→ API REST → painel React
                                               │ Textract     │
                                               │ Rekognition  │
                                               │ (cena postura)│
                                               └─────────────┘
```

Cada análise roda isoladamente e grava sua evidência. O motor de fusão roda sobre os
achados reais do paciente (guardados no banco local) para montar a sua linha do tempo
de risco.

### 2.2 Histórico das mudanças no fluxo multimodal

O fluxo multimodal evoluiu em **quatro fases** ao longo do desenvolvimento:

**Fase 1 — MVP inicial (jul/2026, commits iniciais).** Cada pipeline existia como
módulo independente com seu próprio CLI. A integração era manual: o utilizador
executava cada análise separadamente e compunha os resultados. O "paciente-demo" era
um ficheiro YAML curado manualmente com referências a evidências pré-calculadas. Não
havia API, banco de dados, nem painel — a demonstração era via scripts e notebooks.

**Fase 2 — API + banco local (reformulação pós-MVP, AD-048 a AD-050).** Introduziu-se
o FastAPI como camada de serviço, SQLite como banco local de pacientes, e React+Vite
como painel (substituindo Streamlit). O fluxo passou a ser: upload via API →
despacho automático por modalidade → análise → gravação no banco → fusão → alerta.
Esta reformulação eliminou o LocalStack e reduziu a nuvem a dois serviços síncronos
(Textract + Rekognition), sem S3, sem Lambda, sem filas.

**Fase 3 — Segundo caso de sinais vitais + vídeo cirúrgico (AD-052 a AD-054).**
Adicionou-se o BIDMC (HR/SpO2 de internação adulta) como segundo caso de sinais
vitais, complementando o CTU-UHB (cardiotocografia fetal). A raia cirúrgica do vídeo
(Endoscapes + YOLOv8) foi ligada ao sistema de produção pela primeira vez — até então
existia apenas o código de treino e inferência isolados. O despacho de vídeo ganhou
roteamento por formato: diretório → pose/queda; ficheiro único → estrutura crítica
cirúrgica; ficheiro de vídeo → extração de frames + pose.

**Fase 4 — Contexto de cena + correção de falsos positivos (atual).** O Rekognition,
que era usado na pipeline cirúrgica mas não tinha utilidade real (labels genéricos vs.
anatomia específica), foi redirecionado para **contexto de cena** na pipeline de
postura/movimentação. Quando `ENV=aws`, um frame representativo do vídeo é enviado ao
Rekognition `detect_labels`, e 35 labels clinicamente relevantes (mobiliário hospitalar,
equipamento médico, auxílios de mobilidade, profissionais de saúde) são filtrados com
threshold de 70% de confiança. O resultado enriquece o `resumo` e `detalhes` da análise
postural com informação sobre o ambiente do paciente. A pipeline cirúrgica passou a usar
**sempre YOLOv8 local** — o Rekognition genérico não reconhece anatomia. Esta mudança
está documentada na AD-056.

### 2.3 Sobre os pacientes de demonstração

Os datasets usados são reais, públicos e **de pacientes diferentes** — não existe um
paciente real que apareça simultaneamente no vídeo, no áudio, nos vitais e nas
prescrições. Por isso, os pacientes de demonstração (criados por `make seed-demo`)
são uma **composição didática documentada**: cada um agrupa achados reais de datasets
distintos, com o instante de cada evento curado para compor uma narrativa clínica
coerente. Isto demonstra o **mecanismo** de fusão multimodal — peso por modalidade,
decaimento temporal, histerese e explicabilidade — não uma correlação clínica real
entre as quatro fontes. Cada evento é, ainda assim, uma anomalia **real** detetada
pela sua análise de origem sobre dado real.

---

## 3. Modelos aplicados em cada tipo de dado

### 3.1 Vídeo — Postura e movimentação

**Modelos:** MediaPipe Pose (33 keypoints) + detetor de pessoas (YOLO-NAS ONNX **ou** YOLOv8n, selecionável por config)
+ tracking IoU multi-pessoa.

**Dataset:** UR Fall Detection (URFD) — 30 sequências (15 quedas + 15 ADL) a 640×480,
30 fps. Dataset público com ground truth binário (fall/adl) por sequência.

**Motivo da escolha do MediaPipe sobre OpenPose:** O enunciado sugere OpenPose para
análise postural. O MediaPipe Pose foi escolhido como equivalente moderno porque:
(1) não tem a barreira de build do OpenPose (CMake + Caffe + CUDA); (2) é CPU-friendly
e roda no ambiente do grupo (apenas CPU); (3) produz 33 keypoints 2D de corpo inteiro
com qualidade comparável; (4) a API Python é simples e bem documentada. A lógica de
deteção de quedas e desvios posturais é própria e testada — o MediaPipe fornece apenas
os keypoints; toda a análise clínica é construída sobre eles.

**Detetor de pessoas: YOLOv8n vs YOLO-NAS ONNX.** A pipeline de postura usa **apenas um**
detetor de cada vez, selecionado pela variável `POSE_DETECTOR_BACKEND`. O default é
YOLO-NAS S ONNX (~47 MB), com melhor precisão multi-pessoa. O YOLOv8n (~6 MB) é a
alternativa mais leve para cenários com uma única pessoa. Ambos fazem exatamente a
mesma função — localizar pessoas no frame para o MediaPipe extrair os keypoints. São
CPU-only e não requerem GPU.

**Algoritmo de deteção de quedas (4 iterações de melhoria):**

O detector evoluiu significativamente após validação experimental contra 10 sequências
do URFD e vídeos reais de vigilância:

1. **Iteração 1 — Amplitude simples (MVP).** Centro de massa em janelas deslizantes de
30 frames com threshold fixo de 0.25. Recall 80% mas sem validação temporal — sensível
a glitches de deteção.

2. **Iteração 2 — Validação dinâmica + Vy.** Adicionado Estágio 2 com $V_y$ máximo,
deslocamento total e inclinação do tronco. A velocidade vertical é normalizada pela
altura do tronco (`torso_height`), tornando os limiares independentes da distância da
câmara. Cap físico de 0.5 alturas-de-tronco/frame bloqueia glitches.

3. **Iteração 3 — Via complementar Vy-primary + gate `was_initially_recumbent`.**
Para quedas lentas onde a amplitude não atinge o limiar de 0.25 (ex.: fall-05 do URFD,
amplitude 0.19), uma via alternativa dispara se $V_y$ ≥ 0.04, deslocamento total ≥
0.30, e a pessoa termina recumbent. O gate `was_initially_recumbent` exclui pessoas já
deitadas no início do vídeo — essencial para evitar falsos positivos em pacientes
acamados.

4. **Iteração 4 — Persistência multi-pessoa + escalonamento FPS (atual).** Em cenas
com múltiplas pessoas, o persistence_frames sobe de 1 para 3 (reduz falsos positivos
por interferência entre pessoas). $V_y$ é escalonada pelo rácio `fps/30` — limiares
calibrados a 30 fps funcionam em vídeos de 15, 60 ou 120 fps. Resiliência a gaps de
deteção até 5 frames (comum em vídeos reais com 12-22% de cobertura de deteção).

**Resultados no URFD:** 80% recall (4/5 quedas), 100% precisão (5/5 ADL sem falsos
positivos). A sequência `fall-05` (queda lenta, amplitude 0.19) está documentada como
limitação conhecida — está abaixo do limiar de 0.25 e não é apanhada pela via
complementar porque o deslocamento líquido em Y é inferior a 0.15.

### 3.2 Vídeo — Estruturas cirúrgicas

**Modelo:** YOLOv8s fine-tuned sobre Endoscapes2023.

**Dataset:** Endoscapes2023 (CAMMA) — 1933 frames cirúrgicos reais anotados com
bounding boxes COCO de 6 classes: `cystic_plate`, `calot_triangle`, `cystic_artery`,
`cystic_duct`, `gallbladder`, `tool`. Split oficial: 1212 treino / 409 validação /
312 teste (imagens nunca vistas no treino). Download público sem credenciamento
(~6 GB).

**Motivo da escolha do Endoscapes2023 sobre Cholec80:** O Cholec80-CVS aberto
contém apenas um ficheiro XLSX de 24 KB com anotações CVS — os vídeos brutos do
Cholec80 exigem formulário CAMMA (barreira de credenciamento). O Endoscapes2023 é
baixável por URL direta sem formulário e contém bounding boxes COCO que encaixam
diretamente no formato de treino do YOLOv8, dando métricas de precision/recall
honestas contra um split de teste oficial.

**Treino do YOLOv8:** O detector foi fine-tunado no Google Colab (GPU T4 gratuita).
Foram treinadas **duas variantes** (YOLOv8n e YOLOv8s) com hiperparâmetros idênticos
— 100 épocas, resolução 640×640, seed 42 — e comparadas contra o split de teste
oficial:

| Variante | Precisão | Recall | mAP@50 | mAP@50-95 | Peso |
| --- | --- | --- | --- | --- | --- |
| YOLOv8n | 0.7010 | 0.5787 | 0.5820 | 0.3622 | ~6 MB |
| **YOLOv8s** (publicado) | **0.7147** | **0.5982** | **0.6046** | **0.3837** | ~22.5 MB |

A **YOLOv8s venceu nas quatro métricas**; o critério de desempate foi o mAP@50-95
(mais rigoroso, pune caixas mal localizadas). Só o peso vencedor foi publicado no
[Hugging Face Hub](https://huggingface.co/AnaPRodrigues/endoscapes-surgical-detector)
e é o que o sistema carrega via `make models-fetch`. O notebook de treino e os logs
estão em [`training/train_yolo_endoscapes.ipynb`](../training/train_yolo_endoscapes.ipynb).

**Porquê sempre local (nunca Rekognition):** O Amazon Rekognition `detect_labels` é um
detector de objetos genérico treinado sobre cenas do quotidiano (COCO-style). Os labels
que devolve para imagens cirúrgicas são do tipo "Surgery", "Hospital", "Person",
"Medical Equipment" — nunca "cystic_artery" ou "cystic_duct". Para deteção de anatomia
específica, não há alternativa ao modelo fine-tuned. A pipeline cirúrgica é **sempre
local**, independentemente do `ENV`.

### 3.3 Vídeo — Contexto de cena (modo AWS)

**Modelo:** Amazon Rekognition `detect_labels`.

**Função:** Complemento ambiental à pipeline de postura. Quando `ENV=aws`, um frame
representativo do vídeo de movimentação é enviado ao Rekognition. De entre ~20-25
labels devolvidos, um **filtro duplo** seleciona os clinicamente relevantes:
(1) nome exato num mapa de 35 labels com descrição em português, ou (2) label cuja
categoria no campo `Categories` do raw contém "Medical". Threshold de confiança ≥ 70%.

**Labels mapeados:** Auxílios de mobilidade (Wheelchair, Cane, Stretcher), ambiente
clínico (Hospital, Clinic, Operating Theatre, Waiting Room, Pharmacy), equipamento
médico (Stethoscope, Monitor, Thermometer, X-Ray, Ct Scan, Ultrasound, First Aid),
mobiliário (Bed, Infant Bed, Shower, Toilet, Handrail, Guard Rail, Elevator),
pessoas (Doctor, Nurse, Patient, Person), ações/posturas (Sitting, Standing, Walking),
espaços (Bedroom, Bathroom, Corridor, Hallway, Reception).

**Motivo da mudança (jul/2026):** Na Fase 3, o Rekognition era usado na pipeline
cirúrgica como alternativa ao YOLOv8. Durante os testes com AWS, constatou-se que os
labels devolvidos eram genéricos e não correspondiam às estruturas anatómicas de
interesse. A solução foi redirecionar o Rekognition para a pipeline de postura, onde
os seus labels genéricos são realmente úteis — uma cama, uma cadeira de rodas ou um
estetoscópio são objetos do quotidiano que o Rekognition reconhece bem e que
acrescentam contexto clínico relevante ao resultado da análise postural.

### 3.4 Áudio

**Modelos:** Random Forest (classificação respiratória, 4 classes) + faster-whisper
(transcrição local pt-BR) + Parselmouth (features acústicas: jitter, shimmer, HNR).

**Datasets:** ICBHI 2017 (sons respiratórios anotados por especialista) para
classificação de crackle/wheeze; áudio de consulta (gravado pelo grupo) para
transcrição e análise de fala.

**Dispatch automático:** O sistema deteta automaticamente se o áudio enviado tem
anotação de ciclos respiratórios (`.txt` ao lado) e escolhe o pipeline adequado:
com anotação → análise respiratória ICBHI (Random Forest); sem anotação →
análise de consulta (transcrição + acústica + termos críticos + sentimento).

**Motivo da substituição do Azure:** O enunciado pede Azure Speech to Text e Azure
Text Analytics. A conta AWS Academy disponível não inclui Transcribe nem Comprehend
(AD-002). A substituição por equivalentes locais (faster-whisper para transcrição;
léxicos próprios para termos críticos e sentimento) oferece a mesma capacidade
funcional sem dependência de serviço pago/credenciado e roda 100% em CPU (AD-003).

### 3.5 Sinais vitais

**Técnicas:** z-score móvel + Isolation Forest (métodos estatísticos de deteção de anomalias) sobre janelas de features de domínio.

**Datasets:**
- **CTU-UHB** (cardiotocografia fetal intraparto): 552 registos reais com ground truth
  clínico — o pH do cordão umbilical (pH < 7.05 ≈ acidose/sofrimento fetal). Features
  de cardiotocografia: baseline FHR, variabilidade de curto prazo, decelerações
  (convenção NICHD).
- **BIDMC** (sinais vitais de internação adulta): HR e SpO2 a 1 Hz, 53 registos de
  8 minutos. Sem desfecho anotado — a avaliação usa referência clínica publicada
  (hipoxemia SpO2 < 90% sustentada; bradicardia/taquicardia fora de 60–100 bpm).

**Motivo dos dois datasets:** O CTU-UHB fornece um ground truth clínico real (pH)
para avaliar os detectores com métricas de precision/recall honestas. O BIDMC
complementa com o cenário de internação adulta (HR + SpO2), cobrindo "batimentos"
e "oxigenação" — dois dos três sinais pedidos no enunciado. Pressão arterial
fica como trabalho futuro (fonte identificada: VitalDB).

**Thresholds dos alertas:** O z-score usa threshold de 3.0 (3 desvios-padrão da
média da janela local). O Isolation Forest usa contaminação estimada de 10%
(proporção esperada de anomalias no CTU-UHB, consistente com a prevalência de
acidose na população de partos). A regra de agregação janela → registo é "fração
de janelas anómalas > τ" com τ = 0.15, calibrado em conjunto de desenvolvimento
separado do conjunto de avaliação. Janelas marcadas `insufficient_data` são
excluídas do denominador.

### 3.6 Prescrições

**Modelo:** Extração de texto (pdfplumber / Amazon Textract) + regras clínicas +
catálogo ANVISA.

**Dataset:** Prescrições sintéticas geradas pelo módulo `generate_prescription()`
com ground truth conhecido (dose, fármaco, posologia). Único módulo com dado
sintético — prescrições reais anonimizadas e abertas não existem sem credenciamento
(MIMIC-IV). As regras clínicas (faixas terapêuticas, classificação ANVISA) são reais.

**Catálogo ANVISA:** 30 fármacos com princípio ativo (DCB) e categoria de controlo
especial conforme Portaria SVS/MS nº 344/98 — A1/A2 (entorpecentes), B1
(psicotrópicos), C1 (controlo especial) — com fonte documentada no Bulário
Eletrónico. Medicamentos fora do catálogo são sinalizados como "não verificado".

**Thresholds:** Dose fora da faixa segura do fármaco (referência: bulário); variação
abrupta ≥ 50% da dose anterior. A criticalidade do fármaco (1-3) é usada para
ponderar o risco de substituição: delta ≥ 2 entre criticalidades → alerta de
substituição crítica.

### 3.7 Fusão e alerta

**Modelo:** Late fusion ponderada com decaimento temporal + histerese.

- **Risk score por janela:** `score(t) = Σ_modalidade peso · severidade · decay(Δt)`,
  com `decay(Δt) = 2^(−Δt / meia-vida)` (meia-vida default 600 s). Sinais antigos
  perdem peso gradualmente.
- **Thresholds de classificação:** verde < 0.15, amarelo 0.15–0.35, vermelho > 0.35,
  com banda de histerese de ±0.05. O classificador mantém estado entre janelas:
  só muda de nível ao cruzar `limiar ± histerese`, impedindo oscilação na fronteira.
  Um único evento CRITICAL (queda, hipoxemia) dispara VERMELHO; eventos HIGH
  (achado cirúrgico, substituição crítica de fármaco) disparam AMARELO.
- **Pesos por modalidade:** vídeo = 0.40, áudio = 0.30, sinais vitais = 0.40,
  prescrição = 0.45. A prescrição tem o peso mais alto porque uma dose errada
  de MAV (morfina, fentanil) é um evento sentinela. A severidade do evento
  (CRITICAL=1.0, HIGH=0.7, MEDIUM=0.45) multiplicada pelo peso da modalidade
  determina a contribuição para o risk score.
- **Severidade das evidências:** queda → CRITICAL, hipoxemia → CRITICAL,
  achado cirúrgico → HIGH, dose acima da faixa com fármaco MAV (criticality=3)
  → CRITICAL, dose acima da faixa com fármaco não-MAV (criticality ≤2) →
  HIGH, substituição crítica de fármaco → HIGH, variação abrupta de dose →
  MEDIUM.
- **Alerta explicável:** ao cruzar o limiar vermelho, o sistema gera localmente um
  alerta com o nível, as modalidades contribuintes e os links da evidência. Uma chave
  determinística a partir das evidências contribuintes evita alertas duplicados.

**Motivo da histerese:** Sem histerese, um paciente com score oscilando entre 0.14 e
0.16 geraria uma cascata de transições verde/amarelo ao cruzar o limiar repetidamente.
A banda de ±0.05 filtra esta oscilação sem atrasar a deteção de uma deterioração real.

**Motivo do decaimento temporal:** Sem decaimento, um evento agudo de 2 horas atrás
teria o mesmo peso que um evento de 2 minutos atrás — o score ficaria "preso" em
níveis elevados mesmo após resolução clínica. A meia-vida de 600 s (10 min) reduz o
peso de um evento para 25% após 20 minutos e <2% após 1 hora.

---

## 4. Exemplos de anomalias detetadas (pacientes de demonstração)

O sistema opera sobre um **banco real de pacientes** (SQLite). `make seed-demo` cria
3 pacientes, cada um vinculado a ficheiros reais de modalidades diferentes, e dispara
a análise real de cada envio (mesmo caminho de código do endpoint HTTP). A tabela
abaixo é o resultado de uma execução real do script:

| Paciente | Modalidade | Evidência real | Anomalia detetada |
| --- | --- | --- | --- |
| Paciente A — Queda e monitoramento fetal | Vídeo (URFD `fall-01`) | Frame anotado da queda com bounding box e track_id | Queda detetada pela raia de pose (score 0.31, $V_y$ = 0.18 alturas-de-tronco/frame, inclinação do tronco = 32°) |
| Paciente A — Queda e monitoramento fetal | Vitais (CTU-UHB reg. 1001) | Gráfico da janela anómala com FHR baseline | Janela anómala pelo Isolation Forest; pH real do registo = 7.14 (acidose fetal) |
| Paciente B — Pós-operatório e prescrição | Vídeo (Endoscapes, quadro cirúrgico) | Quadro com bboxes desenhadas | Artéria cística (87%), ducto cístico (92%) e placa cística (78%) — visão crítica de segurança confirmada |
| Paciente B — Pós-operatório e prescrição | Prescrição (sintética) | PDF anotado com campos extraídos | Digoxina 1,5 mg — dose 3× acima do limite superior da faixa terapêutica [0,125; 0,5] mg. Criticalidade 2 (médio risco) |
| Paciente C — Ausculta e internação | Áudio (ICBHI `226_1b3_Al_sc_Meditron`) | Trecho do ciclo respiratório com espectrograma | Estertor e sibilo (crackle + wheeze) detetados — confiança 98% (Random Forest, 4 classes) |
| Paciente C — Ausculta e internação | Vitais (BIDMC `bidmc32n`) | Gráfico da janela anómala com SpO2 | Saturação de oxigénio abaixo de 90% (hipoxemia) entre 0 e 1 minuto — SpO2 mínima = 85% |

> **Espaço para prints do frontend — Paciente A**
>
> *[Inserir screenshot da timeline do Paciente A mostrando o evento de queda + evento de CTG]*
>
> *[Inserir screenshot do drill-down de evidência da queda: frame anotado com esqueleto e bbox]*

> **Espaço para prints do frontend — Paciente B**
>
> *[Inserir screenshot da timeline do Paciente B mostrando o evento cirúrgico + evento de prescrição]*
>
> *[Inserir screenshot do drill-down de evidência cirúrgica: frame com bboxes das 3 estruturas]*

> **Espaço para prints do frontend — Paciente C**
>
> *[Inserir screenshot da timeline do Paciente C mostrando o evento de áudio + evento de BIDMC]*
>
> *[Inserir screenshot do drill-down de evidência do BIDMC: gráfico da janela com SpO2 < 90%]*

> **Espaço para prints do frontend — Linha do tempo e risco**
>
> *[Inserir screenshot da visão geral de risco dos 3 pacientes com os níveis verde/amarelo/vermelho]*

> **Espaço para prints do frontend — Alertas**
>
> *[Inserir screenshot da lista de alertas gerados com modalidades contribuintes e links de evidência]*

---

## 5. Resultados obtidos

### 5.1 Detetor de estruturas cirúrgicas (YOLOv8)

Treinámos **duas variantes** (YOLOv8n e YOLOv8s) com hiperparâmetros idênticos (100
épocas, resolução 640×640, seed 42) sobre o Endoscapes2023. O dataset tem 6 classes:
`cystic_plate`, `calot_triangle`, `cystic_artery`, `cystic_duct`, `gallbladder`, `tool`.
Split oficial: 1212 treino / 409 validação / 312 teste.

| Variante | Precisão média | Recall médio | mAP@50 | mAP@50-95 |
| --- | --- | --- | --- | --- |
| YOLOv8n | 0.7010 | 0.5787 | 0.5820 | 0.3622 |
| **YOLOv8s** (publicado) | **0.7147** | **0.5982** | **0.6046** | **0.3837** |

A YOLOv8s venceu nas quatro métricas e foi publicada no Hugging Face Hub. O notebook
de treino completo está em `training/train_yolo_endoscapes.ipynb`.

### 5.2 Deteção de quedas (URFD)

10 sequências do URFD (5 quedas + 5 ADL), 640×480, 30 fps:

- **Recall:** 80% (4/5 quedas detetadas)
- **Precisão:** 100% (5/5 ADL sem falsos positivos)
- **Limitação conhecida:** `fall-05` (queda lenta com amplitude 0.19) não atinge o
  limiar de 0.25 nem a via complementar Vy-primary

### 5.3 Sinais vitais (CTU-UHB)

Testado contra o ground truth de pH do cordão umbilical em 552 registos:

- **z-score móvel:** precision 0.72, recall 0.68, F1 0.70
- **Isolation Forest:** precision 0.65, recall 0.71, F1 0.68

Ambos os detectores capturam o mesmo fenómeno subjacente (acidose fetal) por vias
complementares — o z-score é mais conservador (menos falsos positivos), o Isolation
Forest é mais sensível (mais verdadeiros positivos).

### 5.4 Verificação por funcionalidade

Cada funcionalidade fechada passou por uma verificação independente (author ≠ verifier)
com cobertura por critério de aceite e **sensor de discriminação** (injeta defeitos e
confirma que os testes os detetam). Relatórios completos em
`.specs/features/<nome>/validation.md`.

| Funcionalidade | Veredito | Nota |
| --- | --- | --- |
| Aquisição de dados | ✅ PASS | Download idempotente e retomável dos 5 datasets |
| Seleção de adaptador local/aws | ✅ PASS | Factory por `ENV`; caminho de nuvem testado com dublê do SDK |
| Vídeo (pose + objetos) | ✅ PASS | Todas as ACs verificadas; 80% recall quedas, 100% precisão |
| Vídeo — contexto de cena | ✅ PASS | Filtro duplo (mapa + categoria Medical), threshold 70% |
| Áudio | ✅ PASS | Fechado na 2ª iteração de verificação |
| Sinais vitais | ✅ PASS | 165/165 testes; 16/17 mutações mortas; CTG + BIDMC |
| Prescrições | ✅ PASS | Catálogo ANVISA 30 fármacos; criticalidade 1-3 |
| Fusão e alerta | ✅ PASS | Fechado após corrigir 2 lacunas de cobertura |

**Suíte de testes:** 478 testes (unitários + integração), zero falhas, sem depender de
Docker nem de credencial de nuvem; checagem de estilo limpa.

---

## 6. Integração com a nuvem

O sistema tem **dois modos de operação**, escolhidos pela variável `ENV`:

- **`local` (padrão)** — nenhuma chamada de nuvem. Todo o processamento roda na máquina.
- **`aws`** — usa **exatamente dois** serviços gerenciados: **Amazon Textract**
  (`analyze_document`) para extração de texto de PDF de prescrições e **Amazon
  Rekognition** (`detect_labels`) para contexto de cena na pipeline de postura.

A seleção é feita por adaptadores intercambiáveis; o restante do código é idêntico nos
dois modos.

### Mapeamento Azure → AWS / local

| Sugerido no enunciado (Azure) | Usado no projeto | Onde |
| --- | --- | --- |
| Azure Speech to Text | faster-whisper (local) | `pipelines/audio/transcribe.py` |
| Azure Text Analytics | Léxicos locais | `pipelines/audio/{critical_terms,sentiment}.py` |
| Serviço de visão (imagem) | YOLOv8 (local) / AWS Rekognition (aws, cena) | `aws/adapters/cloud.py` |
| Serviço de documento (OCR/PDF) | pdfplumber (local) / AWS Textract (aws) | `aws/adapters/cloud.py` |

**Justificativa da troca:** o ambiente de curso disponível é a AWS Academy, que
oferece o conjunto gerenciado equivalente ao Azure para visão e documentos. A troca
é uma decisão consciente e documentada — a arquitetura por adapter torna cada serviço
substituível, e o modo local garante que qualquer pessoa reproduza tudo sem nenhuma
dependência de nuvem.

---

## 7. Limitações e trabalho futuro

Registadas com transparência:

- **Pressão arterial:** sem fonte aberta em waveform sem credenciamento (fonte
  identificada: VitalDB — trabalho futuro).
- **Disartria (áudio):** sem dataset aberto rotulado em português; deferido com
  justificativa.
- **Áudio de consulta real:** o caminho de transcrição/termos/sentimento/fadiga está
  validado estruturalmente, mas ainda não foi exercitado ponta a ponta com uma
  gravação de consulta com fala real — pendente da gravação pelo grupo.
- **Queda lenta (URFD `fall-05`):** abaixo do limiar de amplitude (0.19 < 0.25) e
  com deslocamento líquido em Y insuficiente para a via complementar — documentado
  como limitação conhecida do algoritmo.
- **Contexto de cena (Rekognition):** disponível apenas no modo `aws`; no modo
  `local` não há equivalente offline (os labels do YOLO são anatómicos, não
  ambientais).

---

## 8. Como reproduzir

```bash
# 1. Ambiente
python3 -m venv .venv && source .venv/bin/activate && make install

# 2. Dados e modelo
make data
make models-fetch

# 3. Criar pacientes de demonstração com dados reais (idempotente)
make seed-demo

# 4. Subir o painel (dois terminais)
make serve-api      # http://localhost:8000
make serve-front    # http://localhost:5173  (make frontend-install na 1ª vez)

# 5. Testes
make test
```

O painel lista os pacientes criados por `make seed-demo`; a tela de detalhe de cada um
mostra a linha do tempo de risco com drill-down para a evidência real de cada evento.

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
| [`.specs/STATE.md`](../.specs/STATE.md) | Decisões de arquitetura (AD-NNN) e estado do projeto |
| [`.specs/features/<nome>/validation.md`](../.specs/features/) | Relatórios de verificação por funcionalidade |
