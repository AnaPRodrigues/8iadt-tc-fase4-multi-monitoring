# Video Pipeline Fix v2 — Spec

**Feature**: `video-pipeline-fix-v2`
**Date**: 2026-07-27
**Base**: Diagnóstico de features reais (cam1, cam3, cam4, fisioterapia)

## Problem Statement

A pipeline de vídeo tem 4 problemas confirmados por diagnóstico de features reais:

1. **score=0.5000** é um CAP físico (`min(max_vy, 0.5)`), não confiança. Enganoso.
2. **n_pessoas_reais** conta ghosts (track_ids com <5% cobertura), ativando thresholds multi-pessoa mais restritivos e causando falsos negativos (ex: cam4).
3. **Análise postural ausente** no caminho de upload da API — `detect_trunk_tilt` e `detect_postural_deviations` nunca são chamados.
4. **Evidência de queda** é centrada num único frame, sem contexto temporal (BEFORE/AFTER).

## Goals

- [ ] **VIDEO-01**: `n_pessoas_reais` conta apenas tracks com ≥5% de cobertura válida
- [ ] **VIDEO-02**: `score` reflete severidade multi-fator (Vy + tilt + deslocamento), não apenas Vy capado
- [ ] **VIDEO-03**: API path executa análise postural (tilt, ângulos, simetria)
- [ ] **VIDEO-04**: Evidência temporal (BEFORE/EVENT/AFTER) para quedas
- [ ] **VIDEO-05**: Detecção de corrupção de vídeo reporta `ANALYSIS_DEGRADED`

## Acceptance Criteria

### VIDEO-01: n_pessoas_reais filtrado
**WHEN** `group_poses_by_track_id` produz 14 track_ids mas só 2 têm ≥5% cobertura
**THEN** `n_pessoas_reais = 2` (não 14)
**AND** thresholds single-person (min_vy=0.02, tilt=25°) são usados

### VIDEO-02: Score multi-fator
**WHEN** uma queda é confirmada
**THEN** score = média ponderada de (Vy_score, tilt_score, displacement_score)
**AND** `score` nunca é exatamente 0.5 por cap artificial

### VIDEO-03: Análise postural no upload
**WHEN** um vídeo é enviado via API (não CLI)
**THEN** `detect_trunk_tilt` e `detect_postural_deviations` são executados
**AND** findings de fisioterapia aparecem no resultado

### VIDEO-04: Evidência temporal
**WHEN** uma queda é detectada
**THEN** a evidência inclui before_frame, event_frame, after_frame no metadata

### VIDEO-05: Corrupção reportada
**WHEN** ≥5% dos frames têm erro de decode
**THEN** o resultado inclui `video_integrity: "degraded"` e `decode_errors: N`
