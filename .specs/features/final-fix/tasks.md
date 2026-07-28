# Final Fix — Tasks

**Feature**: `final-fix`
**Spec**: `spec.md`

---

## Fase 1: Fundação (Contrato de Evidência)

### T1 — Expandir `common/evidence.py`
- [x] Adicionar campos: modality, event_type, severity, confidence, timestamp, patient_id, status
- [x] Adicionar `severity_weight()` para mapear severity → peso numérico
- [x] Adicionar enum `SEVERITY_LEVELS` e `ANALYSIS_STATUS`
- **Gate**: `make test` verde, imports de `common.evidence` intactos
- **Commit**: `feat(evidence): adicionar campos semânticos ao contrato de evidência`

---

## Fase 2: Correções por Pipeline

### T2 — Vídeo: FPS scaling
- [x] `pose_detector.py:564`: `30/fps` → `fps/30`
- **Gate**: teste de Vy com FPS=120 produz valores 4× maiores que antes

### T3 — Vídeo: Eliminar descontinuidade hip→upper_body
- [ ] `pose_features.py:238-240`: remover fallback para `_upper_body_center` no `vertical_velocity_robust`
- **Gate**: Vy=None quando quadril ocluído (não spike artificial)

### T4 — Vídeo: Ghost filter adaptativo
- [ ] `pose_detector.py:912-918`: exigir ≥10 pontos válidos para aplicar y_range < 0.10
- **Gate**: objetos com <10 deteções de quadril não são filtrados

### T5 — Vídeo: Vy-primary threshold
- [ ] `pose_detector.py:919`: `0.04` → `0.02`
- **Gate**: caminho Vy-primary usa mesmo threshold que caminho normal

### T6 — Prescrição: Catálogo ANVISA
- [ ] Expandir `catalog.py` com `DrugRange` contendo active_ingredient, control_category, is_controlled, source
- [ ] Adicionar 20+ fármacos com dados reais ANVISA
- [ ] Atualizar `models.py` (PrescriptionRecord, DrugRange)
- [ ] Atualizar `parser.py` e `rules.py` para incluir info regulatória
- **Gate**: `check_dose_range` devolve também control_category e active_ingredient

### T7 — Áudio: Evidência consolidada
- [ ] `analise.py:_analisar_audio_consulta`: gerar JSON único com todos os achados
- [ ] Adicionar severity levels aos eventos de áudio
- **Gate**: sidecar JSON contém transcription, critical_terms, vocal_fatigue, sentiment

---

## Fase 3: Fusão

### T8 — Fusão: Severity levels
- [ ] `servico.py:_eventos_do_paciente`: usar `severity_weight()` do contrato
- [ ] `risk_engine.py`: peso × severity_weight × decay
- **Gate**: queda (CRITICAL) contribui 20× mais que INFO

### T9 — Fusão: Explicação contextual
- [ ] `servico.py:_motivo_clinico`: incluir tempos relativos
- **Gate**: motivo contém "há X segundos"

---

## Fase 4: Frontend + Documentação

### T10 — Frontend: Exibir ANVISA
- [ ] `PainelModalidade.jsx`: mostrar control_category, active_ingredient
- [ ] `PacienteDetalhe.jsx`: severity no drill-down
- **Gate**: painel de prescrição mostra "B1 — Psicotrópicos"

### T11 — Documentação
- [ ] `README.md`: corrigir claims (100% → 80% URFD), adicionar ANVISA
- [ ] `relatorio-tecnico.md`: sincronizar §3.4, §4, §7 com realidade
- **Gate**: documento reflete o que o código entrega

---

## Commits Planeados

| # | Arquivos | Mensagem |
|---|----------|----------|
| 1 | `common/evidence.py` | `feat(evidence): adicionar campos semânticos ao contrato` |
| 2 | `pipelines/video/pose_detector.py` | `fix(video): corrigir FPS scaling invertido em validate_fall_dynamic` |
| 3 | `pipelines/video/pose_features.py` | `fix(video): eliminar descontinuidade hip→upper_body no Vy` |
| 4 | `pipelines/video/pose_detector.py` | `fix(video): ghost filter adaptativo + Vy-primary threshold` |
| 5 | `pipelines/prescription/{catalog,models,parser,rules}.py` | `feat(prescription): classificação ANVISA + princípio ativo` |
| 6 | `app/analise.py` | `feat(audio): evidência consolidada de consulta` |
| 7 | `app/servico.py`, `pipelines/fusion/risk_engine.py` | `feat(fusion): severity levels + explicação contextual` |
| 8 | `frontend/src/components/PainelModalidade.jsx`, `frontend/src/formatos.js` | `feat(frontend): exibir ANVISA e severidade` |
| 9 | `README.md`, `docs/relatorio-tecnico.md` | `docs: alinhar com realidade do sistema` |
