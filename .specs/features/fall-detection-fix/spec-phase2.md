# Fall Detection Fix — Fase 2 (Robustez)

## Problem Statement

A Fase 1 elevou o recall de 0% para 80% (4/5 no URFD), mas fall-05 continua não detetado. A investigação revelou que a queda em fall-05 é mais lenta (espalhada por ~60 frames), com amplitude de centro de massa abaixo do threshold, mas com Vy e deslocamento total fortes. O sistema atual exige que o Estágio 1 (amplitude) passe para chegar ao Estágio 2 (velocidade) — uma única via de deteção.

Além disso, os thresholds são em coordenadas normalizadas absolutas, o que os torna dependentes da resolução e distância da câmara. O `detect_agitation` produz falsos positivos universais (threshold de 10 mudanças/min é atingido por qualquer movimento). E o FPS é hardcoded como 30.

## Goals

- [ ] Recall de queda ≥ 80% mantido (sem regressão em fall-01..04)
- [ ] fall-05 passa a ser detectado
- [ ] `detect_agitation` não dispara em ADL normal (walking)
- [ ] Vy normalizado por altura corporal (scale-independent)
- [ ] FPS real extraído do vídeo quando disponível

## Out of Scope

| Feature | Reason |
|---------|--------|
| Máquina de estados temporal completa | Fase 3 |
| Modelo temporal (LSTM/TCN) | Fase 3 |
| Janelas com overlap | Complexidade adicional; Vy path resolve fall-05 |

---

## User Stories

### P1: Via paralela de deteção por Vy ⭐ MVP

**User Story**: As a system, I want a Vy-primary fall detection path that runs even when the amplitude check fails, so that slower falls (like fall-05) are still detected.

**Why P1**: fall-05 tem max_amplitude=0.19 < 0.25 mas max_vy=0.06 e total_dy=0.40 — o sinal de velocidade é forte. Sem esta via paralela, quedas lentas nunca são detectadas.

**Acceptance Criteria**:

1. WHEN Stage 1 (amplitude) returns "adl" THEN the system SHALL check if max_vy ≥ 0.03 AND total_displacement ≥ 0.25 as a Vy-primary fall path.
2. WHEN Vy-primary path detects a fall THEN the system SHALL validate it through the existing Stage 2 (validate_fall_dynamic).
3. WHEN `analyze_all_persons` runs on fall-05 THEN it SHALL return at least 1 FALL_DETECTED finding.

**Independent Test**: `analyze_all_persons` on fall-05 returns FALL_DETECTED.

---

### P2: Vy normalizado por altura corporal

**User Story**: As a developer, I want Vy expressed in body-heights per frame instead of absolute normalized coordinates, so that thresholds are independent of camera distance and resolution.

**Why P2**: Remove dependência de escala. Uma pessoa próxima da câmara tem o dobro do tamanho em coordenadas normalizadas — o mesmo movimento produz Vy diferente.

**Acceptance Criteria**:

1. WHEN `vertical_velocity_robust` is called THEN the system SHALL also provide a body-height-normalized variant (Vy / torso_height).
2. WHEN a person is at different distances from the camera THEN the normalized Vy SHALL be comparable (same physical movement → same normalized Vy).

**Independent Test**: `vy_normalized = vy_raw / avg_torso_height` produces consistent values across different sequences.

---

### P3: Threshold de agitation corrigido

**User Story**: As a clinician, I want agitation alerts only for genuinely abnormal movement rates, not for normal walking.

**Why P3**: O threshold atual de 10 mudanças/min classifica walking normal (20-36 mudanças/min) como "agitação psicomotora" — falso positivo universal.

**Acceptance Criteria**:

1. WHEN `detect_agitation` runs on ADL sequences (walking) THEN it SHALL NOT produce AGITATION findings.
2. WHEN `detect_agitation` runs on a sequence with genuine agitation (>40 mudanças/min) THEN it SHALL produce AGITATION findings.

**Independent Test**: ADL sequences (adl-01..05) return 0 AGITATION findings.

---

### P4: FPS real do vídeo

**User Story**: As a developer, I want the system to use the video's actual FPS instead of assuming 30, so that time-based calculations are accurate.

**Why P4**: FPS hardcoded como 30 distorce durações e taxas. Um vídeo de 15fps tem metade dos frames para a mesma janela temporal.

**Acceptance Criteria**:

1. WHEN a video file is uploaded THEN the system SHALL extract and use its actual FPS from cv2.CAP_PROP_FPS.
2. WHEN FPS cannot be determined THEN the system SHALL default to 30.0 with a log warning.

**Independent Test**: Video with known FPS produces correct duration in findings.

---

### P5: Testes unitários para `was_initially_recumbent`

**User Story**: As a developer, I want dedicated unit tests for `was_initially_recumbent` so that regressions in the recumbent gate are caught at the unit level.

**Why P5**: Gap documentado pelo Verifier — a função só é testada indiretamente via integração.

**Acceptance Criteria**:

1. WHEN a person has Y > 0.65 in the first 30 frames THEN `was_initially_recumbent` SHALL return True.
2. WHEN a person has Y < 0.65 in the first 30 frames THEN `was_initially_recumbent` SHALL return False.
3. WHEN there are fewer than 5 valid frames in the first 30 THEN `was_initially_recumbent` SHALL return False.

---

## Edge Cases

- WHEN torso height cannot be computed (all landmarks occluded) THEN Vy normalization SHALL fall back to raw Vy.
- WHEN FPS is 0 or negative THEN the system SHALL default to 30.0.
- WHEN both amplitude AND Vy-primary paths fail THEN the system SHALL return "adl" (no fall).

---

## Requirement Traceability

| Requirement ID | Story | Status |
|---------------|-------|--------|
| FALLFIX2-01 | P1: Via paralela Vy | Pending |
| FALLFIX2-02 | P2: Vy normalizado | Pending |
| FALLFIX2-03 | P3: Threshold agitation | Pending |
| FALLFIX2-04 | P4: FPS real | Pending |
| FALLFIX2-05 | P5: Testes was_initially_recumbent | Pending |

---

## Success Criteria

- [ ] fall-05 detected as FALL_DETECTED
- [ ] fall-01..04 still detected (no regression)
- [ ] adl-01..05 no AGITATION findings
- [ ] adl-01..05 no FALL_DETECTED findings (no regression)
- [ ] `make test` passes with 0 failures
