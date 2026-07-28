# Final Fix — Design

**Feature**: `final-fix`
**Date**: 2026-07-27
**Branch**: `feat/f3-vitals-anomaly`

## Architecture

Alterações aditivas sobre a arquitetura existente. Nenhum componente novo, nenhuma refatoração estrutural.

```
Evidência (common/evidence.py)
    ↓ novos campos: severity, status, confidence, modality
    ↓
Pipelines (video, audio, vitals, prescription)
    ↓ cada pipeline preenche os novos campos
    ↓
Fusão (app/servico.py → risk_engine.py)
    ↓ severity_weight() modula o risk score
    ↓
Frontend (React)
    ↓ exibe ANVISA, severity, evidência rica
```

## Decisions

### D-001: Campos opcionais no contrato de evidência
**Decision**: Adicionar `severity`, `confidence`, `status`, `modality`, `event_type`, `patient_id`, `timestamp` como parâmetros opcionais (default vazio/zero) em `save_evidence()`.
**Reason**: Não quebrar pipelines existentes que chamam `save_evidence()` sem estes campos.
**Trade-off**: Campos vazios até cada pipeline ser atualizado — a fusão trata missing como MEDIUM/positive.

### D-002: Severity levels mapeados para pesos
**Decision**: INFO→0.05, LOW→0.2, MEDIUM→0.45, HIGH→0.7, CRITICAL→1.0.
**Reason**: Escala não-linear dá mais peso a eventos graves. Queda (CRITICAL) pesa 20× mais que INFO.
**Trade-off**: Valores calibrados heuristicamente, não derivados de dados clínicos.

### D-003: Catálogo ANVISA como dados embedados
**Decision**: Dados regulatórios no próprio `catalog.py`, sem ficheiro externo.
**Reason**: 24 fármacos é um volume pequeno; ficheiro YAML externo adicionaria complexidade de parsing sem ganho.
**Trade-off**: Para expandir além de ~50 fármacos, migrar para ficheiro de dados.

### D-004: FPS scaling corrigido em validate_fall_dynamic
**Decision**: `_fps_scale_vd = max(fps, 1.0) / 30.0` (antes era `30.0 / max(fps, 1.0)`).
**Reason**: A 120fps, o delta Y por frame é 4× menor; multiplicar por 4 compensa. O código anterior dividia por 4, subestimando Vy em 16×.
**Trade-off**: Nenhum — é correção de bug, não mudança de design.

### D-005: Sem fallback hip→upper_body no Vy
**Decision**: `vertical_velocity_robust` usa apenas quadril; sem fallback para upper_body.
**Reason**: O nariz/ombros têm Y muito diferente do quadril (~0.1-0.2 vs ~0.4-0.7), gerando spike artificial.
**Trade-off**: Frames com quadril ocluído ficam sem Vy — a persistência temporal (max_gap=5) cobre lacunas curtas.

## Componentes Não Alterados

| Componente | Motivo |
|---|---|
| `pose.py` (MediaPipe, tracking) | Funcional, complexo, bem testado |
| `pose_features.py:windowed_features` | Algoritmo correto |
| `pose_features.py:group_poses_by_track_id` | Tracking correto |
| `pose_detector.py:analyze_all_persons` (estrutura) | Só ajustes pontuais |
| `icbhi_classifier.py`, `transcribe.py` | Funcionais |
| `vitals/` (todo) | Funcional, bem testado |
| `hysteresis.py` | Lógica correta |
| `app/` (rotas, DB, repositório) | Arquitetura estável |
| `frontend/` (estrutura React) | Estável |
