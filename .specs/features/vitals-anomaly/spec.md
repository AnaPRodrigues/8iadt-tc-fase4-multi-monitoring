# F3 — Vitals Anomaly Detection Specification

## Problem Statement

A equipe médica precisa identificar precocemente sinais de risco em sinais vitais sem depender de
revisão manual contínua. Este módulo prova, com dados clínicos reais e ground truth real (não
injetado), que um pipeline local de detecção de anomalias em séries temporais funciona antes de
ser integrado às demais fontes multimodais (vídeo, áudio, prescrições) na fusão final (F5). É a
primeira fatia do plano de 7 dias porque destrava a lógica de fusão e é o "coração" da história
demonstrada no vídeo.

## Goals

- [ ] Carregar registros reais do CTU-UHB Intrapartum CTG (FHR + contração uterina) com o pH do cordão umbilical como rótulo clínico real de anomalia (não injetado).
- [ ] Detectar anomalias com dois métodos (rolling z-score + IsolationForest) e medir precision/recall/F1 contra o rótulo pH real.
- [ ] Compor uma timeline de demo concatenando registros CTU-UHB reais (ex.: normal → patológico) para simular deterioração ao longo da internação, mantendo o dado 100% real.
- [ ] Incluir opcionalmente o MIT-BIH Arrhythmia (ECG anotado) como segundo caso de série vital.
- [ ] Produzir evidência reproduzível (gráfico + metadados) para cada anomalia detectada, consumível pela fusão (F5).

## Out of Scope

| Feature | Reason |
| --- | --- |
| Geração sintética de sinais vitais / injeção artificial de anomalias | AD-015/AD-021: dados reais com rótulo clínico real (pH) substituem o simulador sintético — sintético fica restrito a F4 |
| Datasets com credenciamento (MIMIC-III/IV, MIMIC-IV waveform, MIMIC-IV-Ext-BHC) | AD-017: processo de CITI+DUA leva dias/semanas, fora do caminho crítico de 7 dias |
| Streaming real via Kinesis / infra de baixa latência | AD-011: near-real-time por micro-batch é suficiente |
| Processamento em GPU | AD-012: ambiente é CPU-only |
| Integração direta com AWS (S3/Lambda/SNS) | Papel de F3 é gerar sinal + evidência local; envio à nuvem e alerta são responsabilidade de F5 |
| Validação clínica própria do limiar de pH | Limiar pH < 7.05 é adotado da literatura clínica publicada (acidose/sofrimento fetal), não pesquisado/validado por este projeto |
| Datasets de disartria real (TORGO, UA-Speech) | Pertencem ao domínio de F2, não de F3; e estão fora do caminho crítico (AD-020) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Fonte de ground truth de anomalia | pH do cordão umbilical associado a cada registro CTU-UHB; pH < 7.05 = "patológico", caso contrário "normal" | AD-021; limiar clínico padrão da literatura sobre acidose fetal, citável no relatório | y |
| Formato de leitura do CTU-UHB / MIT-BIH | Biblioteca `wfdb` (padrão PhysioNet) | Padrão de fato do ecossistema PhysioNet; evita parser customizado | y |
| Composição da timeline de demo | Config declarativa (lista de IDs de registro + ordem), sem geração de novos valores — apenas concatenação/resample de séries reais | AD-021 ("compositor, não gerador sintético"); precisa ser reprodutível | y |
| Normalização entre registros concatenados | Resample para uma taxa de amostragem comum documentada antes de concatenar | Registros CTU-UHB podem ter taxas/duração diferentes; concatenar sem normalizar quebraria a continuidade temporal | y |
| "Tempo real" = micro-batch em janelas de segundos | Detectores processam a série (real ou timeline composta) por janela deslizante, sem streaming verdadeiro | AD-011 (gray area já respondida no brief) | y |
| Sem GPU disponível | Todos os detectores (z-score, IsolationForest) usam scikit-learn/numpy em CPU | AD-012 (gray area já respondida no brief) | y |
| MIT-BIH é opcional, não bloqueante | Se o download/parsing falhar ou não houver tempo, o caso é pulado sem afetar P1/P2 | Plano de 7 dias prioriza CTU-UHB (AD-016); MIT-BIH é "segundo caso" explicitamente opcional no brief | y |
| Licenciamento dos datasets | CTU-UHB (Open Data Commons) e MIT-BIH (PhysioNet open) usados conforme os termos de atribuição de cada base; citados no relatório técnico | Ambos são abertos sem credenciamento (AD-016), mas exigem atribuição — não é livre de qualquer termo | y |
| Persistência dos artefatos de evidência (gráficos/JSON) | Gravados em diretório de saída local (ex: `output/vitals/`), sem TTL/expiração | Escopo é demo acadêmica de curta duração; não há requisito de retenção de longo prazo | y |
| Sentido das comparações de limiar | **Todas estritas** (`>`): o valor exatamente igual ao limiar NÃO dispara. Vale para o z-score (VITALS-03), para `max_invalid_fraction` (VITALS-09) e para τ (AD-027) | Lacuna apontada pela verificação independente: a spec não dizia se a comparação era estrita ou inclusiva, e a fronteira nunca era exercitada em teste. Uniformizar evita que cada limiar siga uma convenção diferente | y |

**Open questions:** none — todas resolvidas ou registradas acima.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Registro CTU-UHB deve ter série FHR/contração e valor de pH presentes e numéricos antes de entrar no pipeline — ver VITALS-08 |
| Failure / partial-failure states | Registro corrompido/incompleto é descartado com aviso, sem interromper o restante do lote — ver VITALS-08; MIT-BIH ausente é pulado sem afetar P1/P2 — ver VITALS-11 |
| Idempotency / retry / duplicate handling | Composição de timeline via config (lista de IDs + ordem) é determinística — mesma config produz a mesma timeline — ver VITALS-07 |
| Auth boundaries & rate limits | N/A because F3 é um módulo local sem API exposta nem chamada externa autenticada |
| Concurrency / ordering | Concatenação de registros preserva ordem cronológica declarada, sem sobreposição de timestamps entre trechos — ver VITALS-07, VITALS-09 |
| Data lifecycle / expiry | N/A because artefatos de evidência são gerados por execução de demo acadêmica sem requisito de retenção/expiração |
| Observability | Cada anomalia detectada registra ID do registro de origem, pH, timestamp, score e detector, consumível por F5 — ver VITALS-06 |
| External-dependency failure | Falha ao carregar arquivo CTU-UHB/MIT-BIH (dataset local baixado previamente) tratada com erro claro ou descarte, sem abortar o restante do lote — ver VITALS-08, VITALS-11 |
| State-transition integrity | N/A because F3 não possui máquina de estados própria; a classificação verde/amarelo/vermelho pertence a F5 |

---

## User Stories

### P1: Detecção de anomalias sobre CTU-UHB com ground truth real (pH) ⭐ MVP

**User Story**: Como integrante do grupo validando o pipeline, quero carregar registros reais do
CTU-UHB e detectar anomalias comparando contra o rótulo clínico real (pH do cordão), para provar
que a detecção funciona com ground truth honesto antes de integrar às demais fontes multimodais.

**Why P1**: É a fatia vertical que destrava a fusão (F5) e sustenta o argumento central do
relatório e do vídeo — métricas contra rótulo real são mais defensáveis que anomalia injetada.

**Acceptance Criteria**:

1. WHEN um registro CTU-UHB é carregado no formato WFDB THEN o sistema SHALL extrair as séries de FHR (frequência cardíaca fetal) e contração uterina, e o valor de pH do cordão associado ao registro.
2. WHEN o pH do registro é menor que 7.05 THEN o sistema SHALL rotular o registro (ground truth) como "patológico"; caso contrário, como "normal" — limiar documentado e referenciado no relatório técnico.
3. WHEN o detector rolling z-score processa a série FHR/contração THEN o sistema SHALL classificar janelas como anômalas/normais usando um limiar configurável, documentado e justificado.
4. WHEN o detector IsolationForest processa a série multivariada (FHR + contração) THEN o sistema SHALL retornar um score de anomalia por janela e uma classificação binária derivada de um limiar configurável.
5. WHEN as classificações de janela de cada detector são agregadas por registro THEN o sistema SHALL compará-las ao rótulo pH real e calcular precision, recall e F1 por detector, salvos em relatório de métricas (JSON/CSV).
6. WHEN uma anomalia é detectada em uma janela THEN o sistema SHALL gerar evidência reproduzível: gráfico da janela com a anomalia destacada + metadados (ID do registro, timestamp, pH, score, detector).

**Independent Test**: Executar o pipeline sobre um subconjunto baixado de registros CTU-UHB e verificar que (a) o relatório de precision/recall/F1 contra o rótulo pH real é gerado, e (b) para cada anomalia reportada existe evidência (gráfico + metadados) correspondente na saída.

---

### P2: Compositor de timeline de demo (concatenação de registros reais)

**User Story**: Como grupo preparando a demo, quero compor a timeline de um "paciente" concatenando
um registro CTU-UHB normal seguido de um patológico (ou trecho dele), para simular deterioração ao
longo da internação sem fabricar nenhum dado — a série permanece 100% real.

**Why P2**: É a peça que transforma registros isolados do P1 numa história demonstrável no vídeo
("deterioração ao longo do tempo"), mas o pipeline de detecção já é validado sem ela (P1 sozinho é
demonstrável).

**Acceptance Criteria**:

1. WHEN dois ou mais registros CTU-UHB (identificados por ID) são especificados numa ordem via config declarativa THEN o sistema SHALL concatenar suas séries em uma timeline única com timestamps contínuos e sem sobreposição, preservando nos metadados de evidência a proveniência (qual trecho vem de qual registro original).
2. WHEN os registros concatenados têm taxas de amostragem diferentes THEN o sistema SHALL normalizar (resample) para uma taxa comum documentada antes da concatenação.
3. WHEN a timeline composta é processada pelos mesmos detectores do P1 THEN o sistema SHALL gerar anomalias/evidências ao longo da timeline unificada, sinalizando a transição normal→patológico.
4. WHEN a mesma config de composição (lista de IDs + ordem) é executada novamente THEN o sistema SHALL produzir a mesma timeline (determinismo).

**Independent Test**: Rodar o compositor com uma config de 2 registros conhecidos (um normal, um patológico) e confirmar que a timeline resultante tem duração = soma dos trechos, sem gaps/sobreposição, e que os metadados de evidência indicam corretamente de qual registro cada anomalia veio.

---

### P3: Caso opcional MIT-BIH Arrhythmia (segundo caso de série vital anotada)

**User Story**: Como grupo, quero processar opcionalmente um registro do MIT-BIH Arrhythmia (ECG
anotado) pelos mesmos detectores usados no CTU-UHB, para apresentar um segundo caso de série vital
com anomalias reais, se o tempo permitir.

**Why P3**: Enriquece o relatório com um segundo domínio de sinal vital, mas não é indispensável —
a história central de detecção já está provada pelo P1/P2 com CTU-UHB.

**Acceptance Criteria**:

1. WHEN um registro MIT-BIH é carregado no formato WFDB THEN o sistema SHALL extrair a série de ECG e as anotações de arritmia como rótulo real.
2. ~~WHEN a série MIT-BIH é processada pelos detectores (z-score e IsolationForest) THEN o sistema SHALL gerar anomalias e evidências no mesmo formato usado para o CTU-UHB.~~ — **REBAIXADO por AD-028.** A verificação independente constatou que este AC não foi entregue: o módulo é um leitor de dados desconectado do pipeline. Integrá-lo exigiria janelamento e features próprios para ECG a 360 Hz, um domínio distinto de CTG a 4 Hz. Fora do escopo de F3.
3. WHEN o dataset MIT-BIH não está disponível localmente (não baixado ou sem tempo de integrar) THEN o sistema SHALL pular esse caso de estudo sem interromper a execução do pipeline CTU-UHB (P1/P2).

**Independent Test**: Com o dataset MIT-BIH ausente, confirmar que o pipeline CTU-UHB completo (P1/P2) roda normalmente; com o dataset presente, confirmar que gera evidências no mesmo formato do CTU-UHB.

---

## Edge Cases

- WHEN um registro CTU-UHB está corrompido ou incompleto (série ausente ou pH ausente/não numérico) THEN o sistema SHALL descartá-lo do conjunto processado e registrar um aviso, sem interromper o restante do lote.
- WHEN a taxa de amostragem ou duração dos trechos concatenados na timeline difere entre registros THEN o sistema SHALL normalizar (resample) para uma taxa comum documentada antes da concatenação (ver VITALS-07).
- WHEN nenhum registro do subconjunto baixado atinge o limiar de pH patológico THEN o sistema SHALL alertar explicitamente que a demo de "detecção positiva" não está garantida naquele subconjunto, em vez de silenciosamente reportar recall indefinido/zero sem contexto.
- WHEN uma janela não tem pontos suficientes para o IsolationForest THEN o sistema SHALL reportar "dados insuficientes" para aquela janela em vez de falhar silenciosamente ou lançar exceção não tratada.

---

## Requirement Traceability

| Requirement ID | Story | Tarefa | Status |
| --- | --- | --- | --- |
| VITALS-01 | P1: Carga do registro CTU-UHB (série + pH) | T6 | Verified |
| VITALS-02 | P1: Rotulagem de ground truth via limiar de pH | T5 | Verified |
| VITALS-03 | P1: Detector rolling z-score | T10 | Verified |
| VITALS-04 | P1: Detector IsolationForest | T11 | Verified |
| VITALS-05 | P1: Agregação de classificações por registro | T12 | Verified |
| VITALS-06 | P1: Métricas precision/recall/F1 + evidência reproduzível | T2, T3, T13, T14, T15 | Verified |
| VITALS-07 | P2: Compositor de timeline (concatenação determinística + resample) | T16, T17 | Verified |
| VITALS-08 | Edge case: descarte de registro corrompido/incompleto | T6, T15 | Verified |
| VITALS-09 | Edge case: fallback para janela com dados insuficientes | T8, T11 | Verified |
| VITALS-10 | Edge case: alerta quando nenhum registro é patológico no subconjunto | T13 | Verified |
| VITALS-11 | P3: MIT-BIH — AC1 e AC3 (leitura + skip gracioso) | T18 | Verified |
| ~~VITALS-11 AC2~~ | ~~P3: MIT-BIH gera evidências no formato do CTU-UHB~~ | — | **Fora de escopo (AD-028)** |

**ID format:** `VITALS-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 11 requisitos, 11 mapeados para tarefas, 0 não mapeados. VITALS-11 AC2 formalmente fora de escopo por AD-028.

---

## Success Criteria

- [ ] Pipeline processa um subconjunto de registros CTU-UHB ponta a ponta com um único comando e produz métricas + evidências sem intervenção manual.
- [ ] Precision, recall e F1 calculados contra o rótulo pH real, por detector, reportados no relatório técnico.
- [ ] Ao menos uma timeline composta (normal → patológico) demonstrada com evidências corretamente atribuídas ao registro de origem.
- [ ] Toda anomalia reportada tem evidência visual/textual correspondente na saída (critério de aceite global do projeto).
