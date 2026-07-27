# Fall Detection Fix — Correções da Fase 1

## Problem Statement

O diagnóstico forense (2026-07-27) revelou que o pipeline de detecção de quedas tem **recall = 0%** em 5 sequências de queda do URFD testadas. Três causas raiz foram identificadas com evidência experimental:

1. **Gate bloqueador `recumbent`**: `analyze_all_persons` só executa o detector de queda para pessoas `standing`/`transitioning`. Pessoas classificadas como `recumbent` (Y > 0.45) nunca passam pelo detector — mas uma pessoa que caiu está precisamente deitada no chão.
2. **Threshold de Vy incompatível**: `max_vertical_velocity` tem piso de 0.08 em coordenadas normalizadas [0-1]. A queda real (fall-01) produz Vy máximo de 0.024.
3. **CLI quebrada**: `cli.py:239` referencia variáveis não definidas (`windows`, `fall_verdict`, `tilt_findings`) → `NameError`.
4. **Threshold de amplitude muito alto**: `fall_threshold` default 0.55 é quase 2× a amplitude real de uma queda com tracking correto (0.29).

## Goals

- [ ] Recall de detecção de queda > 0% nas sequências URFD testadas (fall-01 a fall-05)
- [ ] CLI `run()` executa sem `NameError`
- [ ] Nenhum falso positivo introduzido nas sequências ADL
- [ ] Testes existentes continuam passando

## Out of Scope

| Feature | Reason |
|---------|--------|
| Normalização de Vy por altura corporal | Fase 2 |
| Máquina de estados temporal (standing→descending→on_floor) | Fase 2 |
| Redução do window_size / stride com overlap | Fase 2 |
| Uso de FPS real do vídeo | Fase 2 |
| Correção do threshold de agitation | Fase 2 |

---

## User Stories

### P1: Detector de queda executa em todas as pessoas ⭐ MVP

**User Story**: As a system, I want to run fall detection on ALL tracked persons, not only those classified as "standing", so that a person who falls and ends up on the floor is detected.

**Why P1**: É a causa raiz #1 do recall=0%. Sem esta correção, nenhuma das outras tem efeito.

**Acceptance Criteria**:

1. WHEN a person is tracked across frames THEN the system SHALL run fall detection (amplitude check → velocity validation) regardless of their classified role.
2. WHEN a person was already lying down in the FIRST 30 frames of the sequence THEN the system SHALL skip fall detection for that person (they didn't fall during this video — they started on the floor).
3. WHEN a person was standing/walking in the first 30 frames and later ends up on the floor THEN the system SHALL detect the transition as a potential fall.

**Independent Test**: Run pipeline on fall-01; verify FALL_DETECTED appears in consolidated findings.

---

### P2: Thresholds compatíveis com coordenadas normalizadas ⭐ MVP

**User Story**: As a developer, I want Vy and amplitude thresholds that match the actual signal range in normalized [0-1] coordinates so that real falls produce detectable values.

**Why P2**: Causa raiz #2. Mesmo que o detector execute, nunca detectaria o pico de Vy.

**Acceptance Criteria**:

1. WHEN `max_vertical_velocity` is called on fall-01 velocities THEN it SHALL return a non-zero value (currently returns 0.0 because floor 0.08 filters everything).
2. WHEN `classify_with_persistence` is called on fall-01 windows with `fall_threshold=0.25` THEN it SHALL return `"queda"` (currently returns `"adl"` because max amplitude 0.29 < 0.55 threshold).

**Independent Test**: `max_vertical_velocity(velocities)` returns > 0 for fall-01; `classify_with_persistence(windows, 0.25, 1)` returns `("queda", frame_idx)`.

---

### P3: CLI funcional sem NameError

**User Story**: As a user, I want `make run-video` to execute without crashing so that the batch pipeline produces evidence.

**Why P3**: Bug que impede qualquer execução do pipeline de produção.

**Acceptance Criteria**:

1. WHEN `run()` is called on a valid config THEN it SHALL complete without `NameError`.
2. WHEN the log line at `cli.py:239` executes THEN all referenced variables (`windows`, `fall_verdict`, `tilt_findings`) SHALL be defined in scope.

**Independent Test**: `run(cfg, run_id="test")` completes with exit code 0 on fall-01.

---

## Edge Cases

- WHEN a person is never detected in the first 30 frames THEN `_was_initially_recumbent` SHALL return `False` (conservative: run fall detection).
- WHEN `extract_all_keypoints` returns empty list for all frames THEN `analyze_all_persons` SHALL return `("Sem alterações detectadas.", 0.0, [], details)` without crashing.
- WHEN ADL sequence has normal walking movement THEN it SHALL NOT produce FALL_DETECTED findings.

---

## Requirement Traceability

| Requirement ID | Story | Status |
|---------------|-------|--------|
| FALLFIX-01 | P1: Detector executa em todas as pessoas | Pending |
| FALLFIX-02 | P1: Skip só se já deitado nos primeiros 30 frames | Pending |
| FALLFIX-03 | P2: Vy floor reduzido de 0.08 para 0.01 | Pending |
| FALLFIX-04 | P2: fall_threshold default reduzido de 0.55 para 0.25 | Pending |
| FALLFIX-05 | P3: CLI sem NameError | Pending |

---

## Success Criteria

- [ ] `analyze_all_persons` on fall-01 returns at least 1 FALL_DETECTED finding
- [ ] `analyze_all_persons` on adl-01 returns 0 FALL_DETECTED findings
- [ ] `cli.run(config)` completes without exceptions
- [ ] All existing tests (`make test`) pass without regression
