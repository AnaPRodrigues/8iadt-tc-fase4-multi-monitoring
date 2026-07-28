# Diagnóstico Final — Tech Challenge Fase 4
**Data**: 2026-07-27
**Branch**: `feat/f3-vitals-anomaly`
**Suíte**: 593 testes coletados

---

## 1. Matriz de Auditoria — Prometido vs. Real

| Modalidade | Capacidade | Status | Funciona? | Evidência | Gap |
|---|---|---|---|---|---|
| Vídeo | Quedas (URFD) | IMPLEMENTADO | ✅ 4/5 recall | ✅ Frame anotado + sidecar JSON | fall-05 não detectado (queda lenta); README diz 100% mas código real é 80% |
| Vídeo | Anomalias posturais (tilt, agitação, convulsão, saída do leito) | IMPLEMENTADO | ✅ Detectores existem | ✅ Frame anotado | Limiares empíricos, não calibrados contra ground truth |
| Vídeo | Estruturas cirúrgicas (Endoscapes) | IMPLEMENTADO | ✅ YOLOv8 funcional | ✅ Bboxes desenhadas | Só keyframes, não vídeo contínuo |
| Vídeo | Upload .mp4/.avi/.mov | IMPLEMENTADO | ✅ | ✅ Frame extraído | Latência de extração em CPU |
| Áudio | Respiração (ICBHI) | IMPLEMENTADO | ✅ RF 4 classes | ✅ Espectrograma | Modelo treinado sob demanda (sem persistência) |
| Áudio | Transcrição (faster-whisper) | IMPLEMENTADO | ✅ pt-BR, small | ✅ Transcript.txt | Nunca testado com fala real do grupo |
| Áudio | Termos críticos | IMPLEMENTADO | ✅ Léxico configurável | ✅ Termo destacado no texto | Busca por substring normalizada (não semântica) |
| Áudio | Fadiga vocal | PARCIAL | ⚠️ z-score degenerado | ⚠️ Sem baseline | Com 1 áudio, z-score = 0.0 sempre |
| Áudio | Sentimento | IMPLEMENTADO | ✅ Léxico local | ⚠️ Só no summary JSON | Sem artefato dedicado |
| Vitais | CTG fetal (CTU-UHB) | IMPLEMENTADO | ✅ Isolation Forest | ✅ Gráfico da janela | pH como ground truth |
| Vitais | HR + SpO2 adulto (BIDMC) | IMPLEMENTADO | ✅ Critérios clínicos | ✅ Gráfico da janela | 1 registro corrompido (bidmc19n) |
| Vitais | Pressão arterial | NÃO IMPLEMENTADO | ❌ | ❌ | Deferido (VitalDB) |
| Prescrição | Dose fora da faixa | IMPLEMENTADO | ✅ Catálogo 14 fármacos | ✅ PDF + JSON | Só faixas de dose, sem fonte ANVISA |
| Prescrição | Variação abrupta | IMPLEMENTADO | ✅ Comparação com anterior | ✅ | Depende de histórico do paciente |
| Prescrição | **Classificação ANVISA** | **NÃO IMPLEMENTADO** | ❌ | ❌ | **GAP P0 — catálogo sem categorias regulatórias** |
| Prescrição | **Princípio ativo** | **NÃO IMPLEMENTADO** | ❌ | ❌ | **GAP P0 — sem mapeamento fármaco→princípio ativo** |
| Prescrição | Fonte da informação | NÃO IMPLEMENTADO | ❌ | ❌ | Sem atribuição de fonte (ANVISA/Bulário) |
| Fusão | Risk score multimodal | IMPLEMENTADO | ✅ Peso × severidade × decay | ✅ Timeline | Severidade sempre 1.0 |
| Fusão | Histerese verde/amarelo/vermelho | IMPLEMENTADO | ✅ Stateful classifier | ✅ Testado | Banda ±0.05 |
| Fusão | Modalidade ausente explícita | IMPLEMENTADO | ✅ `missing_modalities` | ✅ | |
| Fusão | Alerta explicável | PARCIAL | ⚠️ Soma de resumos | ⚠️ | Sem breakdown por modalidade no motivo |
| Fusão | **Severity levels (INFO/LOW/MED/HIGH/CRITICAL)** | **NÃO IMPLEMENTADO** | ❌ | ❌ | **GAP P0** |
| Frontend | Painel por modalidade | IMPLEMENTADO | ✅ React + Vite | ✅ | Mostra resumo + pontuação |
| Frontend | Linha do tempo de risco | IMPLEMENTADO | ✅ Recharts | ✅ | Tooltip com eventos |
| Frontend | Drill-down de evidência | IMPLEMENTADO | ✅ | ✅ | |
| Frontend | **Info ANVISA na prescrição** | **NÃO IMPLEMENTADO** | ❌ | ❌ | **GAP P1** |
| Evidência | Contrato comum | PARCIAL | ⚠️ Funcional mas magro | ⚠️ | **Sem campos: severity, confidence, timestamp, patient_id, status, event_type** |

---

## 2. GAPS P0 (Obrigatórios — bloqueiam promessas centrais)

### P0-1: Prescrição — Classificação ANVISA e Princípio Ativo
**O que falta**: O catálogo (`prescription/catalog.py`) tem 14 fármacos com faixas de dose, mas ZERO informação regulatória. Não há categoria ANVISA (A1/A2/B1/C1), não há princípio ativo, não há fonte.

**Impacto**: A prescrição promete "validação ANVISA" mas não entrega nada além de faixa de dose. Perda de nota significativa.

**Solução**: Expandir `DrugRange` para incluir `active_ingredient`, `control_category`, `is_controlled`, `source`. Preencher com dados reais das listas oficiais da ANVISA.

### P0-2: Fusão — Níveis de Severidade Diferenciados
**O que falta**: Todos os eventos entram com `severity = 1.0`. Uma queda não pesa mais que uma postura inclinada.

**Impacto**: O risk score não reflete a gravidade real dos eventos. Dezenas de eventos leves podem somar o mesmo que um evento crítico.

**Solução**: Adicionar níveis INFO/LOW/MEDIUM/HIGH/CRITICAL no contrato de evidência e mapeá-los para pesos de severidade na fusão.

### P0-3: Contrato de Evidência — Campos Essenciais
**O que falta**: O `Evidence` dataclass tem: feature, run_id, evidence_id, source_record_id, artifact_path, sidecar_path. Faltam: modality, event_type, severity, confidence, timestamp, patient_id, status (positive/negative/unavailable/inconclusive).

**Impacto**: A fusão e o frontend não têm informação suficiente para explicar adequadamente os alertas.

**Solução**: Adicionar campos opcionais ao contrato (sem quebrar as pipelines existentes).

---

## 3. GAPS P1 (Alta Prioridade — melhoram demonstração)

### P1-1: Frontend — Exibir Classificação ANVISA
O painel de prescrição mostra resumo + pontuação, mas sem a categoria regulatória ou princípio ativo.

### P1-2: Evidência de Queda — JSON Rico
O JSON atual tem campos mínimos. Adicionar breakdown: vertical_motion, posture_change, persistence.

### P1-3: Fusão — Explicação Contextual do Alerta
O motivo do alerta é uma concatenação simples. Melhorar para: "Queda confirmada (12s atrás) + SpO2 baixa (20s atrás) + 'falta de ar' (8s atrás)".

### P1-4: Áudio — Evidência Consolidada
Juntar transcrição + termos + fadiga + sentimento num único sidecar JSON.

### P1-5: Documentação — Alinhar README e Relatório
Remover claims não suportados (ex: 100% URFD recall quando é 80%).

---

## 4. O Que NÃO Alterar

| Componente | Motivo |
|---|---|
| `backend/pipelines/video/pose.py` (MediaPipe + tracking) | Funcional, complexo, testado |
| `backend/pipelines/video/pose_features.py` | Funcional, ~28KB de features testadas |
| `backend/pipelines/video/pose_detector.py` | Detectores funcionais, multi-pessoa ok |
| `backend/pipelines/audio/icbhi_classifier.py` | RF funcional, class_weight balanced |
| `backend/pipelines/audio/transcribe.py` | faster-whisper integrado |
| `backend/pipelines/vitals/` (todo o pipeline) | Funcional, bem testado |
| `backend/pipelines/fusion/hysteresis.py` | Lógica correta, testada |
| `backend/pipelines/fusion/risk_engine.py` | Fórmula correta, testada |
| `backend/app/` (rotas, DB, repositório) | Arquitetura estável |
| `backend/aws/` (adapters) | Padrão adapter funcional |
| `frontend/` (React + Vite) | Estrutura estável, funcional |
| Estrutura de pastas | Organizada e documentada |

---

## 5. Plano de Execução P0/P1 (Ordem)

### Bloco P0 (3-4 horas)

1. **P0-3**: Expandir contrato de evidência (`common/evidence.py`) — adicionar campos opcionais
2. **P0-1**: Expandir catálogo de prescrição com ANVISA + princípio ativo
3. **P0-2**: Adicionar níveis de severidade na fusão

### Bloco P1 (2-3 horas)

4. **P1-1**: Frontend — exibir info ANVISA
5. **P1-2**: Vídeo — enriquecer evidência de queda
6. **P1-3**: Fusão — explicação contextual
7. **P1-4**: Áudio — evidência consolidada
8. **P1-5**: Documentação — alinhar

---

## 6. Riscos de Perda de Nota

| Risco | Nível | Mitigação |
|---|---|---|
| ANVISA não implementado | ALTO | P0-1 cobre |
| Severidade indiferenciada na fusão | ALTO | P0-2 cobre |
| Evidência sem campos de status | MÉDIO | P0-3 cobre |
| README com métricas infladas (100% URFD) | MÉDIO | P1-5 cobre |
| Fadiga vocal degenerada (z-score=0) | BAIXO | Documentado como limitação |
| Pressão arterial ausente | BAIXO | Deferido com justificativa |
| Áudio de consulta sem teste real | BAIXO | Documentado, roteiro existe |
