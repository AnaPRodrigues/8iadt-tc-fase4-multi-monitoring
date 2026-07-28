# Final Fix — Correção das Promessas Centrais do Sistema

**Feature**: `final-fix`
**Data**: 2026-07-27
**Branch**: `feat/f3-vitals-anomaly`
**Estado atual**: 590 testes, 0 falhas

---

## Problem Statement

O sistema funciona estruturalmente (API, DB, frontend, pipelines), mas tem **gaps entre o que promete e o que entrega** em 4 áreas:

1. **Vídeo**: Bugs de FPS scaling e descontinuidade de landmarks degradam a deteção de quedas em vídeos com FPS ≠ 30.
2. **Prescrição**: O catálogo tem doses mas zero classificação ANVISA (A1/A2/B1/C1), zero princípios ativos, zero fontes — o relatório promete "validação ANVISA" mas não entrega.
3. **Fusão**: Severidade indiferenciada (todos eventos = 1.0) e evidência sem campos de status.
4. **Contrato de evidência**: Faltam campos semânticos (severity, status, modality, confidence).

## Goals

- [ ] **Vídeo**: Corrigir FPS scaling, eliminar descontinuidade hip→upper_body, ajustar thresholds, ghost filter adaptativo.
- [ ] **Prescrição**: Adicionar classificação ANVISA real (A1/A2/A3/B1/B2/C1/C5), princípio ativo, fonte.
- [ ] **Fusão**: Níveis de severidade (INFO/LOW/MEDIUM/HIGH/CRITICAL) + explicação contextual do alerta.
- [ ] **Evidência**: Campos severity, confidence, status, modality, event_type, patient_id no contrato.
- [ ] **Áudio**: Evidência consolidada (JSON único com transcrição + termos + fadiga).
- [ ] **Frontend**: Exibir ANVISA, severidade, evidência rica.
- [ ] **Documentação**: Alinhar README/relatório com realidade.

## Out of Scope

- Reescrever detectores de queda
- Treinar novos modelos
- Adicionar pressão arterial (VitalDB — trabalho futuro)
- Disartria (sem dataset — trabalho futuro)
- Alterar arquitetura (FastAPI, SQLite, React)

---

## User Stories

### P0-1: Evidência com campos semânticos
**AS** sistema de fusão **I WANT** campos severity/status/confidence no contrato **SO THAT** o risk score reflete a gravidade real dos eventos.

### P0-2: Deteção de quedas robusta
**AS** operador **I WANT** deteção de quedas confiável independente do FPS **SO THAT** vídeos de qualquer fonte produzem resultados corretos.

### P0-3: Validação ANVISA na prescrição
**AS** médico **I WANT** ver a categoria regulatória e princípio ativo do medicamento **SO THAT** sei se é controlado e qual a fonte da informação.

### P0-4: Fusão com severidade diferenciada
**AS** equipe médica **I WANT** que queda pese mais que postura inclinada no risk score **SO THAT** o alerta reflete gravidade real.

### P1-1: Frontend com info completa
**AS** médico **I WANT** ver classificação ANVISA, severidade e evidência rica no painel **SO THAT** tenho contexto completo para decidir.

---

## Acceptance Criteria

### VIDEO-01: FPS scaling
**WHEN** um vídeo de 120fps é processado **THEN** Vy é corretamente normalizado (×4) e o threshold de queda funciona.

### VIDEO-02: Sem descontinuidade de landmarks
**WHEN** o quadril é ocluído **THEN** Vy é marcado como `None` (não usa upper_body como fallback).

### VIDEO-03: Ghost filter usa mínimo de frames
**WHEN** y_range é calculado **THEN** só filtra se ≥10 pontos válidos de quadril.

### PRESC-01: Catálogo ANVISA
**WHEN** um medicamento é validado **THEN** o resultado inclui active_ingredient, control_category, is_controlled, source.

### PRESC-02: Fonte da informação
**WHEN** a dose é validada **THEN** o resultado indica "ANVISA — Bulário Eletrônico" ou "não verificado".

### FUSION-01: Severity levels
**WHEN** eventos de modalidades diferentes contribuem **THEN** CRITICAL pesa 1.0, HIGH 0.7, MEDIUM 0.45, LOW 0.2, INFO 0.05.

### FUSION-02: Explicação contextual
**WHEN** um alerta é gerado **THEN** o motivo inclui tempos relativos (ex.: "queda há 12s").

### AUDIO-01: Evidência consolidada
**WHEN** um áudio de consulta é analisado **THEN** um JSON único contém transcrição + termos + fadiga + sentimento.
