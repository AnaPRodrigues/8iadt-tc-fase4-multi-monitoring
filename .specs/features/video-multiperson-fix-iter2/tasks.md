# Video Multi-Person Fix — Iteration 2 Tasks

## Execution Protocol (MANDATORY)

Implement these tasks with the `tlc-spec-driven` skill — activate it by name and follow its Execute flow and Critical Rules. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Design**: `.specs/features/video-multiperson-fix-iter2/design.md`
**Spec**: `.specs/features/video-multiperson-fix-iter2/spec.md`
**Status**: Done (awaiting Verifier)

---

## Test Coverage Matrix

> Generated from codebase sampling (`backend/tests/video/`) and spec. Guidelines found: `pyproject.toml` (pytest config) — strong defaults applied for coverage depth.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
|------------|-------------------|---------------------|------------------|-------------|
| Domain logic (`pose_features.py`, `pose_detector.py`) | unit | All branches; 1:1 to spec ACs; every listed edge case has a test | `backend/tests/video/test_<module>.py` | `python -m pytest backend/tests/video/test_<module>.py -q` |
| Orchestration (`analise.py`) | integration | Routes added/modified: happy path + edge + error/failure paths | `backend/tests/app/test_analise.py` | `python -m pytest backend/tests/app/test_analise.py -q` |
| Entities / config (`models.py`) | none | Build gate only | — | `ruff check backend` |

## Gate Check Commands

> Generated from codebase (`pyproject.toml`, `Makefile`).

| Gate Level | When to Use | Command |
|------------|-------------|---------|
| Quick | After tasks with unit tests only (domain logic) | `python -m pytest backend/tests/video/test_<module>.py -q` |
| Full | After tasks modifying orchestration (analise.py) | `python -m pytest backend/tests/video/ backend/tests/app/test_analise.py -q` |
| Build | After last task in phase / entity-only tasks | `python -m pytest backend/tests/ -q && ruff check backend` |

---

## Execution Plan

Phases are ordered and run sequentially — each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Foundation (constants + role classifier)

```
T1 → T2
```

T1 must complete before T2 (T2 uses the visibility constant from T1).

### Phase 2: New Detectors

```
T3 → T4 → T5
```

All depend on T2 (`classify_person_role`). T3-T5 are independent of each other but ordered for clarity.

### Phase 3: Multi-Person Pipeline Integration

```
T6 → T7 → T8
```

T6 (persistência) → T7 (orchestrator) → T8 (wire in analise.py + cli.py).

---

## Task Breakdown

### T1: Unify visibility threshold + reduce streak minimum (B3 + C1)

**What**: Substituir `_MIN_VISIBILITY = 0.5` e `_MIN_OCCLUSION_VIS = 0.4` por uma única constante `_MIN_VISIBILITY = 0.4`. Extrair o valor mágico `3` do filtro de streak como `_MIN_CONSECUTIVE_FRAMES = 2`. Atualizar todos os pontos de uso.

**Where**: `backend/pipelines/video/pose_features.py` (modify constants + references)

**Depends on**: None

**Reuses**: N/A — alteração de constantes existentes

**Requirement**: ITER2-07, ITER2-08

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `_MIN_VISIBILITY = 0.4` (única constante, remove `_MIN_OCCLUSION_VIS`)
- [ ] `_MIN_CONSECUTIVE_FRAMES = 2` (novo, extraído do valor mágico 3)
- [ ] `hip_center()` usa `_MIN_VISIBILITY` e devolve coordenadas com visibilidade 0.45
- [ ] Filtro de streak em `select_ground_person` usa `_MIN_CONSECUTIVE_FRAMES`
- [ ] Todos os outros gates de visibilidade usam `_MIN_VISIBILITY` (vertical_velocity, joint_angle, trunk_tilt, _upper_body_center, select_ground_person)
- [ ] Teste: `hip_center()` com visibilidade 0.45 → devolve coordenadas (novo)
- [ ] Teste: pessoa em 2 frames consecutivos → incluída no `select_ground_person` (novo)
- [ ] Teste: pessoa em 1 frame isolado → descartada (novo)
- [ ] Gate quick: 68+ testes existentes sem regressão
- [ ] Test count: ≥ 71 testes passam

**Tests**: unit

**Gate**: quick

**Commit**: `fix(video-pose): unify visibility to 0.4 and reduce streak minimum to 2`

---

### T2: Add `classify_person_role()` (A3 helper)

**What**: Nova função que classifica uma pessoa como "recumbent", "standing", "transitioning" ou "unknown" com base na posição Y dos quadris nos frames recentes.

**Where**: `backend/pipelines/video/pose_features.py` (new function)

**Depends on**: T1 (`_MIN_VISIBILITY` unificado)

**Reuses**: `is_recumbent()` (Iteração 1), `hip_center()`

**Requirement**: ITER2-02

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `classify_person_role(person_frames) -> str` implementada
- [ ] `is_recumbent(frames)` → "recumbent"
- [ ] Y médio (30 frames, `hip_center`) < 0.35 → "standing"
- [ ] Caso contrário → "transitioning"
- [ ] < 10 frames válidos → "unknown"
- [ ] Teste: pessoa deitada 100 frames (Y=0.80) → "recumbent"
- [ ] Teste: pessoa em pé 100 frames (Y=0.30) → "standing"
- [ ] Teste: pessoa a levantar (Y: 0.80→0.30) → "transitioning"
- [ ] Teste: < 10 frames → "unknown"
- [ ] Teste: timeline com None frames → "unknown"
- [ ] Gate quick: sem regressão
- [ ] Test count: +5 testes

**Tests**: unit

**Gate**: quick

**Commit**: `feat(video-pose): add classify_person_role() for multi-person role dispatch`

---

### T3: Add `detect_seizure()` (B2a)

**What**: Novo detector de convulsão/espasmo via desvio padrão da velocidade angular de cotovelos (13,14) e joelhos (25,26) em janela deslizante de 60 frames.

**Where**: `backend/pipelines/video/pose_detector.py` (new function)

**Depends on**: T2 (`classify_person_role` define o papel, mas o detector é independente)

**Reuses**: `joint_angle()` (existente), `PosturalFinding` (existente), padrão de streak de `detect_postural_deviations()`

**Requirement**: ITER2-04

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `detect_seizure(frames, fps, window_frames=60, min_std=0.05, persistence_frames=30) -> list[PosturalFinding]`
- [ ] Velocidade angular: `|angle_frame_N - angle_frame_N-1|` para 4 articulações
- [ ] Janela 60 frames: `std(velocidades)` por articulação, média das 4
- [ ] Média > 0.05 por 30+ frames consecutivos → finding "SEIZURE"
- [ ] Articulação com visibilidade < 0.4 excluída (não invalida o frame)
- [ ] < 60 frames → [] (dados insuficientes)
- [ ] Teste: oscilação rítmica (Y varia ±0.03 a cada 2 frames) nos cotovelos/joelhos por 90 frames → 1 finding
- [ ] Teste: timeline sem oscilação → 0 findings
- [ ] Teste: < 60 frames → []
- [ ] Teste: articulação ocluída (vis < 0.4) → excluída, mas outras ainda contribuem
- [ ] Gate quick: sem regressão
- [ ] Test count: +4 testes

**Tests**: unit

**Gate**: quick

**Commit**: `feat(video-pose): add detect_seizure() for convulsion/spasm detection`

---

### T4: Add `detect_agitation()` (B2b)

**What**: Novo detector de agitação psicomotora via frequência de mudanças de posição (>10/min).

**Where**: `backend/pipelines/video/pose_detector.py` (new function)

**Depends on**: T2

**Reuses**: `hip_center()`, `PosturalFinding`

**Requirement**: ITER2-05

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `detect_agitation(frames, fps, window_frames=30, min_changes_per_minute=10, min_total_frames=120) -> list[PosturalFinding]`
- [ ] Divide timeline em janelas de 30 frames, calcula Y médio por janela
- [ ] Mudança = `|Y_medio_N - Y_medio_N-1| > 0.03`
- [ ] Taxa = mudanças / (total_frames/fps) * 60
- [ ] Taxa > 10 → finding "AGITATION"
- [ ] < 120 frames → [] (dados insuficientes para taxa por minuto)
- [ ] Teste: 20 mudanças em 60s → 1 finding
- [ ] Teste: 2 mudanças em 60s → 0 findings (abaixo do threshold)
- [ ] Teste: < 120 frames → []
- [ ] Teste: timeline com gaps (None) → ignora janelas vazias
- [ ] Gate quick: sem regressão
- [ ] Test count: +4 testes

**Tests**: unit

**Gate**: quick

**Commit**: `feat(video-pose): add detect_agitation() for psychomotor agitation detection`

---

### T5: Add `detect_bed_exit()` (B2c)

**What**: Novo detector de saída do leito via Y subindo sustentado + deslocamento lateral em pessoa previamente deitada.

**Where**: `backend/pipelines/video/pose_detector.py` (new function)

**Depends on**: T2 (`classify_person_role` para gate de `is_recumbent`)

**Reuses**: `is_recumbent()`, `hip_center()`, `lateral_displacement()`, `PosturalFinding`

**Requirement**: ITER2-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `detect_bed_exit(frames, fps, window_frames=60, min_delta_y=-0.10, min_delta_x=0.05, min_total_frames=120) -> list[PosturalFinding]`
- [ ] Gate: só executa se `is_recumbent(frames)` — senão devolve []
- [ ] ΔY: Y médio (últimos 30 frames) vs. Y médio (30 frames anteriores)
- [ ] ΔX: soma de `lateral_displacement()` nos mesmos 60 frames
- [ ] ΔY < -0.10 E ΔX > 0.05 → finding "BED_EXIT"
- [ ] < 120 frames → [] (dados insuficientes)
- [ ] Teste: pessoa deitada (Y≈0.8) que sobe (Y→0.5) + ΔX>0.05 ao longo de 90 frames → 1 finding
- [ ] Teste: pessoa de pé (Y≈0.3) → 0 findings (gate is_recumbent)
- [ ] Teste: pessoa deitada sem deslocamento lateral → 0 findings (ΔX insuficiente)
- [ ] Teste: < 120 frames → []
- [ ] Gate quick: sem regressão
- [ ] Test count: +4 testes

**Tests**: unit

**Gate**: quick

**Commit**: `feat(video-pose): add detect_bed_exit() for bed exit detection`

---

### T6: Refactor `select_ground_person()` with track_id persistence (A2)

**What**: Adicionar persistência de track_id ao `select_ground_person`: uma vez identificado o track_id dominante, mantê-lo ao longo da sequência a menos que desapareça por > 30 frames.

**Where**: `backend/pipelines/video/pose_features.py` (modify function + add module state)

**Depends on**: T1 (constantes), T2 (`classify_person_role` disponível, mas não depende diretamente)

**Reuses**: `dominant_track_id()` (existente), `group_poses_by_track_id()` (Iteração 1), padrão `_tracker_state` de `pose.py`

**Requirement**: ITER2-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Estado do módulo: `_ground_person_state = {"dominant_tid": None, "frames_absent": 0}`
- [ ] `reset_ground_person_state()` — limpa o estado (chamado por `reset_person_tracker`)
- [ ] Nos primeiros 60 frames: calcular track_id com maior Y médio → `dominant_tid`
- [ ] Frames seguintes: se `dominant_tid` presente → usar essa pose; se ausente → incrementar `frames_absent`
- [ ] `frames_absent > 30` → recalcular `dominant_tid` na janela recente (últimos 60 frames)
- [ ] Sem tracking (todos track_id=None) → comportamento original (Y máximo por frame)
- [ ] Teste: 2 track_ids onde Y alterna → track_id estável nos 100 frames
- [ ] Teste: track_id dominante some por 35 frames → recalcula
- [ ] Teste: track_id dominante some por 10 frames → mantém (ausência breve)
- [ ] Teste: sem tracking → comportamento original (Y máximo)
- [ ] Testes existentes de `select_ground_person` sem regressão (single-person, sem tracking)
- [ ] Gate quick: sem regressão
- [ ] Test count: +4 testes

**Tests**: unit

**Gate**: quick

**Commit**: `feat(video-pose): add track_id persistence to select_ground_person`

---

### T7: Add `analyze_all_persons()` orchestrator (A3)

**What**: Nova função que itera todas as pessoas (por track_id), classifica o papel de cada uma e despacha os detectores adequados, consolidando todos os achados.

**Where**: `backend/pipelines/video/pose_detector.py` (new function)

**Depends on**: T2 (classify_person_role), T3-T5 (detectors), T6 (select_ground_person)

**Reuses**: `group_poses_by_track_id()`, `classify_person_role()`, `validate_fall_dynamic()`, `detect_seizure()`, `detect_agitation()`, `detect_bed_exit()`, `detect_postural_deviations()`, `detect_trunk_tilt()`, `sumarizar_achados_video()`

**Requirement**: ITER2-03

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `analyze_all_persons(all_poses_per_frame, fps=30.0, joint_targets=None, fall_threshold=0.55, persistence_frames=1) -> tuple[str, float, list[PosturalFinding], dict]`
- [ ] Itera `group_poses_by_track_id()` — para cada track_id:
  - `classify_person_role()` → papel
  - "recumbent" → `detect_agitation()` + `detect_bed_exit()`
  - "standing"/"transitioning" → `validate_fall_dynamic()`
- [ ] Consolida findings de TODAS as pessoas
- [ ] Devolve resumo + pontuação + lista consolidada
- [ ] Sem tracking → fallback ao comportamento Iteração 1 (single-person)
- [ ] Teste: 1 deitado (convulsão) + 1 de pé (estático) → 1 finding "SEIZURE" atribuído ao deitado
- [ ] Teste: 1 deitado (agitação) + 1 de pé que cai → 2 findings ("AGITATION" + "FALL_DETECTED")
- [ ] Teste: single-person sem tracking → mesmo comportamento que Iteração 1
- [ ] Teste: cena vazia (0 pessoas) → sem findings
- [ ] Gate quick: sem regressão nos testes existentes
- [ ] Test count: +4 testes

**Tests**: unit

**Gate**: quick

**Commit**: `feat(video-pose): add analyze_all_persons() multi-person orchestrator`

---

### T8: Wire multi-person pipeline in `analise.py` + `cli.py`

**What**: Atualizar `_analisar_video_pose` e `cli.run` para usar `analyze_all_persons()` em vez do fluxo single-person atual. Adicionar `reset_ground_person_state()` ao `reset_person_tracker()`.

**Where**: `backend/app/analise.py` (modify `_analisar_video_pose`), `backend/pipelines/video/cli.py` (modify `run`), `backend/pipelines/video/pose.py` (modify `reset_person_tracker`)

**Depends on**: T7

**Reuses**: `analyze_all_persons()`, `group_poses_by_track_id()`, `find_pose_by_track_id()`

**Requirement**: ITER2-03, ITER2-01 (via reset)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `reset_person_tracker()` em `pose.py` chama `reset_ground_person_state()`
- [ ] `_analisar_video_pose` substitui `select_ground_person` + `classify_with_persistence` + `validate_fall_dynamic` por `analyze_all_persons()`
- [ ] Evidência usa `find_pose_by_track_id()` para o frame correto da pessoa que gerou o finding
- [ ] `sumarizar_achados_video()` estendido para reconhecer novos finding_types ("SEIZURE", "AGITATION", "BED_EXIT")
- [ ] `cli.run` atualizado para o novo fluxo (mesmo padrão de `_analisar_video_pose`)
- [ ] Teste de integração: vídeo URFD `fall-01` → resultado idêntico ao baseline (single-person)
- [ ] Teste de integração: `_analisar_video_pose` com vídeo multi-pessoa → findings por papel
- [ ] Gate full: `python -m pytest backend/tests/video/ backend/tests/app/test_analise.py -q`
- [ ] Build gate: `make test && ruff check backend`
- [ ] Test count: 554+ testes sem regressão

**Tests**: integration

**Gate**: full

**Commit**: `feat(video-pose): wire multi-person pipeline to analysis dispatch`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ──→ T2
Phase 2:  T3 ──→ T4 ──→ T5
Phase 3:  T6 ──→ T7 ──→ T8
```

Execution is strictly sequential — one task at a time, in order. 8 tasks total fits a single batch (≤ ~8 tasks) → inline execution, no sub-agents needed.

---

## Task Granularity Check

| Task | Scope | Status |
|------|-------|--------|
| T1: Unify constants | 1 file, 2 constants | ✅ Granular |
| T2: classify_person_role() | 1 function | ✅ Granular |
| T3: detect_seizure() | 1 function + tests | ✅ Granular |
| T4: detect_agitation() | 1 function + tests | ✅ Granular |
| T5: detect_bed_exit() | 1 function + tests | ✅ Granular |
| T6: select_ground_person persistence | 1 function modification | ✅ Granular |
| T7: analyze_all_persons() | 1 function + tests | ✅ Granular |
| T8: Wire in analise.py + cli.py | 3 files, cohesive change | ⚠️ OK (mesma responsabilidade: dispatch) |

## Diagram-Definition Cross-Check

| Task | Depends On (body) | Diagram Shows | Status |
|------|------------------|---------------|--------|
| T1 | None | (start) | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T2 | T3 → T4 | ✅ Match |
| T5 | T2 | T4 → T5 | ✅ Match |
| T6 | T1, T2 | T5 → T6 | ✅ Match |
| T7 | T2, T3-T5, T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Modified | Matrix Requires | Task Says | Status |
|------|-------------------|-----------------|-----------|--------|
| T1: constants | Domain logic | unit | unit | ✅ OK |
| T2: classify_person_role | Domain logic | unit | unit | ✅ OK |
| T3: detect_seizure | Domain logic | unit | unit | ✅ OK |
| T4: detect_agitation | Domain logic | unit | unit | ✅ OK |
| T5: detect_bed_exit | Domain logic | unit | unit | ✅ OK |
| T6: select_ground_person | Domain logic | unit | unit | ✅ OK |
| T7: analyze_all_persons | Domain logic | unit | unit | ✅ OK |
| T8: analise.py + cli.py | Orchestration | integration | integration | ✅ OK |
