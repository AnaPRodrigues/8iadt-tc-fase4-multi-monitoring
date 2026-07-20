# F1 — Video Analysis Specification

## Problem Statement

A equipe médica precisa identificar desvios de procedimento em vídeos clínicos (ex.: instrumento
usado fora da fase esperada, ausência de instrumento esperado) sem revisar cada gravação
manualmente. Assim como em F3, priorizamos dado real e anotado: o Cholec80-CVS fornece vídeo
cirúrgico laparoscópico real com anotação de fase/instrumento, permitindo detectar anomalia como
desvio da sequência anotada em vez de fabricar eventos. Complementarmente, keyframes selecionados
são analisados na nuvem via Rekognition, demonstrando a integração de serviços gerenciados de IA
exigida pelo desafio (AD-023: escopo restrito ao pipeline cirúrgico, sem MediaPipe Pose/clipe
gravado pelo grupo).

## Goals

- [ ] Carregar vídeos do Cholec80-CVS com sua anotação real de fase/instrumento como ground truth.
- [ ] Detectar eventos fora da sequência de fases esperada usando YOLOv8 local (anomalia = desvio da anotação).
- [ ] Complementar com análise de keyframes na nuvem via S3 → Lambda → Rekognition (labels/objetos).
- [ ] Produzir evidência reproduzível (frame anotado + JSON de eventos) e um relatório automático por vídeo, consumíveis pela fusão (F5).
- [ ] Medir precision/recall/F1 dos eventos detectados contra a anotação real.

## Out of Scope

| Feature | Reason |
| --- | --- |
| MediaPipe Pose / análise postural (queda, assimetria) | AD-023: grupo optou pelo escopo restrito a Cholec80-CVS; vídeo endoscópico não permite pose estimation e nenhum clipe extra será gravado |
| Cenário de fisioterapia com corpo inteiro | Decorre da mesma decisão AD-023 |
| Treinamento de modelo de detecção de fase do zero | Fora do prazo de 7 dias; qualquer fine-tuning necessário do YOLOv8 é leve e documentado no Design, não um pipeline de treino completo |
| Streaming de vídeo em tempo real | Abordagem é por keyframes/amostragem em micro-batch, não frame-a-frame em baixa latência (consistente com AD-011 aplicado a vídeo) |
| Reconhecimento completo do fluxo cirúrgico (todas as fases/instrumentos do Cholec80) | O roteiro da demo (AD-008) define o escopo; cobre desvio de fase/instrumento, não uma reprodução completa do dataset |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Estrutura exata das anotações do Cholec80-CVS (fases, presença de instrumento) | A confirmar na fase de Design, lendo a documentação/schema real do dataset antes de implementar o parser | Não fabricar estrutura de dataset sem verificar a fonte (Knowledge Verification Chain); evita retrabalho se o schema for diferente do assumido | n — verificação pendente no Design |
| Modelo YOLOv8 usado | Variante leve pré-treinada (ex. YOLOv8n/YOLOv8s) como ponto de partida; fine-tuning leve sobre classes de instrumento cirúrgico se o modelo genérico (COCO) não cobrir bem essas classes | AD-012 (CPU-only); decisão final e viabilidade do fine-tuning ficam para o Design, após avaliar o schema de anotação | n — a confirmar no Design |
| Seleção de keyframes para a nuvem | Amostragem periódica (ex.: 1 frame a cada N segundos) combinada com frames onde o pipeline local já detectou evento anômalo | Reduz custo/volume de chamadas ao Rekognition (limite de 1000 detecções, AD-007) mantendo cobertura dos momentos relevantes | n — parâmetro N a calibrar no Design |
| Subconjunto de vídeos Cholec80-CVS usado na demo | Amostra curada (não os 80 vídeos completos), suficiente para treinar/avaliar e caber no prazo | Processar o dataset completo é desproporcional ao valor demonstrativo dentro de 7 dias | y |

**Open questions:** none — todas resolvidas ou registradas acima. Itens marcados "confirmed: n" exigem uma etapa de verificação técnica no Design (schema do dataset, parâmetros de amostragem), não uma decisão de produto em aberto.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Vídeo em formato/resolução suportado; anotação de fase/instrumento presente e no formato esperado antes de processar — ver VIDEO-12 |
| Failure / partial-failure states | Trechos sem anotação completa são descartados do cálculo de métricas sem interromper o restante — ver VIDEO-12; falha/limite do Rekognition não derruba o pipeline local — ver VIDEO-09 |
| Idempotency / retry / duplicate handling | Reenvio do mesmo keyframe ao S3 não deve duplicar o label anexado ao evento (dedupe por nome/hash do arquivo) — ver VIDEO-15 |
| Auth boundaries & rate limits | Lambda executa somente com a role `LabRole`; respeita limite de 10 execuções concorrentes e de 1000 detecções do Rekognition (AD-007) — ver VIDEO-09 |
| Concurrency / ordering | Eventos dentro de um mesmo vídeo mantêm ordem cronológica; vídeos processados no mesmo lote não misturam eventos/IDs entre si — ver VIDEO-14 |
| Data lifecycle / expiry | N/A because artefatos de evidência são gerados por execução de demo acadêmica sem requisito de retenção/expiração |
| Observability | Cada vídeo/frame processado registra se a etapa de nuvem (Rekognition) foi bem-sucedida, pulada ou falhou, consumível por F5 |
| External-dependency failure | Falha/timeout ou limite do Rekognition tratado sem interromper o pipeline local — ver VIDEO-09 |
| State-transition integrity | N/A because F1 não possui máquina de estados própria; a classificação verde/amarelo/vermelho pertence a F5 |

---

## User Stories

### P1: Detecção de eventos fora da sequência de fases (YOLOv8 local) ⭐ MVP

**User Story**: Como integrante do grupo validando o pipeline, quero detectar instrumentos por
frame com YOLOv8 e sinalizar quando a presença/ausência de instrumento diverge da fase cirúrgica
anotada, para provar detecção de desvio com ground truth real antes de integrar às demais fontes
multimodais.

**Why P1**: Cobre a exigência obrigatória de "detectar movimentos ou eventos fora do padrão
esperado" com o dataset real anotado, sendo a fatia que sustenta o relatório e o vídeo de demo.

**Acceptance Criteria**:

1. WHEN um vídeo do Cholec80-CVS é carregado junto com sua anotação de fase/instrumento THEN o sistema SHALL extrair a sequência de fases e a presença de instrumentos anotada como ground truth.
2. WHEN o YOLOv8 processa os frames amostrados do vídeo THEN o sistema SHALL detectar os instrumentos/objetos presentes em cada frame.
3. WHEN a detecção de instrumento em um frame diverge da fase anotada esperada (instrumento presente fora da fase correta, ou instrumento esperado ausente) THEN o sistema SHALL classificar o frame/janela como evento anômalo, com o tipo de desvio identificado.
4. WHEN os eventos anômalos detectados são comparados à anotação real do vídeo THEN o sistema SHALL calcular precision, recall e F1, salvos em relatório de métricas.
5. WHEN um evento anômalo é detectado THEN o sistema SHALL gerar evidência reproduzível: frame anotado (bounding boxes dos instrumentos) + metadados (timestamp, fase esperada, instrumento detectado, tipo de desvio) + entrada no JSON de eventos do vídeo.

**Independent Test**: Rodar o pipeline sobre o subconjunto curado de vídeos Cholec80-CVS e verificar que (a) o relatório de precision/recall/F1 contra a anotação real é gerado, e (b) existe evidência (frame anotado + metadados) para cada evento anômalo reportado.

---

### P2: Complemento em nuvem via Rekognition sobre keyframes

**User Story**: Como grupo, quero enviar keyframes selecionados do vídeo para análise no
Rekognition (S3 → Lambda → Rekognition), para demonstrar a integração com serviços gerenciados de
IA na nuvem exigida pelo desafio, complementando a detecção local.

**Why P2**: Cobre a exigência obrigatória de "integrar com serviços gerenciados em nuvem"; não
bloqueia a demonstração central de detecção (P1), que já funciona só localmente.

**Acceptance Criteria**:

1. WHEN keyframes são selecionados de um vídeo processado THEN o sistema SHALL fazer upload desses keyframes para o bucket S3 de landing.
2. WHEN um keyframe é enviado ao S3 THEN o sistema SHALL disparar automaticamente uma Lambda (role `LabRole`) que chama o Rekognition para obter labels/objetos/pessoas detectados no frame.
3. WHEN o Rekognition retorna labels THEN o sistema SHALL anexar esses labels como evidência complementar ao evento local correspondente (quando o keyframe coincidir com um evento do P1) ou como registro independente.
4. WHEN o Rekognition falha, expira por timeout, ou o limite de 1000 detecções (AD-007) é atingido THEN o sistema SHALL registrar o erro/limite no CloudWatch e continuar o restante do pipeline local (P1) sem depender da nuvem para funcionar.

**Independent Test**: Enviar um pequeno lote de keyframes ao S3 e confirmar que os labels do Rekognition aparecem como evidência complementar nos eventos correspondentes; simular indisponibilidade (ex. sem credenciais válidas) e confirmar que o pipeline local (P1) continua funcionando e o erro é registrado claramente.

---

### P3: Relatório automático consolidado por vídeo

**User Story**: Como equipe médica, quero um relatório automático por vídeo resumindo os desvios
detectados (local + nuvem), para revisão rápida sem abrir o JSON bruto de eventos.

**Why P3**: Cobre a exigência de "gerar relatórios automáticos indicando desvios ou falhas no
procedimento"; é uma camada de apresentação sobre os eventos já produzidos por P1/P2.

**Acceptance Criteria**:

1. WHEN o processamento de um vídeo é concluído (P1 e, se disponível, P2) THEN o sistema SHALL gerar um relatório legível (Markdown/HTML) por vídeo, listando cada evento anômalo com timestamp, tipo de desvio e link para a evidência (frame anotado).
2. WHEN nenhum evento anômalo é detectado em um vídeo THEN o sistema SHALL gerar o relatório indicando explicitamente "nenhum desvio detectado", em vez de omitir o relatório.

**Independent Test**: Processar um vídeo com desvios conhecidos e um vídeo sem desvios; confirmar que ambos geram relatório, um listando os eventos e o outro declarando ausência de desvios.

---

## Edge Cases

- WHEN o vídeo Cholec80-CVS não possui anotação de fase/instrumento completa para algum trecho THEN o sistema SHALL descartar esse trecho do cálculo de métricas, sem interromper o restante do processamento do vídeo.
- WHEN o YOLOv8 não detecta nenhum instrumento em um frame THEN o sistema SHALL classificá-lo como "sem instrumento visível", distinto de uma falha de processamento.
- WHEN o limite de detecções do Rekognition (1000, AD-007) é atingido durante o processamento de um lote THEN o sistema SHALL interromper apenas o envio à nuvem (P2), preservando os resultados locais já obtidos (P1).
- WHEN dois ou mais vídeos são processados no mesmo lote THEN o sistema SHALL manter os eventos/evidências de cada vídeo isolados, sem mistura de IDs ou timestamps entre vídeos diferentes.
- WHEN o mesmo keyframe é reenviado ao S3 (reprocessamento) THEN o sistema SHALL evitar duplicar o label anexado ao evento correspondente.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| VIDEO-01 | P1: Carga de vídeo + anotação de fase/instrumento | Design | Pending |
| VIDEO-02 | P1: Detecção de instrumentos por frame (YOLOv8) | Design | Pending |
| VIDEO-03 | P1: Classificação de evento anômalo (desvio de fase) | Design | Pending |
| VIDEO-04 | P1: Métricas precision/recall/F1 | Design | Pending |
| VIDEO-05 | P1: Evidência (frame anotado + JSON de eventos) | Design | Pending |
| VIDEO-06 | P2: Seleção e upload de keyframes ao S3 | Design | Pending |
| VIDEO-07 | P2: Trigger S3 → Lambda → Rekognition | Design | Pending |
| VIDEO-08 | P2: Anexação de labels como evidência complementar | Design | Pending |
| VIDEO-09 | P2: Tratamento de falha/limite do Rekognition | Design | Pending |
| VIDEO-10 | P3: Relatório automático consolidado por vídeo | Design | Pending |
| VIDEO-11 | P3: Relatório mesmo sem desvios detectados | Design | Pending |
| VIDEO-12 | Edge: trechos sem anotação descartados das métricas | Design | Pending |
| VIDEO-13 | Edge: frame sem instrumento tratado como classe própria | Design | Pending |
| VIDEO-14 | Edge: isolamento de eventos entre vídeos no mesmo lote | Design | Pending |
| VIDEO-15 | Dimensão: dedupe de keyframe reenviado | Design | Pending |

**ID format:** `VIDEO-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 15 total, 0 mapped to tasks, 15 unmapped ⚠️ (aguardando fase Design/Tasks)

---

## Success Criteria

- [ ] Pipeline local (YOLOv8) roda ponta a ponta sobre o subconjunto Cholec80-CVS com um único comando, produzindo métricas de precision/recall/F1 sem intervenção manual.
- [ ] Ao menos um lote de keyframes processado com sucesso pelo Rekognition, com labels anexados como evidência complementar.
- [ ] Relatório automático gerado para cada vídeo processado (com ou sem desvios).
- [ ] Toda anomalia detectada tem evidência visual/textual correspondente na saída (critério de aceite global do projeto).
