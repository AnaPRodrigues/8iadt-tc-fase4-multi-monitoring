# F3 — Vitals Anomaly Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Design**: `.specs/features/vitals-anomaly/design.md`
**Status**: In Progress

## Progresso

| Fase | Tarefas | Status |
| --- | --- | --- |
| 1 — Fundação e core | T1–T4 | ✅ Concluída (commits `480da5e`, `9c05ce0`, `68b8f53`, `00b22bd`) |
| 2 — Carga e preparação do sinal | T5–T8 | ✅ Concluída (commits `e7d07d2`, `90453d0`, `39bf964`, `837a68d`) |
| 3 — Detecção e avaliação | T9–T13 | ✅ Concluída (commits `56e4933`, `0ba2a8c`, `9e8b2f9`, `1a74c83`, `ce635a6`) |
| 4 — Evidência e demo | T14–T15 | ✅ Concluída (commits `e292baf`, `032f1fb`) |
| 5 — Compositor (P2) | T16–T17 | ✅ Concluída (commits `adb91e7`, `20a87e2`) |
| 6 — MIT-BIH (P3) | T18 | ✅ Concluída (commit `03c6834`) |

Todas as 18 tarefas implementadas e commitadas. Suíte: 135 testes passando, lint limpo.
Verificação independente pendente — ver `validation.md` quando o Verifier concluir.

---

## Test Coverage Matrix

> Gerada a partir da spec e das respostas do usuário — projeto greenfield, sem testes existentes e sem guidelines documentados. **Guidelines encontradas: nenhuma — defaults fortes aplicados.** Stack confirmada pelo usuário: pytest + ruff + Makefile; profundidade: lógica de domínio 1:1 com os ACs da spec.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Lógica de domínio (`core/metrics`, `core/evidence`, `core/config`, `vitals/loader`, `vitals/preprocess`, `vitals/windowing`, `vitals/features`, `vitals/detectors`, `vitals/aggregate`, `vitals/evaluate`, `vitals/compositor`) | unit | Todos os ramos; 1:1 com os ACs da spec; todo edge case listado tem teste | `tests/{core,vitals}/test_*.py` | `pytest -q -m "not integration"` |
| Orquestração / CLI (`vitals/cli`) | integration | Happy path ponta a ponta + dataset ausente + registro corrompido no lote | `tests/integration/test_*.py` | `pytest -q` |
| Scaffolding / config (`pyproject.toml`, `Makefile`, `ruff.toml`, `core/logging`) | none | — (só gate de build/lint) | — | `make lint` |

## Gate Check Commands

> Geradas a partir da stack confirmada pelo usuário (pytest + ruff + Makefile).

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Após tarefas só com testes unitários | `pytest -q -m "not integration"` |
| Full | Após tarefas com testes de integração | `pytest -q` |
| Build | Após conclusão de fase ou tarefas só de config | `make lint && pytest -q` |

---

## Execution Plan

Fases são ordenadas e rodam sequencialmente — cada fase termina antes da próxima começar, e as tarefas dentro de uma fase executam em ordem.

### Phase 1: Fundação do projeto e núcleo compartilhado

Estabelece o esqueleto (AD-025) e o contrato de evidência (AD-026) que F1/F2/F4/F5 herdam.

```
T1 → T2 → T3 → T4
```

### Phase 2: Carga e preparação do sinal

```
T5 → T6 → T7 → T8
```

### Phase 3: Detecção, agregação e avaliação

```
T9 → T10 → T11 → T12 → T13
```

### Phase 4: Evidência visual e demo ponta a ponta

```
T14 → T15
```

### Phase 5: Compositor de timeline (P2)

```
T16 → T17
```

### Phase 6: Caso opcional MIT-BIH (P3)

```
T18
```

---

## Task Breakdown

### T1: Esqueleto do projeto e logging estruturado

**What**: Criar a estrutura do monorepo Python (AD-025) com `pyproject.toml`, `Makefile`, config do ruff/pytest e `core/logging.py`.
**Where**: `pyproject.toml`, `Makefile`, `ruff.toml`, `src/core/logging.py`, `src/{core,vitals}/__init__.py`, `tests/`
**Depends on**: None
**Reuses**: —
**Requirement**: infraestrutura (AD-025)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Estrutura `src/{core,vitals}/`, `tests/{core,vitals,integration}/`, `infra/`, `output/` criada
- [ ] `Makefile` com alvos `test`, `lint` e `demo`
- [ ] Marcador `integration` registrado na config do pytest
- [ ] `core/logging.py` expõe `get_logger(name)` com saída estruturada
- [ ] Gate passa: `make lint && pytest -q`

**Tests**: none
**Gate**: build

**Commit**: `chore(core): esqueleto do projeto, Makefile e logging estruturado`

---

### T2: `core/metrics.py` — precision/recall/F1

**What**: Implementar `binary_metrics()` e `save_report()` no formato único de relatório de métricas do projeto.
**Where**: `src/core/metrics.py`, `tests/core/test_metrics.py`
**Depends on**: T1
**Reuses**: `core/logging.py`
**Requirement**: VITALS-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `binary_metrics(y_true, y_pred) -> MetricsReport` com precision, recall, F1 e support
- [ ] `save_report()` grava JSON legível
- [ ] Divisão por zero tratada explicitamente (sem positivos previstos, sem positivos reais)
- [ ] Testes cobrem: caso balanceado, só negativos, só positivos, previsão vazia, e o caso "nenhum registro patológico" (VITALS-10)
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 6 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(core): relatório de precision/recall/F1`

---

### T3: `core/evidence.py` — contrato único de evidência

**What**: Implementar o formato de evidência compartilhado (AD-026): metadados estruturados + caminho do artefato visual.
**Where**: `src/core/evidence.py`, `tests/core/test_evidence.py`
**Depends on**: T1
**Reuses**: `core/logging.py`
**Requirement**: VITALS-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `evidence_dir(feature, run_id) -> Path` seguindo a convenção `output/[feature]/[run_id]/`
- [ ] `save_evidence(event, artifact_path) -> Evidence` persiste metadados + referência ao artefato
- [ ] Metadados incluem `source_record_id` (proveniência exigida por VITALS-07)
- [ ] Testes cobrem: gravação bem-sucedida, diretório inexistente criado, artefato ausente rejeitado
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 4 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(core): contrato único de evidência`

---

### T4: `core/config.py` — carga de config declarativa

**What**: Implementar carga e validação da config declarativa (YAML/JSON) usada pelo CLI e pelo compositor.
**Where**: `src/core/config.py`, `tests/core/test_config.py`
**Depends on**: T1
**Reuses**: `core/logging.py`
**Requirement**: suporte a VITALS-07 (config do compositor) e aos limiares configuráveis

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `load_config(path) -> Config` com validação de campos obrigatórios
- [ ] Valores default documentados aplicados quando o campo é omitido
- [ ] Config inválida levanta erro com mensagem indicando o campo problemático
- [ ] Testes cobrem: config completa, config mínima com defaults, campo obrigatório ausente, tipo inválido
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 4 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(core): carga de configuração declarativa`

---

### T5: `parse_ph()` e rotulagem de ground truth

**What**: Implementar o parser do pH a partir das linhas de comentário do `.hea` e a regra de rotulagem `pH < 7.05`.
**Where**: `src/vitals/loader.py`, `tests/vitals/test_loader_ph.py`
**Depends on**: T1
**Reuses**: `core/logging.py`
**Requirement**: VITALS-02

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `parse_ph(comments) -> float | None` extrai o valor do formato verificado `#pH           7.26`
- [ ] `is_pathological(ph) -> bool` aplica o limiar 7.05 (limiar como constante nomeada, não literal solto)
- [ ] pH ausente, não numérico ou malformado retorna `None` (nunca levanta exceção não tratada)
- [ ] Testes cobrem: pH normal, pH patológico, valor exatamente 7.05 (fronteira), comentário ausente, valor não numérico, espaçamento variável
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 6 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): parser de pH e rotulagem de ground truth`

---

### T6: `load_record()` / `load_dataset()` — leitura WFDB

**What**: Implementar a leitura de registros CTU-UHB via `wfdb`, com descarte de registros inválidos sem interromper o lote.
**Where**: `src/vitals/loader.py` (modificar), `tests/vitals/test_loader.py`
**Depends on**: T5
**Reuses**: `parse_ph()` (T5), `core/logging.py`
**Requirement**: VITALS-01, VITALS-08

**Tools**:
- MCP: NONE (context7 não está disponível neste ambiente)
- Skill: NONE

**Done when**:
- [ ] **Confirmar os nomes reais dos atributos do objeto retornado por `wfdb.rdrecord()` antes de escrever o parser** — via `pip show wfdb` + inspeção no REPL, ou documentação oficial (pendência registrada no design — não presumir)
- [ ] `load_record(path) -> VitalRecord` extrai FHR, UC, `fs` e pH
- [ ] `load_dataset(dir) -> (records, failures)` descarta inválidos e acumula `LoadFailure`, sem interromper o lote (VITALS-08)
- [ ] Contagem de descartes registrada em log
- [ ] Testes cobrem (com fixtures WFDB sintéticas locais, sem depender do dataset baixado): registro válido, `.hea` sem pH, sinal ausente, arquivo corrompido, lote misto válido+inválido
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 5 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): leitura de registros CTU-UHB com descarte resiliente`

---

### T7: `vitals/preprocess.py` — perda de sinal e gaps

**What**: Implementar máscara de perda de sinal e interpolação de gaps curtos (mitigação do risco de dropout de CTG registrado no design).
**Where**: `src/vitals/preprocess.py`, `tests/vitals/test_preprocess.py`
**Depends on**: T6
**Reuses**: —
**Requirement**: mitigação de risco do design (suporte a VITALS-09)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `mark_signal_loss(signal) -> mask` identifica amostras inválidas (zeros/dropout)
- [ ] `interpolate_gaps(signal, mask, max_gap_s)` interpola gaps curtos; gaps acima do limite permanecem marcados como inválidos
- [ ] Sinal totalmente perdido não causa divisão por zero nem interpolação espúria
- [ ] Testes cobrem: sinal limpo, gap curto interpolado, gap longo preservado como inválido, sinal todo zerado, gap na borda inicial/final
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 5 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): tratamento de perda de sinal e gaps`

---

### T8: `vitals/windowing.py` — janelas deslizantes

**What**: Implementar o fatiamento em janelas deslizantes com marcação de `insufficient_data`.
**Where**: `src/vitals/windowing.py`, `tests/vitals/test_windowing.py`
**Depends on**: T7
**Reuses**: máscara de T7
**Requirement**: VITALS-09

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `make_windows(record, size_s, stride_s) -> list[Window]` preserva ordem cronológica estritamente crescente
- [ ] Janela com fração de amostras inválidas acima do limite é marcada `insufficient_data=True` (VITALS-09)
- [ ] Série mais curta que uma janela é tratada sem exceção
- [ ] Testes cobrem: janelamento regular, sobreposição por stride, janela final parcial, série curta demais, janela toda inválida, ordem cronológica preservada
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 6 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): janelamento deslizante com marcação de dados insuficientes`

---

### T9: `vitals/features.py` — features estatísticas e de domínio CTG

**What**: Implementar a extração do vetor de features por janela, incluindo features de domínio (mitigação do risco de correlação fraca com pH).
**Where**: `src/vitals/features.py`, `tests/vitals/test_features.py`
**Depends on**: T8
**Reuses**: `Window` (T8)
**Requirement**: suporte a VITALS-03, VITALS-04

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `extract(window) -> FeatureVector` com estatísticas (média, desvio, min, max)
- [ ] Features de domínio CTG: baseline de FHR, variabilidade de curto prazo, contagem de decelerações
- [ ] Janela `insufficient_data` retorna vetor marcado, nunca `NaN` silencioso
- [ ] Testes cobrem: janela normal, janela constante (desvio zero), janela com deceleração conhecida, janela insuficiente, valores fisiologicamente extremos
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 5 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): extração de features estatísticas e de domínio CTG`

---

### T10: `RollingZScoreDetector`

**What**: Implementar o `Protocol` comum de detector e o detector baseline rolling z-score.
**Where**: `src/vitals/detectors.py`, `tests/vitals/test_detectors_zscore.py`
**Depends on**: T9
**Reuses**: `FeatureVector` (T9)
**Requirement**: VITALS-03

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `Detector` Protocol com `score(windows) -> list[float]`
- [ ] `RollingZScoreDetector(threshold)` implementa o Protocol; limiar configurável, não hardcoded
- [ ] Janelas `insufficient_data` recebem score `None`, nunca 0.0
- [ ] Desvio-padrão zero na janela de baseline não causa divisão por zero
- [ ] Testes cobrem: série sem anomalia, outlier isolado detectado, limiar respeitado (abaixo/acima), baseline constante, janelas insuficientes
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 6 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): detector rolling z-score`

---

### T11: `IsolationForestDetector`

**What**: Implementar o detector multivariado (FHR+UC) com seed fixa para reprodutibilidade.
**Where**: `src/vitals/detectors.py` (modificar), `tests/vitals/test_detectors_iforest.py`
**Depends on**: T10
**Reuses**: `Detector` Protocol (T10)
**Requirement**: VITALS-04

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `IsolationForestDetector(contamination, seed)` implementa o mesmo Protocol de T10
- [ ] Mesma seed + mesma entrada produz scores idênticos (determinismo verificado em teste)
- [ ] Janelas `insufficient_data` excluídas do treino e recebem score `None` (VITALS-09)
- [ ] Dados insuficientes para treinar o modelo reportam "dados insuficientes", sem exceção não tratada
- [ ] Testes cobrem: determinismo por seed, detecção de outlier multivariado, exclusão de janelas insuficientes, conjunto pequeno demais para treinar
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 5 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): detector IsolationForest multivariado`

---

### T12: `vitals/aggregate.py` — regra janela → registro

**What**: Implementar a regra de agregação "fração de janelas anômalas > τ" definida em AD-027.
**Where**: `src/vitals/aggregate.py`, `tests/vitals/test_aggregate.py`
**Depends on**: T11
**Reuses**: —
**Requirement**: VITALS-05

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `aggregate(window_flags, tau) -> RecordVerdict` com τ configurável (default 0.15)
- [ ] Janelas `None` (dados insuficientes) **excluídas do denominador**, nunca contadas como normais (AD-027)
- [ ] `RecordVerdict` reporta `anomalous_fraction`, `n_windows_valid` e `n_windows_excluded`
- [ ] Registro sem nenhuma janela válida é sinalizado, não classificado como normal
- [ ] Testes cobrem: fração acima de τ, abaixo de τ, exatamente τ (fronteira), todas as janelas insuficientes, mistura válidas+insuficientes com verificação do denominador
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 6 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): agregação de janelas em veredicto por registro`

---

### T13: `vitals/evaluate.py` — avaliação contra o rótulo pH

**What**: Comparar os veredictos agregados ao rótulo pH real e produzir o relatório de métricas por detector.
**Where**: `src/vitals/evaluate.py`, `tests/vitals/test_evaluate.py`
**Depends on**: T12
**Reuses**: `core/metrics.py` (T2), `aggregate()` (T12)
**Requirement**: VITALS-06, VITALS-10

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `evaluate(verdicts, records) -> list[MetricsReport]` — um relatório por detector
- [ ] Quando nenhum registro do subconjunto é patológico, emite aviso explícito de que o recall é indefinido (VITALS-10) em vez de reportar zero sem contexto
- [ ] Prevalência real da classe patológica incluída no relatório (mitigação do risco de desbalanceamento)
- [ ] Testes cobrem: conjunto misto, conjunto só normal (aviso de VITALS-10), conjunto só patológico, registros descartados excluídos do cálculo
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 5 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): avaliação contra rótulo pH com aviso de classe ausente`

---

### T14: Gerador de gráfico de evidência

**What**: Gerar o gráfico da janela anômala destacada, gravado via o contrato de evidência de T3.
**Where**: `src/vitals/plot.py`, `tests/vitals/test_plot.py`
**Depends on**: T13
**Reuses**: `core/evidence.py` (T3)
**Requirement**: VITALS-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `plot_anomaly_window(record, event, out_path) -> Path` gera gráfico com FHR/UC e a janela anômala destacada
- [ ] Título/legenda incluem `record_id`, pH e detector de origem
- [ ] Artefato gravado sob a convenção de `evidence_dir()` (AD-026)
- [ ] Testes cobrem: geração do arquivo, conteúdo dos metadados associados, janela na borda da série
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 3 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): gráfico de evidência da janela anômala`

---

### T15: `vitals/cli.py` — pipeline ponta a ponta e `make demo`

**What**: Orquestrar loader → preprocess → windowing → features → detectores → agregação → avaliação → evidência num único comando.
**Where**: `src/vitals/cli.py`, `Makefile` (modificar), `tests/integration/test_vitals_pipeline.py`
**Depends on**: T14
**Reuses**: todos os módulos anteriores, `core/config.py` (T4)
**Requirement**: VITALS-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `run(config_path) -> int` executa o pipeline completo e grava tudo sob `output/vitals/[run_id]/`
- [ ] `make demo` executa o cenário ponta a ponta sem intervenção manual
- [ ] Relatório de métricas e evidências gerados na mesma execução
- [ ] Testes de integração cobrem: happy path com fixtures, diretório de dataset ausente, lote com registro corrompido (pipeline continua)
- [ ] Gate passa: `pytest -q`
- [ ] Test count: ≥ 3 testes de integração passam

**Tests**: integration
**Gate**: full

**Commit**: `feat(vitals): pipeline ponta a ponta e alvo make demo`

---

### T16: `vitals/compositor.py` — timeline de registros reais

**What**: Implementar a concatenação determinística de registros reais com proveniência por trecho (P2).
**Where**: `src/vitals/compositor.py`, `tests/vitals/test_compositor.py`
**Depends on**: T15
**Reuses**: `loader.py` (T6), `core/config.py` (T4)
**Requirement**: VITALS-07

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `compose(spec) -> VitalRecord` concatena na ordem declarada, com timestamps contínuos e sem sobreposição
- [ ] `provenance` preserva de qual registro original veio cada trecho
- [ ] `_ensure_uniform_rate()` valida 4 Hz e só resampla se divergirem (defensivo — todos os registros CTU-UHB são 4 Hz, fato verificado)
- [ ] Mesma config produz a mesma timeline (determinismo verificado em teste)
- [ ] Testes cobrem: concatenação de 2 registros, continuidade de timestamps, proveniência correta por trecho, determinismo, registros com fs divergente, config com registro inexistente
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 6 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): compositor de timeline com proveniência`

---

### T17: Integrar o compositor ao CLI

**What**: Permitir que o CLI execute o cenário de timeline composta (normal → patológico) além do modo por registro.
**Where**: `src/vitals/cli.py` (modificar), `tests/integration/test_vitals_timeline.py`
**Depends on**: T16
**Reuses**: `compose()` (T16), pipeline de T15
**Requirement**: VITALS-07

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] CLI aceita config de timeline e roda o pipeline sobre a série composta
- [ ] Evidências geradas atribuem corretamente cada anomalia ao registro de origem
- [ ] Testes de integração cobrem: cenário normal→patológico ponta a ponta, atribuição de proveniência na evidência
- [ ] Gate passa: `pytest -q`
- [ ] Test count: ≥ 2 testes de integração passam

**Tests**: integration
**Gate**: full

**Commit**: `feat(vitals): cenário de timeline composta no CLI`

---

### T18: Adaptador MIT-BIH (P3, opcional)

**What**: Adaptador para registros MIT-BIH Arrhythmia com skip gracioso quando o dataset está ausente.
**Where**: `src/vitals/mitbih.py`, `tests/vitals/test_mitbih.py`
**Depends on**: T17
**Reuses**: `loader.py` (T6), detectores (T10, T11)
**Requirement**: VITALS-11

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Carrega ECG + anotações de arritmia como rótulo real
- [ ] Produz evidências no mesmo formato do CTU-UHB (AD-026)
- [ ] Dataset ausente ⇒ caso pulado com log claro, sem interromper o pipeline CTU-UHB (VITALS-11)
- [ ] Testes cobrem: carga válida, dataset ausente (skip gracioso), anotação ausente
- [ ] Gate passa: `pytest -q -m "not integration"`
- [ ] Test count: ≥ 3 testes passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(vitals): adaptador opcional MIT-BIH`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

Phase 1:  T1 ──→ T2 ──→ T3 ──→ T4
Phase 2:  T5 ──→ T6 ──→ T7 ──→ T8
Phase 3:  T9 ──→ T10 ──→ T11 ──→ T12 ──→ T13
Phase 4:  T14 ──→ T15
Phase 5:  T16 ──→ T17
Phase 6:  T18
```

**Packing previsto (18 tarefas, budget ~7):**

| Batch | Fases | Tarefas |
| --- | --- | --- |
| 1 | Phase 1 + Phase 2 | T1–T8 (8) |
| 2 | Phase 3 + Phase 4 | T9–T15 (7) |
| 3 | Phase 5 + Phase 6 | T16–T18 (3) |

Como o packing gera mais de um batch, o Execute vai **oferecer** delegação a sub-agentes (offer-then-confirm) — nada é despachado sem sua aprovação.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1: Esqueleto + logging | config/scaffolding coeso | ✅ Granular |
| T2: `core/metrics` | 1 módulo, 2 funções coesas | ✅ Granular |
| T3: `core/evidence` | 1 módulo, 2 funções coesas | ✅ Granular |
| T4: `core/config` | 1 módulo | ✅ Granular |
| T5: `parse_ph` + rotulagem | 2 funções puras coesas | ✅ Granular |
| T6: `load_record`/`load_dataset` | 1 módulo (carga WFDB) | ✅ Granular |
| T7: `preprocess` | 1 módulo | ✅ Granular |
| T8: `windowing` | 1 módulo | ✅ Granular |
| T9: `features` | 1 módulo | ✅ Granular |
| T10: z-score + Protocol | 1 detector + contrato | ✅ Granular |
| T11: IsolationForest | 1 detector | ✅ Granular |
| T12: `aggregate` | 1 função | ✅ Granular |
| T13: `evaluate` | 1 módulo | ✅ Granular |
| T14: `plot` | 1 função | ✅ Granular |
| T15: `cli` + `make demo` | 1 ponto de entrada | ✅ Granular |
| T16: `compositor` | 1 módulo | ✅ Granular |
| T17: timeline no CLI | 1 modificação coesa | ✅ Granular |
| T18: adaptador MIT-BIH | 1 módulo | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (corpo) | Diagrama mostra | Status |
| --- | --- | --- | --- |
| T1 | None | (início da Phase 1) | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T1 | T2 → T3 (cadeia sequencial da fase) | ✅ Match |
| T4 | T1 | T3 → T4 (cadeia sequencial da fase) | ✅ Match |
| T5 | T1 | Phase 2 após Phase 1 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | Phase 3 após Phase 2 | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |
| T14 | T13 | Phase 4 após Phase 3 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |
| T16 | T15 | Phase 5 após Phase 4 | ✅ Match |
| T17 | T16 | T16 → T17 | ✅ Match |
| T18 | T17 | Phase 6 após Phase 5 | ✅ Match |

> Nota: T2, T3 e T4 dependem logicamente apenas de T1 (são módulos independentes de `core/`). O diagrama os desenha em cadeia porque a execução dentro de uma fase é estritamente sequencial — nenhuma dependência aponta para fase posterior.

---

## Test Co-location Validation

| Task | Camada criada/modificada | Matriz exige | Tarefa diz | Status |
| --- | --- | --- | --- | --- |
| T1 | Scaffolding/config | none | none | ✅ OK |
| T2 | Domínio (`core/metrics`) | unit | unit | ✅ OK |
| T3 | Domínio (`core/evidence`) | unit | unit | ✅ OK |
| T4 | Domínio (`core/config`) | unit | unit | ✅ OK |
| T5 | Domínio (`vitals/loader`) | unit | unit | ✅ OK |
| T6 | Domínio (`vitals/loader`) | unit | unit | ✅ OK |
| T7 | Domínio (`vitals/preprocess`) | unit | unit | ✅ OK |
| T8 | Domínio (`vitals/windowing`) | unit | unit | ✅ OK |
| T9 | Domínio (`vitals/features`) | unit | unit | ✅ OK |
| T10 | Domínio (`vitals/detectors`) | unit | unit | ✅ OK |
| T11 | Domínio (`vitals/detectors`) | unit | unit | ✅ OK |
| T12 | Domínio (`vitals/aggregate`) | unit | unit | ✅ OK |
| T13 | Domínio (`vitals/evaluate`) | unit | unit | ✅ OK |
| T14 | Domínio (`vitals/plot`) | unit | unit | ✅ OK |
| T15 | Orquestração (`vitals/cli`) | integration | integration | ✅ OK |
| T16 | Domínio (`vitals/compositor`) | unit | unit | ✅ OK |
| T17 | Orquestração (`vitals/cli`) | integration | integration | ✅ OK |
| T18 | Domínio (`vitals/mitbih`) | unit | unit | ✅ OK |

Nenhuma violação — todas as tarefas carregam seus próprios testes.

---

## Requirement Traceability

| Requirement | Tarefas | Status |
| --- | --- | --- |
| VITALS-01 | T6 | Mapeado |
| VITALS-02 | T5 | Mapeado |
| VITALS-03 | T10 | Mapeado |
| VITALS-04 | T11 | Mapeado |
| VITALS-05 | T12 | Mapeado |
| VITALS-06 | T2, T3, T13, T14, T15 | Mapeado |
| VITALS-07 | T16, T17 | Mapeado |
| VITALS-08 | T6 | Mapeado |
| VITALS-09 | T8, T11 | Mapeado |
| VITALS-10 | T13 | Mapeado |
| VITALS-11 | T18 | Mapeado |

**Coverage:** 11 de 11 requisitos mapeados para tarefas — 0 não mapeados.
