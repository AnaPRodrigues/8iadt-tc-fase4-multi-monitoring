# F2 — Audio Analysis Specification

## Problem Statement

A equipe médica precisa identificar sinais de dificuldade respiratória e alterações vocais
(fadiga, termos clínicos críticos) em áudios de consulta sem ouvir cada gravação manualmente.
Assim como em F3, priorizamos dado real e rotulado onde existe: o ICBHI 2017 fornece anotação de
especialista para dificuldade respiratória (crackle/wheeze), permitindo métricas honestas de
precision/recall. Já a transcrição, termos críticos e qualidade vocal não têm dataset público
rotulado disponível no prazo, então usam 1–2 áudios de "consulta" gravados/atuados pelo próprio
grupo (não dado de paciente real).

## Goals

- [ ] Classificar dificuldade respiratória (crackle/wheeze/normal) sobre o ICBHI 2017, com métricas contra o rótulo real de especialista.
- [ ] Transcrever áudio de consulta (pt-BR) localmente via faster-whisper e identificar termos críticos configuráveis + sentimento.
- [ ] Calcular um score heurístico de qualidade vocal/fadiga via features acústicas (jitter, shimmer, HNR, pausas).
- [ ] Produzir evidência reproduzível para cada anomalia/termo detectado, consumível pela fusão (F5).

## Out of Scope

| Feature | Reason |
| --- | --- |
| Detecção de disartria real (datasets TORGO/UA-Speech) | AD-020: fora do caminho crítico de 7 dias; documentada como trabalho futuro no relatório |
| Fine-tuning/treinamento de modelo de fala próprio | Usa faster-whisper pré-treinado "as-is"; nenhum treinamento de ASR customizado |
| Diarização de falantes (quem fala o quê) | Não exigido pelo roteiro da demo (AD-008) |
| Suporte a outros idiomas além de pt-BR | Gray area já respondida no brief: código, docs e Whisper configurados só para pt-BR |
| Validação clínica do score de fadiga vocal | Heurística documentada e justificada no relatório, não validada clinicamente (sem dataset rotulado de fadiga) |
| Integração direta com AWS (S3/Lambda/SNS) | Papel de F2 é gerar evidência local; envio à nuvem e alerta são responsabilidade de F5 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Rigor de métricas por sub-pipeline | P1 (ICBHI) tem precision/recall/F1 contra rótulo real; P2/P3 (áudio gravado pelo grupo) não têm ground truth externo — avaliação qualitativa (termos/critérios conhecidos incluídos deliberadamente no roteiro de gravação) | Não existe dataset público rotulado de termos críticos/fadiga vocal em pt-BR no prazo; documentar essa diferença de rigor no relatório evita superestimar a confiabilidade de P2/P3 | y |
| Subconjunto do ICBHI usado na demo | Amostra curada do dataset (não as 6898 ocorrências completas), suficiente para treinar/avaliar o classificador leve em CPU dentro do prazo | 5,5h de áudio anotado é mais do que o necessário para uma demo; processar tudo consome tempo desproporcional ao valor demonstrativo | y |
| Classificador respiratório | Modelo leve (ex.: regressão logística ou random forest sobre MFCC/features espectrais), CPU-only, sem deep learning treinado do zero | AD-012 (sem GPU); mantém consistência com "modelos leves" usados em outras features | n — escolha exata do algoritmo fica para o Design |
| Áudio de consulta gravado pelo grupo | 1–2 gravações curtas (1–3 min) roteirizadas para incluir deliberadamente termos críticos conhecidos e trechos neutros | Precisa ser reprodutível e permitir validar se o sistema identifica corretamente o que foi roteirizado (proxy de ground truth) | n — grupo define o roteiro exato das gravações |
| Lista padrão de termos críticos | Lista configurável (YAML/JSON) com termos citados no brief: "dor no peito", "falta de ar", "tontura" + termos adicionais definidos pelo grupo | Facilita ajuste sem editar código; termos-base já vêm do brief | y |
| Motor de sentimento local | Léxico pt-BR (ou modelo leve de classificação de polaridade) rodando em CPU, sem chamada a serviço de nuvem | AD-002/AD-003: Comprehend indisponível no Learner Lab; sentimento precisa ser 100% local | y |
| Fórmula/limiar do score de fadiga vocal | Combinação heurística de jitter, shimmer, HNR e taxa de pausas, com limiar calibrado empiricamente nos áudios do grupo e documentado no relatório | Sem dataset rotulado de fadiga vocal disponível; heurística é a opção viável dentro do prazo (AD-008) | y |

**Open questions:** none — todas resolvidas ou registradas acima. Os itens marcados "confirmed: n" são defaults propostos pelo agente/decisões operacionais do grupo, abertos a ajuste sem bloquear o avanço para Design.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Formato/duração mínima de áudio validados antes de extrair features; ciclo ICBHI sem anotação é excluído do cálculo de métricas — ver AUDIO-12, AUDIO-13 |
| Failure / partial-failure states | Áudio corrompido/formato não suportado é pulado com erro registrado, sem travar o lote — ver AUDIO-12; transcrição vazia/não confiável é sinalizada, não inventada — ver AUDIO-10 |
| Idempotency / retry / duplicate handling | Reprocessar o mesmo arquivo produz o mesmo transcript/score/classe (determinismo), com eventual não determinismo do modelo documentado se existir — ver AUDIO-14 |
| Auth boundaries & rate limits | N/A because F2 é um módulo local sem API exposta nem chamada externa autenticada |
| Concurrency / ordering | N/A because cada arquivo de áudio é processado de forma independente; não há requisito de ordenação entre arquivos (diferente de F3, que tem séries temporais contínuas) |
| Data lifecycle / expiry | N/A because artefatos de evidência são gerados por execução de demo acadêmica sem requisito de retenção/expiração |
| Observability | Cada arquivo processado registra classe/termos/score, detector de origem e se a extração foi bem-sucedida, consumível por F5 |
| External-dependency failure | N/A because o núcleo de detecção (whisper, librosa, classificador) roda localmente sem chamada externa; upload de evidência ao S3 (consumo por F5) deve tolerar falha de rede sem derrubar o processamento local |
| State-transition integrity | N/A because F2 não possui máquina de estados própria; a classificação verde/amarelo/vermelho pertence a F5 |

---

## User Stories

### P1: Classificação de dificuldade respiratória sobre ICBHI 2017 ⭐ MVP

**User Story**: Como integrante do grupo validando o pipeline, quero classificar ciclos
respiratórios do ICBHI 2017 (crackle/wheeze/normal) e medir a performance contra o rótulo real de
especialista, para provar detecção de dificuldade respiratória com métricas honestas antes de
integrar às demais fontes multimodais.

**Why P1**: Cobre a exigência obrigatória de "detectar alterações vocais indicativas de... dificuldades respiratórias" do enunciado, com o único sub-pipeline de F2 que tem rótulo real — mais defensável no relatório.

**Acceptance Criteria**:

1. WHEN um ciclo respiratório anotado do ICBHI 2017 é carregado THEN o sistema SHALL extrair features espectrais/MFCC via librosa e a anotação real (crackle/wheeze/normal) associada.
2. WHEN as features de um subconjunto de ciclos são extraídas THEN o sistema SHALL treinar (ou carregar previamente treinado) um classificador leve em CPU para prever a classe respiratória.
3. WHEN o classificador processa um ciclo do conjunto de teste THEN o sistema SHALL retornar a classe prevista e um score de confiança.
4. WHEN as previsões do conjunto de teste são comparadas às anotações reais THEN o sistema SHALL calcular precision, recall e F1 por classe, salvos em relatório de métricas.
5. WHEN uma classe anômala (crackle ou wheeze) é prevista THEN o sistema SHALL gerar evidência reproduzível: espectrograma do ciclo + metadados (ID do registro, classe prevista, classe real, score).

**Independent Test**: Treinar/avaliar sobre o subconjunto curado do ICBHI e verificar que (a) o relatório de precision/recall/F1 por classe é gerado, e (b) existe evidência (espectrograma + metadados) para cada ciclo anômalo previsto.

---

### P2: Transcrição, termos críticos e sentimento sobre áudio de consulta

**User Story**: Como integrante do grupo, quero transcrever um áudio de consulta gravado pelo
grupo (pt-BR) localmente, identificar termos clínicos críticos e o sentimento geral, para cobrir a
exigência de "identificar termos críticos e sentimentos" sem depender de serviço de nuvem indisponível.

**Why P2**: Cobre a exigência obrigatória de identificação de termos críticos/sentimento; é
necessário para o fluxo de alerta em F5, mas depende de áudio atuado (menor rigor que P1).

**Acceptance Criteria**:

1. WHEN um áudio de consulta gravado pelo grupo (pt-BR) é processado pelo faster-whisper THEN o sistema SHALL gerar um transcript em texto.
2. WHEN o transcript é gerado THEN o sistema SHALL buscar pela lista configurável de termos críticos e destacar cada ocorrência com o trecho de contexto.
3. WHEN o transcript é gerado THEN o sistema SHALL calcular um sentimento (positivo/negativo/neutro) usando um motor local (léxico pt-BR ou modelo leve), sem chamada a serviço de nuvem.
4. WHEN um termo crítico é encontrado THEN o sistema SHALL gerar evidência reproduzível: transcript com o termo destacado + timestamp aproximado, quando disponível.
5. WHEN o áudio não produz transcrição inteligível (silêncio/ruído excessivo) THEN o sistema SHALL registrar "transcrição vazia/não confiável" em vez de reportar termos críticos falsos.

**Independent Test**: Processar 1–2 áudios roteirizados com termos críticos conhecidos e verificar que são identificados corretamente com evidência; processar um áudio silencioso e confirmar que o sistema reporta "não confiável" sem falso positivo de termo crítico.

---

### P3: Score de qualidade vocal (fadiga) via features acústicas

**User Story**: Como integrante do grupo, quero calcular um score heurístico de fadiga/qualidade
vocal a partir de features acústicas do áudio de consulta, para reforçar a exigência de "detectar
cansaço" do enunciado como evidência complementar.

**Why P3**: Enriquece a demo com um segundo tipo de sinal vocal, mas não é indispensável — a
exigência central de "dificuldade respiratória" já está coberta pelo P1 com rótulo real.

**Acceptance Criteria**:

1. WHEN o áudio de consulta é processado THEN o sistema SHALL extrair features acústicas: jitter, shimmer, HNR, taxa de pausas e velocidade de fala.
2. WHEN as features são combinadas THEN o sistema SHALL calcular um score heurístico de fadiga/qualidade vocal, com fórmula e limiar documentados e justificados no relatório técnico.
3. WHEN o score heurístico ultrapassa o limiar configurado THEN o sistema SHALL sinalizar "possível fadiga vocal" como evidência complementar, explicitamente marcada como heurística não validada clinicamente.

**Independent Test**: Comparar o score gerado entre um áudio "normal" e um áudio gravado deliberadamente com fala mais lenta/pausada, e confirmar que o segundo produz score de fadiga mais alto.

---

## Edge Cases

- WHEN um arquivo de áudio está corrompido ou em formato não suportado THEN o sistema SHALL registrar um erro claro e pular o arquivo, sem travar o processamento do restante do lote.
- WHEN a anotação do ICBHI está ausente para um ciclo THEN o sistema SHALL excluir aquele ciclo do cálculo de métricas, em vez de contá-lo como erro do classificador.
- WHEN o mesmo arquivo de áudio é processado duas vezes THEN o sistema SHALL produzir o mesmo transcript/score/classe; qualquer não determinismo interno do modelo SHALL ser documentado explicitamente no relatório.
- WHEN a lista de termos críticos está vazia ou não é fornecida THEN o sistema SHALL usar a lista padrão documentada em vez de falhar.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| AUDIO-01 | P1: Carga de ciclo ICBHI + extração de features | Tasks | ✅ Verified |
| AUDIO-02 | P1: Classificador respiratório leve (CPU) | Tasks | ✅ Verified |
| AUDIO-03 | P1: Predição de classe + score de confiança | Tasks | ✅ Verified |
| AUDIO-04 | P1: Métricas precision/recall/F1 por classe | Tasks | ✅ Verified |
| AUDIO-05 | P1: Evidência de classe anômala (espectrograma) | Tasks | ✅ Verified |
| AUDIO-06 | P2: Transcrição faster-whisper (pt-BR) | Tasks | ✅ Verified |
| AUDIO-07 | P2: Busca de termos críticos configuráveis | Tasks | ✅ Verified |
| AUDIO-08 | P2: Sentimento local (sem nuvem) | Tasks | ✅ Verified |
| AUDIO-09 | P2: Evidência de termo crítico | Tasks | ✅ Verified |
| AUDIO-10 | Edge: transcrição vazia/não confiável | Tasks | ✅ Verified |
| AUDIO-11 | P3: Features acústicas + score de fadiga vocal | Tasks | ✅ Verified (iteração 2 — Fix 3: evidência testada com 2 áudios reais; limitação de baseline com 1 áudio documentada em design.md como aceita) |
| AUDIO-12 | Edge: arquivo corrompido/formato não suportado | Tasks | ✅ Verified (iteração 2 — Fix 4: lado consult_audio_paths agora testado em integração) |
| AUDIO-13 | Edge: ciclo ICBHI sem anotação excluído das métricas | Tasks | ✅ Verified |
| AUDIO-14 | Edge: determinismo de reprocessamento | Tasks | ✅ Verified |

**ID format:** `AUDIO-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 14 total, 14 mapped to tasks (T1–T13, ver `tasks.md`), 0 unmapped — 14/14 Verified (validation.md, iteração 2, PASS)

---

## Success Criteria

- [ ] Classificador respiratório roda ponta a ponta sobre o subconjunto ICBHI com um único comando, produzindo métricas por classe sem intervenção manual.
- [ ] Precision, recall e F1 por classe (crackle/wheeze/normal) reportados no relatório técnico, contra rótulo real.
- [ ] Ao menos um áudio de consulta gravado pelo grupo processado com transcript, termos críticos e score de fadiga vocal gerados corretamente.
- [ ] Toda anomalia/termo crítico detectado tem evidência visual/textual correspondente na saída (critério de aceite global do projeto).
