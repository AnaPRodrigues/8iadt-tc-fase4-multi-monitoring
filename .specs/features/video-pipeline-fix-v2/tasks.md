# Video Pipeline Fix v2 — Tasks

## Fase 1: Correções do detector de queda

### T1 — Filtrar n_pessoas_reais (VIDEO-01)
- **File**: `pose_detector.py:analyze_all_persons`
- **Change**: Contar apenas tracks com ≥5% cobertura, não todos
- **Gate**: `make test` verde, cam4 detecta queda
- **Test**: `test_n_pessoas_filtra_ghosts`

### T2 — Score multi-fator (VIDEO-02)
- **File**: `pose_detector.py:analyze_all_persons`
- **Change**: score = (Vy_score + tilt_score + disp_score) / 3, remover cap de 0.5
- **Gate**: score != 0.5000 para quedas reais
- **Test**: `test_score_nao_e_cap_fixo`

### T3 — Análise postural no API path (VIDEO-03)
- **File**: `app/analise.py:_analisar_video_pose`
- **Change**: Executar detect_trunk_tilt + detect_postural_deviations após analyze_all_persons
- **Gate**: fisioterapia.mp4 produz findings posturais
- **Test**: `test_fisioterapia_produz_achados_posturais`

### T4 — Evidência temporal (VIDEO-04)
- **File**: `pose_detector.py:save_fall_evidence`
- **Change**: Adicionar before_frame, event_frame, after_frame ao metadata
- **Gate**: sidecar JSON contém os 3 timestamps
- **Test**: `test_evidencia_temporal_tem_before_after`

## Fase 2: Robustez

### T5 — Corrupção de vídeo (VIDEO-05)
- **File**: `app/analise.py:_extrair_frames`
- **Change**: Contar decode_errors, reportar video_integrity
- **Gate**: vídeo corrompido reporta "degraded"
- **Test**: `test_video_corrompido_reporta_degraded`

## Gate Check Commands

| Level | Command |
|-------|---------|
| Quick | `pytest backend/tests/video/ -q --tb=short` |
| Full  | `pytest backend/tests/video/ backend/tests/app/test_analise.py -q --tb=short` |
| Build | `pytest backend/tests/ -q --tb=short` |
