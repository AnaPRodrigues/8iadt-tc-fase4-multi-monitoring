# Video Analysis (F1) Validation

**Date**: 2026-07-22
**Spec**: `.specs/features/video-analysis/spec.md`
**Diff range**: `0ac6b8a..HEAD` (branch `feat/f3-vitals-anomaly`)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status  | Notes |
| ---- | ------- | ----- |
| T1 `pose_loader.py` | ✅ Done | commit `c49be7f` |
| T2 `pose.py` | ✅ Done | commit `de572fe` |
| T3 `pose_features.py` | ✅ Done | commit `7c72a56` |
| T4 `pose_detector.py` | ✅ Done | commit `5f30611` |
| T5 `pose_evaluate.py` | ✅ Done | commit `43be52f` |
| T6 `object_loader.py` | ✅ Done | commit `c4eeed9` |
| T7 `object_finetune.py` | ✅ Done | commit `0a09db4` |
| T8 `object_detector.py` | ✅ Done | commit `a0fe433` |
| T9 `object_evaluate.py` | ✅ Done | commit `12aab49` |
| T10 `adapters.py` | ✅ Done | commit `d3d6556` |
| T11 `handler.py` | ✅ Done | commit `dd0b166` |
| T12 `infra.py` | ✅ Done | commit `2c0032c` |
| T13 `report.py` | ✅ Done | commit `2b07570` |

All 13 tasks present and committed. `git log --oneline 0ac6b8a..HEAD` shows all commits; `git status` at session start and after full test run is clean (no uncommitted changes).

---

## Spec-Anchored Acceptance Criteria

### P1: Raia pose — detecção de queda vs. ADL (URFD + MediaPipe Pose)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| VIDEO-01: carga de sequência URFD + extração de keypoints | `Sequence` com `seq_id`/`label`/frames em ordem numérica; `PoseFrame` com 33 landmarks reais | `backend/tests/video/test_pose_loader.py:14-19` — `seq.label == "fall"`, `len(seq.frame_paths) == 160`; `backend/tests/video/test_pose.py:61-70` — `len(pose_frame.landmarks) == 33` | ✅ PASS |
| VIDEO-02: métricas de movimento por janela (amplitude/velocidade/assimetria) | Valores batendo com cálculo geométrico manual do centro de massa | `backend/tests/video/test_pose_features.py:46-54` — `windows[0].center_of_mass_amplitude == esperado` (via `math.dist`); `:84-92` — `asymmetry == pytest.approx(0.4)` | ✅ PASS |
| VIDEO-03: classificação queda vs ADL por threshold | "queda" se **qualquer** janela excede threshold (`>`, não `>=`); "adl" caso contrário | `backend/tests/video/test_pose_detector.py:32-41` — `classify_sequence(...) == "queda"` / `"adl"`; `:48-53` — limiar exatamente igual não classifica como queda (`== "adl"`) | ✅ PASS |
| VIDEO-04: precision/recall/F1 da raia pose vs rótulo real | `predicted=="queda"` mapeado contra `label=="fall"`; support/precision/recall exatos | `backend/tests/video/test_pose_evaluate.py:19-23` — `report.precision == 0.5`, `report.recall == 0.5`, `report.support == 2` | ✅ PASS |
| VIDEO-05: evidência de queda (frame anotado + metadados) | Artefato + sidecar no disco com `seq_id`/`event_frame`/`score` corretos | `backend/tests/video/test_pose_detector.py:63-83` — `evidence.artifact_path.is_file()`, `sidecar["metadata"]["seq_id"] == "fall-01"`, `["event_frame"] == 50`, `["score"] == 0.87` | ✅ PASS |

### P2: Raia objeto — detecção de estruturas críticas (Endoscapes + YOLOv8/Rekognition)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| VIDEO-06: carga de frame + anotação COCO real | Caixas reais das 6 classes, mapeadas por `category_id`→nome via `categories` (não por índice) | `backend/tests/video/test_object_loader.py:21-31` — caixa `calot_triangle` bate com `(453.0, 208.0, 124.0, 55.0)`; `:42-61` — mapeamento por `id` fora de ordem sequencial produz nome correto (`"tool"`) | ✅ PASS |
| VIDEO-07: detecção via `ImageAnalyzer` (YOLOv8 local / Rekognition cloud) | Local: bbox+classe+confiança reais com pesos fine-tuned; cloud: adapter registrado e Lambda real disparado por evento S3 real | `backend/tests/video/test_object_detector.py:19-36` — detecções reais com classes válidas de `finetuned_weights`; `backend/tests/video/test_video_adapters.py:39-44` — `get_image_analyzer("local")` devolve `YoloImageAnalyzer`; `backend/tests/integration/test_video_infra.py:95-106` — upload real dispara Lambda de verdade (via CloudWatch Logs) | ✅ PASS |
| VIDEO-08: precision/recall/F1 por classe vs COCO real (IoU) | IoU alto conta como acerto, IoU baixo não conta, classe ausente tem `support=0`/métricas `None` | `backend/tests/video/test_object_evaluate.py:9-32` — IoU alto → `precision==1.0`/`recall==1.0`; `:34-57` — IoU baixo → `precision==0.0`/`recall==0.0`; `:60-83` — `support==0`, `precision is None` | ✅ PASS |
| VIDEO-09: evidência de estrutura crítica (frame + metadados) | Evidência gerada só quando há `cystic_artery`/`cystic_duct`/`cystic_plate`; ausência de estrutura crítica não gera evidência | `backend/tests/video/test_object_detector.py:47-64` — sidecar `metadata.detections` contém só a detecção crítica (`cystic_artery`), exclui `tool`; `:66-75` — sem estrutura crítica, `evidence is None` e diretório não criado | ✅ PASS |
| VIDEO-10: falha/timeout/limite do Rekognition tratado sem derrubar o pipeline, registrado no CloudWatch | (a) processamento local segue, sem propagar exceção; (b) erro/limite registrado no CloudWatch | `backend/tests/integration/test_video_handler.py:102-122` — `test_handler_falha_do_analyzer_nao_derruba_o_handler`: `response["statusCode"] == 200` e nenhuma evidência gerada, apesar do analyzer lançar `RuntimeError` | ⚠️ Spec-precision gap — (a) coberto com precisão; (b) "registrado no CloudWatch" não é verificado por nenhum teste (nem para a falha genérica, nem para o cenário específico "limite de 1000 atingido" — nenhum teste nomeia esse cenário; o código trata via `except Exception` genérico, que cobre o caso por construção, mas sem asserção dedicada) |

### P3: Relatório automático consolidado

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| VIDEO-11: relatório consolidado listando eventos com frame/tipo/link de evidência | Cada evento aparece com frame, tipo (`queda`/`estrutura_critica`) e caminho de evidência | `backend/tests/video/test_report.py:8-21` — `"Frame 42"`, `"queda"`, `"fall-42.png"` (pose) e `"Frame 7"`, `"estrutura_critica"`, `"critical-7.png"` (objeto) todos presentes | ✅ PASS |
| VIDEO-12: relatório mesmo sem eventos declara ausência | Texto explícito "nenhum evento detectado" (não omissão) | `backend/tests/video/test_report.py:24-27` — `"nenhum evento detectado" in relatorio.lower()` | ✅ PASS |

### Edge Cases (dimensões implícitas)

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| VIDEO-13: frame sem pessoa descartado da janela | `extract_keypoints` devolve `None`; janela exclui o frame, resultado idêntico ao cálculo só com frames válidos | `backend/tests/video/test_pose.py:73-79` — frame vazio → `pose_frame is None`; `backend/tests/video/test_pose_features.py:57-73` — janela com `None` intercalado produz `amplitude`/`velocity` idênticos à janela sem os `None` | ✅ PASS |
| VIDEO-14: sequência curta demais → "dados_insuficientes" | Nunca "adl" por omissão | `backend/tests/video/test_pose_detector.py:44-45` — `classify_sequence([], threshold=0.3) == "dados_insuficientes"` | ✅ PASS |
| VIDEO-15: isolamento de eventos entre sequências no mesmo lote | Chamadas sucessivas de `generate_report` não misturam dados entre sequências | `backend/tests/video/test_report.py:39-51` — `relatorio_a1 == relatorio_a2`, `"10" in relatorio_a1 and "99" not in relatorio_a1` | ✅ PASS |
| VIDEO-16: dedupe de keyframe reenviado ao S3 | Reenvio do mesmo objeto sobrescreve (não duplica) o sidecar de evidência | `backend/tests/integration/test_video_handler.py:125-144` — `len(matching_sidecars) == 1` após dois `lambda_handler` sucessivos sobre o mesmo objeto | ✅ PASS (confirmado também pelo sensor de mutação nº 3, ver abaixo) |

**Status**: 15/16 critérios com correspondência precisa ao resultado definido na spec; 1 spec-precision gap (VIDEO-10, sub-cláusula "registrado no CloudWatch" / cenário específico de limite de 1000 detecções).

---

## Discrimination Sensor

| # | File:line | Description | Killed? |
| - | --------- | ------------ | ------- |
| 1 | `backend/pipelines/video/pose_detector.py:39` | `classify_sequence`: `>` → `>=` no limiar de amplitude do centro de massa | ✅ Killed — `test_limiar_e_estritamente_excedido_nao_apenas_igualado` falhou (`'adl' != 'queda'`) |
| 2 | `backend/pipelines/video/object_evaluate.py:22` | `IOU_THRESHOLD`: `0.5` → `0.95` (afrouxa/aperta o casamento detecção↔caixa real) | ✅ Killed — `test_deteccao_com_iou_alto_conta_como_acerto` falhou (`precision` foi para `0.0`, esperado `1.0`) |
| 3 | `backend/pipelines/video/handler.py:24-27` | `_evidence_id`: removida a determinicidade (bucket+key), adicionado sufixo aleatório (`uuid4`) — quebra a idempotência de nome | ✅ Killed — `test_handler_reenvio_do_mesmo_objeto_nao_duplica_evidencia` falhou (`2 sidecars == 1` esperado, achou 2) |

Todas as 3 mutações foram injetadas em estado de trabalho real e revertidas via `git checkout -- <arquivo>` logo após confirmar a falha; `git status` confirmado limpo após cada reversão e ao final da sessão.

**Sensor depth**: lightweight (3 mutações, proporcional ao risco: threshold de classificação, limiar de casamento IoU, idempotência de evidência cloud — as três áreas mais sensíveis a regressão silenciosa)
**Result**: 3/3 killed — PASS ✅

---

## Code Quality

| Principle | Status |
| --- | --- |
| No features beyond what was asked | ✅ — cada módulo implementa exatamente o escopo do task correspondente |
| No abstractions for single-use code | ✅ |
| No unnecessary "flexibility" added | ✅ |
| Only touched files required for task | ✅ — diff restrito a `backend/pipelines/video/`, `backend/tests/video/`, `backend/tests/integration/test_video_*.py`, `backend/tests/conftest.py` (fixture compartilhada `finetuned_weights`), specs, Makefile/pyproject/docker-compose/.env.example (infra de suporte) |
| Didn't "improve" unrelated code | ✅ |
| Matches existing patterns/style | ✅ — reaproveita `common.evidence`/`common.metrics`/`common.logging`, mesmo padrão idempotente "checar antes de criar" de `pipelines/prescription/infra.py`, mesmo padrão de Lambda thin de F4 |
| Would senior engineer approve? | ✅ |
| Tests map to acceptance criteria and are non-shallow (spot-check one story) | ✅ — spot-check em P1 (pose): `test_pose_evaluate.py` testa exclusão de "dados_insuficientes" do cálculo com números que discriminam de verdade (support/recall mudam de valor, não apenas de "0 para não-0") |
| Spec-anchored outcome check | ✅ com 1 gap flagged (VIDEO-10, ver acima) |
| Per-layer Coverage Expectation met (domain 1:1 ACs; routes happy+edge+error) | ✅ — `handler.py`/`infra.py` (única camada "rota"/integração real) tem casos de sucesso, falha do analyzer e reenvio duplicado |
| Every test maps to a spec AC, listed edge case, or Done-when criterion (no unclaimed tests) | ✅ — nenhum teste "solto" sem rastreio a VIDEO-NN |
| Documented project quality/testing guidelines followed | `coding-principles.md` (test integrity, simplicidade) — seguido; nenhuma violação encontrada |

Observação (não bloqueante, não uma violação de qualidade): `design.md` descreve o dedupe de VIDEO-16 como "por ETag (mesmo padrão de PRESC-11/F4)", mas a implementação real (e o `tasks.md`/T11 "Done when") usa nome determinístico por bucket+key. `tasks.md` é a fonte que efetivamente rege a implementação e foi seguida corretamente; é só uma deriva de texto entre `design.md` e a implementação final, sem impacto funcional.

---

## Edge Cases

- [x] VIDEO-13 (frame sem pessoa descartado da janela): Handled and tested
- [x] VIDEO-14 (sequência curta demais → "dados insuficientes"): Handled and tested
- [x] Estrutura/instrumento não detectado → lista vazia, distinto de falha: Handled and tested (`test_object_detector.py::test_detect_sem_nenhuma_deteccao_devolve_lista_vazia_nao_erro`)
- [ ] VIDEO-10 edge (limite de 1000 detecções do Rekognition atingido, interrompe só a nuvem preservando resultados locais): coberto apenas indiretamente (o `except Exception` genérico do handler cobriria esse caso por construção), mas **nenhum teste nomeia esse cenário especificamente**, nem confirma o registro no CloudWatch
- [x] VIDEO-15 (isolamento entre sequências/vídeos no mesmo lote): Handled and tested
- [x] VIDEO-16 (dedupe de keyframe reenviado): Handled and tested (e confirmado pelo sensor de mutação)

---

## Gate Check

- **Gate command**: `make lint && pytest -q -m "not integration"` (Build); adicionalmente `pytest -q` (Full, com LocalStack de pé) para cobrir T11/T12
- **Result (Build/Quick)**: `make lint` — "All checks passed!"; `pytest -q -m "not integration"` — **292 passed**, 0 failed, 70 deselected (99.09s)
- **Result (Full)**: `pytest -q` — **362 passed**, 0 failed (294.76s / 4min55s), LocalStack real via `make localstack-up` (já de pé antes da sessão)
- **Test count before feature**: não medido diretamente pelo Verifier (fora do diff em revisão); o diff acrescenta 15 arquivos de teste novos (`backend/tests/video/*.py` × 11, `backend/tests/integration/test_video_*.py` × 2, mais fixtures em `backend/tests/conftest.py`)
- **Test count after feature**: 362 (292 unit + 70 integration) no total do repositório
- **Delta**: 100% dos testes no escopo do diff são novos (feature nova, sem testes pré-existentes para vídeo)
- **Skipped tests**: nenhum skip observado nesta execução (LocalStack estava de pé; os testes de integração de vídeo usam `pytest.mark.skipif` condicionado à disponibilidade de LocalStack em `:4566`, que respondeu durante toda a sessão)
- **Failures**: nenhuma

---

## Fix Plans (if issues found)

### Fix 1: VIDEO-10 — cobertura de teste incompleta para a sub-cláusula "registrado no CloudWatch" e o cenário específico de limite de 1000 detecções

- **Root cause**: `handler.py` trata qualquer exceção do `ImageAnalyzer` genericamente (`except Exception`), o que cobre o cenário de limite/timeout por construção, mas nenhum teste (a) nomeia esse cenário especificamente (ex.: simular uma exceção do tipo `ClientError` com `ThrottlingException`/`ProvisionedThroughputExceededException` do Rekognition), nem (b) verifica que a mensagem de log da falha realmente chega ao CloudWatch Logs (só a invocação bem-sucedida é verificada via CloudWatch em `test_video_infra.py`).
- **Fix task**: Adicionar um teste de integração que force uma exceção nomeada como "limite atingido" (ex.: monkeypatch do analyzer para lançar uma exceção com mensagem/tipo reconhecível de throttling) e, usando o mesmo padrão de `_log_group_has_invocation` de `test_video_infra.py`, confirmar via `get_log_events` que a mensagem de erro aparece no CloudWatch Logs do Lambda real.
- **Priority**: Minor (a funcionalidade já está correta e coberta na parte que importa — o pipeline não trava; a lacuna é só de asserção/observabilidade explícita, não um defeito funcional)

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| --- | --- | --- |
| VIDEO-01 | Implementing | ✅ Verified |
| VIDEO-02 | Implementing | ✅ Verified |
| VIDEO-03 | Implementing | ✅ Verified |
| VIDEO-04 | Implementing | ✅ Verified |
| VIDEO-05 | Implementing | ✅ Verified |
| VIDEO-06 | Implementing | ✅ Verified |
| VIDEO-07 | Implementing | ✅ Verified |
| VIDEO-08 | Implementing | ✅ Verified |
| VIDEO-09 | Implementing | ✅ Verified |
| VIDEO-10 | Implementing | ⚠️ Verified with gap (CloudWatch-observability assertion missing for the failure/limit path) |
| VIDEO-11 | Implementing | ✅ Verified |
| VIDEO-12 | Implementing | ✅ Verified |
| VIDEO-13 | Implementing | ✅ Verified |
| VIDEO-14 | Implementing | ✅ Verified |
| VIDEO-15 | Implementing | ✅ Verified |
| VIDEO-16 | Implementing | ✅ Verified |

---

## Summary

**Overall**: ⚠️ Issues (minor, non-blocking) — feature is functionally complete and ready; one test-coverage gap flagged for a follow-up fix task

**Spec-anchored check**: 15/16 ACs matched spec outcome precisely; 1 spec-precision gap (VIDEO-10 CloudWatch-observability sub-clause)
**Sensor**: 3/3 mutations killed
**Gate**: 362 passed, 0 failed (292 unit + 70 integration); `make lint` clean

**What works**: Both lanes (pose/URFD/MediaPipe and object/Endoscapes/YOLOv8) run end-to-end against real data (not mocks); all 16 requirement IDs have direct test evidence; evidence contract (AD-026) correctly wired for both fall and critical-structure events; Lambda complement is real (deployed to LocalStack, triggered by a real S3 event) and its idempotent-evidence-naming behavior is confirmed by an actual mutation kill; report generation correctly declares "no events" and never mixes data across sequences (proven, not just asserted-by-purity).

**Issues found**: Fix 1 (VIDEO-10 CloudWatch-observability + specific-limit-scenario test coverage) — see Fix Plans above.

**Next steps**: Optional — implement Fix 1 as a small follow-up task if the team wants full observability-assertion coverage before demo day. Not a blocker: the pipeline's actual behavior (continues without depending on the cloud) is already precisely tested; only the "log reaches CloudWatch" and "named limit scenario" assertions are missing.
