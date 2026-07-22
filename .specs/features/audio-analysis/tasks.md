# F2 (audio-analysis) Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its
Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is
the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review,
Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Design**: `.specs/features/audio-analysis/design.md`
**Status**: Draft

---

## Test Coverage Matrix

> Generated from codebase sampling — confirm before Execute. Guidelines found: nenhum
> `AGENTS.md`/`CONTRIBUTING.md` de padrão de teste; inferido de `backend/tests/vitals/`,
> `backend/tests/video/`, `backend/tests/common/test_config.py` e `backend/tests/conftest.py`.
> Padrão observado: **unit usa fixtures sintéticas/leves geradas em `tmp_path`** (ex.:
> `conftest.py` gera registros WFDB sintéticos "para testar sem baixar os GB do CTU-UHB");
> **integration roda contra dado real já baixado por F0**, marcado `@pytest.mark.integration` e
> excluído do gate rápido. Exceção documentada: `test_pose.py` baixa o modelo `.task` real
> (5.7 MB) sem marcação `integration`, por decisão explícita da tarefa que o criou — não é o
> padrão dominante, então F2 não a repete (o modelo faster-whisper "tiny" ainda é a fonte externa
> mais pesada de F2; ver nota em T8).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Lógica de domínio (config, loader, features, classifier, evaluate, evidence, transcribe, critical_terms, sentiment, acoustic_features, fatigue_score) | unit | Todos os branches; 1:1 com as ACs da spec; todo edge case listado (AUDIO-10, 12, 13, 14) coberto com fixtures sintéticas/leves, sem depender de download pesado | `backend/tests/audio/test_*.py` | `make test-unit` |
| Integração contra dado real (contagens reais do ICBHI, pipeline ponta a ponta) | integration | Contagens reais do dataset batem com o medido nesta sessão (920 arquivos, 126 pacientes, 6898 ciclos); `cli.run()` sobre o subconjunto curado real produz `metrics.json` + evidências; raia P2/P3 testada com um áudio real não-vocal (ICBHI) confirmando o caminho "não confiável" ponta a ponta; `consult_audio_paths` vazio não derruba o run | `backend/tests/integration/test_audio_pipeline.py` | `make test` |
| Dataclasses puras (`models.py`) | none | Nenhuma lógica própria — exercitadas transitivamente pelos testes acima | — | `make lint` |

## Gate Check Commands

> Geradas a partir do `Makefile` do projeto — confirmar antes de Execute.

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Após tarefas só com testes unit | `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio` |
| Full | Após tarefas com teste integration | `.venv/bin/python -m pytest -q backend/tests/audio backend/tests/integration/test_audio_pipeline.py` |
| Build | Fim de fase / tarefas de config-only | `make test && make lint` |

---

## Execution Plan

Phases are ordered and run sequentially — each phase completes before the next begins, and tasks
within a phase execute in order.

### Phase 1: Foundation

```
T1 → T2 → T3
```

### Phase 2: P1 — Classificador respiratório ICBHI (dado real rotulado)

```
T4 → T5 → T6 → T7
```

### Phase 3: P2 — Transcrição, termos críticos, sentimento

```
T8 → T9 → T10
```

### Phase 4: P3 — Fadiga vocal

```
T11 → T12
```

### Phase 5: Orquestração

```
T13
```

---

## Task Breakdown

### T1: Dataclasses compartilhadas de F2

**What**: Criar `pipelines/audio/models.py` com todas as dataclasses do design (`IcbhiRecordingMeta`,
`RespiratoryCycle`, `Prediction`, `TranscriptSegment`, `Transcript`, `CriticalTermHit`,
`SentimentResult`, `AcousticFeatures`), frozen, sem lógica.
**Where**: `backend/pipelines/audio/models.py`
**Depends on**: None
**Reuses**: convenção de `pipelines/video/models.py` (centralizar dataclasses de uma feature em um único módulo, precedente de F1/T1).
**Requirement**: Fundação de AUDIO-01..14.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Todas as 8 dataclasses do design existem, `frozen=True`, com os campos exatos listados em `design.md` § Data Models
- [ ] `make lint` limpo

**Tests**: none
**Gate**: build

---

### T2: Configuração declarativa de F2

**What**: Criar `pipelines/audio/config.py` com `Config` (dataclass) e `load_config(path) -> Config`,
mesma disciplina de `common/config.py` (campo desconhecido = erro; obrigatórios explícitos), campos
próprios: `icbhi_dataset_dir` (obrigatório), `icbhi_max_patients` (default 40),
`consult_audio_paths` (default `[]`), `critical_terms_path` (default `None` → usa lista embutida),
`whisper_model_size` (default `"small"`), `no_speech_threshold` (default `0.6`),
`sentiment_threshold` (default `0.2`), `fatigue_threshold` (default `1.0`), `seed` (default `42`),
`output_root` (default `"output"`).
**Where**: `backend/pipelines/audio/config.py`
**Depends on**: T1
**Reuses**: o *padrão* de validação de `common/config.py` (não a classe — ver design.md § Tech Decisions e § Risks).
**Requirement**: Fundação de AUDIO-01..14.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Campo desconhecido no YAML levanta `ValueError`
- [ ] `icbhi_dataset_dir` ausente levanta `ValueError`
- [ ] Defaults aplicados corretamente quando omitidos
- [ ] `consult_audio_paths` vazio é válido (não é erro)
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_config.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T2 config declarativa de audio-analysis`

---

### T3: Loader ICBHI (parsing, ciclos, subconjunto curado)

**What**: Criar `pipelines/audio/icbhi_loader.py` com `parse_filename(name) -> IcbhiRecordingMeta`,
`load_cycles(txt_path, wav_path) -> list[RespiratoryCycle]` (rótulo `normal`/`crackle`/`wheeze`/`both`
a partir das duas flags binárias — SPEC_DEVIATION documentada no design), `load_dataset(dataset_dir)
-> tuple[list[RespiratoryCycle], list[str]]` (tolerante a arquivo corrompido/linha malformada, AUDIO-12/13)
e `select_subset(cycles, max_patients, seed) -> list[RespiratoryCycle]` (amostra determinística por
paciente, nunca por ciclo solto).
**Where**: `backend/pipelines/audio/icbhi_loader.py`
**Depends on**: T1
**Reuses**: padrão de tolerância a falha de `pipelines/vitals/loader.py::load_dataset`.
**Requirement**: AUDIO-01, AUDIO-12, AUDIO-13.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `parse_filename` extrai os 5 campos do formato documentado (`filename_format.txt`) para nomes reais do dataset
- [ ] Ciclo com `crackle=1,wheeze=1` vira classe `"both"` (não descartado, não vira `"crackle"` por acidente)
- [ ] Linha de anotação malformada é excluída do resultado, não conta como erro do classificador
- [ ] Arquivo `.wav` corrompido/ilegível é pulado e reportado na lista de falhas, sem derrubar o lote
- [ ] `select_subset` com o mesmo `seed` produz o mesmo subconjunto de pacientes (determinismo)
- [ ] Teste de integração confirma as contagens reais medidas nesta sessão: 920 arquivos válidos, 126 pacientes, 6898 ciclos totais em `data/icbhi/ICBHI_final_database/`
- [ ] Gate check passa: `.venv/bin/python -m pytest -q backend/tests/audio/test_icbhi_loader.py`

**Tests**: unit + integration
**Gate**: full

**Commit**: `feat(f2): T3 icbhi_loader com parsing real e subconjunto curado`

---

### T4: Extração de features espectrais/MFCC por ciclo

**What**: Criar `pipelines/audio/icbhi_features.py::extract(cycle, sr=4000) -> np.ndarray` — recorta
o trecho `[start_s, end_s]` do WAV, resample, calcula MFCC(13) + centroide/bandwidth/rolloff
espectral + zero-crossing rate via `librosa`, agrega média+desvio-padrão em vetor 1-D de tamanho fixo.
**Where**: `backend/pipelines/audio/icbhi_features.py`
**Depends on**: T1, T3
**Reuses**: nada de `common/`.
**Requirement**: AUDIO-01.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Vetor de saída tem sempre o mesmo tamanho para ciclos de duração diferente (testado com dois ciclos sintéticos de durações distintas)
- [ ] Mesmo ciclo processado duas vezes produz o mesmo vetor (determinismo, AUDIO-14)
- [ ] Ciclo silencioso (amplitude ~0) não levanta exceção e produz vetor finito (sem NaN/Inf)
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_icbhi_features.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T4 icbhi_features extração MFCC/espectral`

---

### T5: Classificador respiratório (split por paciente, treino, predição)

**What**: Criar `pipelines/audio/icbhi_classifier.py` com `split_by_patient(cycles, test_size, seed)`
(via `sklearn.model_selection.GroupShuffleSplit` agrupado por `patient_id`, nunca por ciclo solto),
`train(cycles, seed) -> IcbhiClassifier` (`RandomForestClassifier(n_estimators=200,
class_weight="balanced", random_state=seed)`), `predict(model, cycle) -> Prediction` (classe +
`predict_proba` da classe vencedora como confiança).
**Where**: `backend/pipelines/audio/icbhi_classifier.py`
**Depends on**: T4
**Reuses**: `scikit-learn` (já em `pyproject.toml`); nenhum artefato persistido em disco (design: sem cache de modelo).
**Requirement**: AUDIO-02, AUDIO-03, AUDIO-14 (parte: `random_state=seed`).

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `split_by_patient` nunca coloca o mesmo `patient_id` nos dois lados do split (testado com dataset sintético de pacientes com múltiplos ciclos)
- [ ] `train`+`predict` com `seed` fixo é determinístico (duas execuções produzem a mesma predição)
- [ ] `predict` retorna confiança em `[0, 1]`
- [ ] Treinado sobre um conjunto sintético linearmente separável, o classificador acerta a classe majoritária esperada (prova que a lógica de treino/predição está conectada, não só que não lança exceção)
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_icbhi_classifier.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T5 icbhi_classifier RandomForest com split por paciente`

---

### T6: Avaliação por classe (precision/recall/F1)

**What**: Criar `pipelines/audio/icbhi_evaluate.py::evaluate(y_true, y_pred, classes) ->
list[MetricsReport]` (one-vs-rest por classe via `common.metrics.binary_metrics`) e
`save_evaluation(reports, path)`.
**Where**: `backend/pipelines/audio/icbhi_evaluate.py`
**Depends on**: T5
**Reuses**: `common/metrics.py` (`binary_metrics`), mesmo padrão de `pipelines/vitals/evaluate.py`.
**Requirement**: AUDIO-04.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Uma classe ausente do conjunto de teste produz `precision`/`recall`/`f1` como `None` (nunca `0.0`), igual à disciplina de `common/metrics.py`
- [ ] As 4 classes (`normal`/`crackle`/`wheeze`/`both`) aparecem no relatório mesmo quando uma delas tem `support=0`
- [ ] `save_evaluation` grava JSON válido, recarregável
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_icbhi_evaluate.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T6 icbhi_evaluate metricas por classe`

---

### T7: Evidência de ciclo anômalo (espectrograma)

**What**: Criar `pipelines/audio/icbhi_evidence.py::plot_spectrogram(cycle, path) -> Path`
(mel-spectrogram em dB via `librosa.feature.melspectrogram`/`librosa.display.specshow`) e
`evidence_id_for(cycle, predicted) -> str`, gravando via `common.evidence.save_evidence` sempre que
a classe prevista ≠ `"normal"`.
**Where**: `backend/pipelines/audio/icbhi_evidence.py`
**Depends on**: T5
**Reuses**: `common/evidence.py` (`save_evidence`, `evidence_dir`).
**Requirement**: AUDIO-05.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] PNG do espectrograma é gerado e é um arquivo de imagem válido (`is_file()`, tamanho > 0)
- [ ] Sidecar JSON contém `record_id`, `cycle_index`, classe prevista, classe real, score
- [ ] Ciclo previsto como `"normal"` não gera evidência (só classes anômalas geram)
- [ ] `evidence_id_for` é determinístico (mesmo ciclo + mesma predição → mesmo id)
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_icbhi_evidence.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T7 icbhi_evidence espectrograma de ciclo anomalo`

---

### T8: Transcrição local (faster-whisper) com sinalização de confiabilidade

**What**: Criar `pipelines/audio/transcribe.py::transcribe(audio_path, model_size,
no_speech_threshold, model=None) -> Transcript` — `model` é injetável (default constrói
`WhisperModel(model_size, device="cpu", compute_type="int8")`) para permitir teste sem repetir
inferência real cara. Chama `model.transcribe(audio_path, language="pt", temperature=0.0,
beam_size=5)` (API real confirmada por introspecção nesta sessão). `Transcript.reliable = texto não
vazio E média de `no_speech_prob` dos segmentos ≤ `no_speech_threshold``.
**Where**: `backend/pipelines/audio/transcribe.py`
**Depends on**: T1
**Reuses**: nada de `common/`.
**Requirement**: AUDIO-06, AUDIO-10, AUDIO-14 (parte: `temperature=0.0`).

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Unit: com um `model` fake injetado (segmentos/`no_speech_prob` controlados), `reliable` fica `True`/`False` corretamente nos dois casos, incluindo o limiar exato de `no_speech_threshold`
- [ ] Unit: `model.transcribe` é chamado com `temperature=0.0` (asserido explicitamente — não implícito)
- [ ] Integration (sem fake, modelo real `"tiny"`, baixado sob demanda como `pose_landmarker` faz em F1): transcrever um áudio real do ICBHI (som respiratório, sem fala) produz `reliable=False` — caso negativo real, sem fabricar áudio de fala
- [ ] **Gap documentado, não bloqueante**: não existe ainda áudio real de consulta (fala) no repositório para validar o caminho positivo (`reliable=True`, transcript com conteúdo real) — fica para quando o grupo gravar os áudios (nota já registrada no handoff de `STATE.md`); a lógica de decisão de `reliable` já está 100% coberta pelos testes unit acima com valores controlados
- [ ] Gate check passa: `.venv/bin/python -m pytest -q backend/tests/audio/test_transcribe.py`

**Tests**: unit + integration
**Gate**: full

**Commit**: `feat(f2): T8 transcribe faster-whisper com flag de confiabilidade`

---

### T9: Termos críticos configuráveis

**What**: Criar `pipelines/audio/critical_terms.py` com `normalize_text(s) -> str` (minúsculas +
remoção de acento via `unicodedata`, reutilizável por `sentiment.py`), `load_terms(path | None) ->
list[str]` (lista padrão embutida se ausente/vazia: "dor no peito", "falta de ar", "tontura" +
extras do brief), `find_terms(transcript, terms) -> list[CriticalTermHit]` (contexto ±40 caracteres,
timestamp aproximado do segmento whisper que contém o match), `save_term_evidence(hit, transcript,
run_id, ...) -> Evidence` (artefato `.txt` com o transcript e o termo destacado `**termo**`).
**Where**: `backend/pipelines/audio/critical_terms.py`
**Depends on**: T8
**Reuses**: `common/evidence.py` (`save_evidence`).
**Requirement**: AUDIO-07, AUDIO-09.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Termo multi-palavra ("dor no peito") é encontrado mesmo com acentuação/caixa diferente no transcript
- [ ] `find_terms` sobre um `Transcript` sem nenhum termo retorna lista vazia (sem falso positivo)
- [ ] `load_terms(None)` e `load_terms(path_vazio)` retornam a lista padrão documentada
- [ ] Timestamp aproximado corresponde ao segmento correto quando o transcript tem múltiplos segmentos
- [ ] Evidência gerada tem o termo destacado no artefato `.txt` e os metadados no sidecar
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_critical_terms.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T9 critical_terms busca e evidencia de termos criticos`

---

### T10: Sentimento local (léxico pt-BR)

**What**: Criar `pipelines/audio/sentiment.py::classify(transcript_text, threshold) ->
SentimentResult` — conta ocorrências normalizadas (via `critical_terms.normalize_text`) de um
léxico curado embutido (positivo/negativo), `score = (pos-neg)/(pos+neg)` se houver hit, senão
`0.0`; `|score| < threshold` → `"neutro"`.
**Where**: `backend/pipelines/audio/sentiment.py`
**Depends on**: T9
**Reuses**: `critical_terms.normalize_text`.
**Requirement**: AUDIO-08.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Texto sem nenhuma palavra do léxico → `score=0.0`, `label="neutro"`
- [ ] Texto majoritariamente positivo → `label="positivo"`; majoritariamente negativo → `label="negativo"`
- [ ] `threshold` configurável muda a classificação de um mesmo score-limite (dois valores de threshold produzindo labels diferentes para o mesmo texto, prova que não está hardcoded)
- [ ] Nenhuma chamada de rede/serviço de nuvem (AD-002/003) — garantido por construção (sem import de client AWS no módulo)
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_sentiment.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T10 sentiment lexico pt-BR local`

---

### T11: Features acústicas (jitter, shimmer, HNR, pausas, velocidade de fala)

**What**: Criar `pipelines/audio/acoustic_features.py::extract(audio_path, transcript) ->
AcousticFeatures` — receita Parselmouth/Praat validada nesta sessão (`To Pitch` → `To PointProcess
(periodic, cc)` → `Get jitter (local)`/`Get shimmer (local)`; `To Harmonicity (cc)` → `Get mean` para
HNR); pausas via `librosa.effects.split(y, top_db=...)`; velocidade de fala = contagem de palavras
do `transcript` / duração de fala.
**Where**: `backend/pipelines/audio/acoustic_features.py`
**Depends on**: T8
**Reuses**: nada de `common/`.
**Requirement**: AUDIO-11.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Sobre um sinal de voz sintético (harmônicos + ruído, mesmo tipo testado nesta sessão) `jitter_local`, `shimmer_local`, `hnr_db` são finitos e nas faixas plausíveis (jitter < 5%, shimmer < 20%, HNR entre 0–40 dB)
- [ ] Sinal com pausas de silêncio inseridas deliberadamente produz `pause_rate` maior que o mesmo sinal sem pausas
- [ ] `speaking_rate_wps` é calculado a partir da contagem de palavras do `Transcript` passado (não recalcula transcrição)
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_acoustic_features.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T11 acoustic_features jitter shimmer hnr pausas`

---

### T12: Score heurístico de fadiga vocal

**What**: Criar `pipelines/audio/fatigue_score.py::score(features, baseline) -> float` (z-score de
cada feature contra o `baseline` da mesma execução, combinado em média de
`[jitter_z, shimmer_z, -hnr_z, pause_rate_z, -speaking_rate_z]`) e `is_fatigued(score, threshold) ->
bool`.
**Where**: `backend/pipelines/audio/fatigue_score.py`
**Depends on**: T11
**Reuses**: nada de `common/`.
**Requirement**: AUDIO-11.

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Duas `AcousticFeatures` sintéticas — uma "normal" e uma com fala mais lenta/pausada (jitter/shimmer maiores, HNR menor, pause_rate maior, speaking_rate menor) — contra o mesmo `baseline`: a segunda produz `score` estritamente maior (valida o comportamento pedido pelo Independent Test de P3 da spec, a nível de função)
- [ ] `is_fatigued` respeita o `threshold` configurável (dois thresholds produzindo resultados diferentes para o mesmo score)
- [ ] `baseline` de um único elemento não levanta exceção (z-score com desvio-padrão zero tratado sem `ZeroDivisionError`/`NaN` silencioso)
- [ ] Gate check passa: `.venv/bin/python -m pytest -q -m "not integration" backend/tests/audio/test_fatigue_score.py`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(f2): T12 fatigue_score heuristica de fadiga vocal`

---

### T13: CLI ponta a ponta de F2

**What**: Criar `pipelines/audio/cli.py::run(config_path, run_id) -> int` e `main(argv) -> int` —
mesmo esqueleto de `pipelines/vitals/cli.py` (dica de `make data` em `FileNotFoundError`). Orquestra:
(1) carrega config; (2) P1 — carrega+seleciona subconjunto ICBHI, split por paciente, treina, avalia,
grava `metrics.json` + evidências dos ciclos anômalos; (3) para cada caminho em
`consult_audio_paths` (pula com `log.warning` se vazio) — transcreve, busca termos críticos +
gera evidência quando encontrados, calcula sentimento, calcula features acústicas + score de fadiga
e gera evidência quando ultrapassa o limiar; tudo sob `output/audio/<run_id>/`.
**Where**: `backend/pipelines/audio/cli.py`
**Depends on**: T2, T3, T6, T7, T9, T10, T12
**Reuses**: esqueleto de `pipelines/vitals/cli.py`; `common/evidence.py`, `common/logging.py`.
**Requirement**: Orquestra AUDIO-01..14 (integração).

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Integration: `run()` sobre o subconjunto curado real do ICBHI (`icbhi_max_patients=40`) produz `metrics.json` com as 4 classes e ao menos uma evidência de ciclo anômalo em `output/audio/<run_id>/`
- [ ] Integration: `run()` com `consult_audio_paths=[<um wav real do ICBHI, sem fala>]` completa sem lançar exceção e a raia P2/P3 grava um resumo com `reliable=False`, sem evidência de termo crítico falso-positivo (reusa o achado de T8)
- [ ] Integration: `run()` com `consult_audio_paths=[]` roda só P1 até o fim, sem falhar
- [ ] `FileNotFoundError` (dataset ICBHI ausente) produz a dica de `make data`, mesmo padrão de `vitals/cli.py`
- [ ] Gate check passa: `.venv/bin/python -m pytest -q backend/tests/audio backend/tests/integration/test_audio_pipeline.py`
- [ ] `make lint` limpo em todo `backend/pipelines/audio/`

**Tests**: integration
**Gate**: full

**Commit**: `feat(f2): T13 cli orquestracao ponta a ponta de audio-analysis`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5

Phase 1:  T1 ──→ T2 ──→ T3
Phase 2:  T4 ──→ T5 ──→ T6 ──→ T7
Phase 3:  T8 ──→ T9 ──→ T10
Phase 4:  T11 ──→ T12
Phase 5:  T13
```

Execution is strictly sequential — there is no intra-phase parallelism.

**Packing note (13 tasks total, > ~8 task threshold):** se o usuário aceitar delegação a
sub-agentes no início do Execute, o empacotamento natural em lotes de ~7 tarefas, respeitando
fronteira de fase, é: **Lote 1 = Fase 1 + Fase 2 (T1–T7, 7 tarefas)**, **Lote 2 = Fase 3 + Fase 4 +
Fase 5 (T8–T13, 6 tarefas)**. Oferta feita no início do Execute, não decidida aqui.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1: models.py | 1 arquivo, dataclasses puras | ✅ Granular |
| T2: config.py | 1 arquivo, 1 função de carga + dataclass | ✅ Granular |
| T3: icbhi_loader.py | 1 arquivo, 4 funções coesas do mesmo domínio (loader) | ⚠️ OK — coeso, mesmo padrão de F1 T6 (`object_loader.py`) |
| T4: icbhi_features.py | 1 arquivo, 1 função | ✅ Granular |
| T5: icbhi_classifier.py | 1 arquivo, 3 funções coesas (split/train/predict do mesmo componente) | ⚠️ OK — coeso, mesmo padrão de F1 T4 (`pose_detector.py`) |
| T6: icbhi_evaluate.py | 1 arquivo, 2 funções | ✅ Granular |
| T7: icbhi_evidence.py | 1 arquivo, 2 funções | ✅ Granular |
| T8: transcribe.py | 1 arquivo, 1 função | ✅ Granular |
| T9: critical_terms.py | 1 arquivo, 4 funções coesas (mesmo componente do design) | ⚠️ OK — coeso, mesmo padrão de F1 T9 (`object_evaluate.py`) |
| T10: sentiment.py | 1 arquivo, 1 função | ✅ Granular |
| T11: acoustic_features.py | 1 arquivo, 1 função | ✅ Granular |
| T12: fatigue_score.py | 1 arquivo, 2 funções | ✅ Granular |
| T13: cli.py | 1 arquivo, orquestração (`run`/`main`) | ✅ Granular — é o padrão "1 CLI = 1 tarefa" já usado em F3 e (implicitamente) F1 |

**Granularity check**: nenhuma tarefa toca mais de um arquivo novo; tarefas com múltiplas funções
no mesmo arquivo são cada uma um único componente coeso do design (mesmo padrão de granularidade
usado em F1, ver `STATE.md` § Resumo de implementação de F1).

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | (nenhuma seta de entrada) | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T1 | T1 → T2 → T3 (T3 depende diretamente só de T1; a seta T2→T3 no diagrama reflete ordem sequencial de fase, não dependência de dado — ver nota) | ✅ Match* |
| T4 | T1, T3 | T3 → T4 (fase 1→2) | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T5 | T6 → T7 (sequencial de fase; dependência real é T5) | ✅ Match* |
| T8 | T1 | T7 → T8 (fase 2→3, sequencial) | ✅ Match* |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | T8 | T10 → T11 (fase 3→4, sequencial) | ✅ Match* |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T2, T3, T6, T7, T9, T10, T12 | T12 → T13 (fase 4→5, sequencial) | ✅ Match* |

**Nota (`*`)**: dentro de uma fase e entre fases consecutivas, o diagrama desenha a ordem de
*execução* (sempre sequencial, uma tarefa por vez); o `Depends on` de cada tarefa documenta a
dependência de *dado* real, que pode ser um subconjunto das tarefas anteriores na sequência (ex.:
T7 executa depois de T6 na ordem, mas seus dados vêm de T5, não de T6). Nenhuma tarefa depende de
uma tarefa de fase posterior — regra respeitada em todas as 13 tarefas.

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| --- | --- | --- | --- | --- |
| T1: models.py | Entity (dataclasses) | none | none | ✅ OK |
| T2: config.py | Domínio (validação) | unit | unit | ✅ OK |
| T3: icbhi_loader.py | Domínio + dado real | unit + integration | unit + integration | ✅ OK |
| T4: icbhi_features.py | Domínio | unit | unit | ✅ OK |
| T5: icbhi_classifier.py | Domínio | unit | unit | ✅ OK |
| T6: icbhi_evaluate.py | Domínio | unit | unit | ✅ OK |
| T7: icbhi_evidence.py | Domínio | unit | unit | ✅ OK |
| T8: transcribe.py | Domínio + dado real (negativo) | unit + integration | unit + integration | ✅ OK |
| T9: critical_terms.py | Domínio | unit | unit | ✅ OK |
| T10: sentiment.py | Domínio | unit | unit | ✅ OK |
| T11: acoustic_features.py | Domínio | unit | unit | ✅ OK |
| T12: fatigue_score.py | Domínio | unit | unit | ✅ OK |
| T13: cli.py | Integração ponta a ponta | integration | integration | ✅ OK |

Nenhuma violação. Nenhuma tarefa usa "testado em outra tarefa" como justificativa de `Tests: none`
fora do caso legítimo (T1, camada `Entity` sem lógica).

---

## Aberto / Blocker documentado

- **T8** tem um gap aceito e explícito (não um `Tests: none` disfarçado): o caminho **positivo**
  de transcrição (fala real → transcript correto) só pode ser validado com o(s) áudio(s) de
  consulta que o grupo ainda vai gravar (nota já registrada em `STATE.md` § Handoff, "confirmed:
  n" no roteiro exato). A lógica de decisão de `reliable` está 100% coberta por unit tests com
  valores controlados; o caminho negativo tem cobertura de integração real (áudio ICBHI sem fala).
  Isso é rastreado aqui para o Verifier não redescobrir — mesmo padrão do gap aceito em VIDEO-10.
