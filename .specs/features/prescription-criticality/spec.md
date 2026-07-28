# Prescription Criticality — Spec

**Feature**: `prescription-criticality`
**Scope**: Medium (3 files, 5 tasks)
**Base**: `.specs/features/final-fix/`

## Problem Statement

O módulo `rules.py` avalia apenas dose (faixa terapêutica) e variação abrupta (mesmo fármaco). Não deteta quando há substituição por um fármaco de maior criticidade — ex.: dipirona (risco 1) → morfina (risco 3). Isto é clinicamente relevante para medicamentos de Alta Vigilância (ISMP).

## Goals

- [ ] **PRESC-10**: `DrugRange.criticality` (int 1-3) classifica o risco do fármaco
- [ ] **PRESC-11**: `check_high_risk_substitution` deteta saltos de ≥2 níveis entre fármacos diferentes
- [ ] **PRESC-12**: `evaluate_prescription` orquestra as 3 regras por ordem de gravidade
- [ ] **PRESC-13**: Testes existentes sem regressão

## Acceptance Criteria

### PRESC-10: DrugRange.criticality
**WHEN** `lookup("dipirona")` é chamado **THEN** `criticality == 1`
**WHEN** `lookup("tramadol")` é chamado **THEN** `criticality == 2`
**WHEN** `lookup("morfina")` é chamado **THEN** `criticality == 3`
**WHEN** `lookup("fentanil")` é chamado **THEN** `criticality == 3`

### PRESC-11: check_high_risk_substitution
**WHEN** previous=dipirona(crit=1), current=morfina(crit=3) **THEN** `kind="substituicao_critica"`
**WHEN** previous=morfina(crit=3), current=fentanil(crit=3) **THEN** `kind="normal"`
**WHEN** previous=None **THEN** `kind="normal"`
**WHEN** previous e current são o mesmo fármaco **THEN** `kind="normal"`
**WHEN** fármaco fora do catálogo **THEN** `kind="sem_referencia"`

### PRESC-12: evaluate_prescription
**WHEN** há dose_fora_de_faixa E substituicao_critica **THEN** devolve dose_fora_de_faixa primeiro (mais grave)
**WHEN** não há anomalias **THEN** devolve kind="normal"

### PRESC-13: Regressão
**WHEN** `make test` é executado **THEN** todos os testes existentes em `tests/prescription/` passam
