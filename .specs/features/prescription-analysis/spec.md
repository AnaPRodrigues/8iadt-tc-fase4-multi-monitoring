# F4 — Prescription Analysis (Textract) Specification

## Problem Statement

A equipe médica precisa identificar mudanças de prescrição fora do esperado (dose fora de faixa
terapêutica, salto abrupto vs. histórico do paciente) sem revisar manualmente cada documento.
Diferente das demais features, não existe dataset aberto de prescrições longitudinais rotuladas
sem credenciamento (MIMIC-IV) — este é o único módulo do projeto onde o dado de entrada é
sintético por necessidade (AD-022), mas com regras clínicas baseadas em faixas terapêuticas reais.
F4 também é a primeira fatia do plano de 7 dias a validar o fluxo AWS gerenciado completo
(S3 → Lambda → Textract → SNS), reduzindo risco de integração cedo no cronograma.

## Goals

- [ ] Gerar prescrições sintéticas em PDF com casos normais e anômalos, com ground truth conhecido (medicamento, dose, se é anômalo e por quê).
- [ ] Extrair campos estruturados (medicamento, dose, frequência) de PDFs via AWS Textract, disparado automaticamente por upload no S3.
- [ ] Classificar anomalias de dose fora de faixa terapêutica (referência real) e de mudança abrupta vs. histórico do paciente (DynamoDB).
- [ ] Provisionar toda a infraestrutura AWS envolvida (S3, Lambda, DynamoDB, permissões) por script idempotente, sem configuração manual.
- [ ] Medir precision/recall por tipo de anomalia contra o ground truth do gerador sintético.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Integração com dados reais do MIMIC-IV como caminho principal | AD-017/AD-022: credenciamento (CITI+DUA) fora do caminho crítico; tratado como alternativa opcional não bloqueante (P3) |
| Orquestração via Step Functions | Opcional e de responsabilidade de F5 (orquestração do fluxo de alerta), não de F4 |
| Envio da notificação final (SNS → e-mail da equipe) | F4 produz o evento/registro de anomalia; o disparo do alerta é responsabilidade de F5 |
| Verificador de interação medicamentosa / suporte clínico completo | Fora do roteiro da demo (AD-008); escopo é dose fora de faixa + mudança abrupta, não uma base farmacológica completa |
| Melhoria de acurácia de OCR além do Textract gerenciado | Nenhum treinamento de modelo customizado; usa Textract "as-is" |
| Suporte a formatos de prescrição além de PDF gerado pelo grupo | Fora do roteiro da demo; entrada é controlada e conhecida |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Catálogo de faixas terapêuticas de referência | Lista curada de ~10–15 medicamentos comuns, com dose mín/máx e unidade, extraída de bulas públicas (ex. bulário ANVISA) | Cobre o suficiente para a demo sem exigir uma base farmacológica completa (AD-022: "a regra clínica é real, o documento é sintético") | n — proposta do agente, grupo deve validar/ajustar a lista de medicamentos |
| Medicamento fora do catálogo | Registro marcado como "sem referência disponível para faixa terapêutica" — não classificado como normal nem anômalo | Evita falso positivo/negativo por ausência de dado de referência; honestidade nos limites do sistema | y |
| Limiar de "mudança abrupta" de dose | Variação > 50% em relação ao registro anterior do mesmo paciente/medicamento | Heurística comum em alerta clínico para saltos de dosagem; documentada e ajustável no relatório | n — proposta do agente, valor pode ser recalibrado |
| Chave de deduplicação de evento S3 | Hash SHA-256 do conteúdo do PDF combinado com o identificador do paciente extraído | Evita duplicar histórico no DynamoDB em caso de reentrega do evento S3 (comportamento padrão da AWS) | n — proposta do agente para a fase de Design |
| Concorrência na leitura do histórico do paciente | Last-write-wins aceitável para o escopo da demo (sem lock distribuído) | Volume de uploads simultâneos por paciente é baixo no cenário de demo; lock distribuído seria complexidade desnecessária (AD-008) | y |
| Geração dos PDFs sintéticos | Script próprio do grupo (biblioteca de geração de PDF a definir no Design) com seed para reprodutibilidade | Precisa ser reprodutível para o relatório técnico citar exemplos estáveis, mesmo padrão usado em F3 | y |
| Retenção dos dados no DynamoDB | Sem TTL; tabela removida ao final via script de teardown do ambiente do Learner Lab | Escopo de demo acadêmica de curta duração; nenhuma retenção de longo prazo é necessária (AD-007) | y |

**Open questions:** none — todas resolvidas ou registradas acima. Os itens marcados "confirmed: n" são defaults propostos pelo agente e ficam abertos a ajuste do grupo sem bloquear o avanço para Design.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Dose extraída deve ser numérica e positiva; medicamento deve casar (exato ou aproximado) com o catálogo de referência antes de aplicar a regra de faixa — ver PRESC-05, PRESC-14 |
| Failure / partial-failure states | Falha do Textract (PDF ilegível/corrompido) tratada sem travar o restante do lote — ver PRESC-07; campo ausente/malformado é sinalizado, não adivinhado — ver PRESC-04 |
| Idempotency / retry / duplicate handling | Reentrega do evento S3 não deve duplicar o registro no histórico DynamoDB — ver PRESC-11 |
| Auth boundaries & rate limits | Lambda executa somente com a role `LabRole` (sem criação de roles, AD-007); concorrência de Lambda respeita o limite de 10 execuções simultâneas do Learner Lab — ver PRESC-08 |
| Concurrency / ordering | Duas prescrições quase simultâneas do mesmo paciente: comportamento last-write-wins documentado (ver Assumptions), não deixado indefinido |
| Data lifecycle / expiry | Histórico DynamoDB sem TTL automático; removido via script de teardown do ambiente (ver Assumptions) — decisão explícita, não omissão |
| Observability | Cada execução da Lambda registra no CloudWatch: arquivo processado, sucesso/falha, tipo de anomalia (se houver) — ver PRESC-06 |
| External-dependency failure | Falha/timeout do Textract é registrada e o arquivo é movido para um prefixo de erro no S3, sem retry infinito automático — ver PRESC-07 |
| State-transition integrity | N/A because um registro de prescrição não passa por uma máquina de estados própria em F4 — ele é classificado uma vez (normal/anômalo/sem referência) e persistido; o escalonamento (verde/amarelo/vermelho) pertence a F5 |

---

## User Stories

### P1: Pipeline de extração e detecção de dose fora de faixa ⭐ MVP

**User Story**: Como integrante do grupo validando a integração AWS, quero que uma prescrição em
PDF enviada ao S3 seja automaticamente processada (Textract → parser → regra de faixa terapêutica)
e gere uma evidência de anomalia quando a dose estiver fora da faixa de referência, para provar o
fluxo gerenciado completo cedo no cronograma.

**Why P1**: Valida a integração AWS (S3 → Lambda → Textract) no dia 3 do plano, reduzindo risco de
integração antes das demais features; e cobre a exigência de "evolução de prescrições" do enunciado.

**Acceptance Criteria**:

1. WHEN o gerador de prescrições sintéticas é executado com uma seed THEN o sistema SHALL produzir PDFs de prescrição com casos normais e anômalos em proporção conhecida, registrando o ground truth (medicamento, dose, se é anômalo e por quê) em arquivo separado do PDF.
2. WHEN um PDF de prescrição é enviado ao bucket S3 de landing THEN o sistema SHALL disparar automaticamente uma Lambda (role `LabRole`) via evento de criação de objeto S3.
3. WHEN a Lambda recebe o evento THEN o sistema SHALL chamar o Textract para extrair texto/campos do PDF.
4. WHEN os campos extraídos são parseados THEN o sistema SHALL estruturar um registro (medicamento, dose numérica + unidade, frequência, identificador do paciente, timestamp); campos ausentes ou não numéricos SHALL ser sinalizados como "extração incompleta", nunca inferidos.
5. WHEN a dose extraída está fora da faixa terapêutica de referência do medicamento identificado THEN o sistema SHALL classificar o registro como anômalo, tipo "dose fora de faixa".
6. WHEN uma anomalia é detectada THEN o sistema SHALL gerar evidência reproduzível: prescrição anotada (campos destacados) + motivo da anomalia, salva no S3; e SHALL registrar a execução (arquivo, resultado, tipo de anomalia) no CloudWatch.
7. WHEN o Textract falha ao processar o PDF (ilegível/corrompido/timeout) THEN o sistema SHALL registrar o erro no CloudWatch, mover o arquivo para um prefixo de erro no S3, e continuar processando os demais uploads sem travar.
8. WHEN a infraestrutura AWS de F4 (bucket S3, tabela DynamoDB, Lambda, permissões) é necessária THEN o sistema SHALL provisioná-la via script idempotente (CloudFormation ou boto3), sem qualquer configuração manual no console.
9. WHEN o pipeline acessa credenciais AWS THEN o sistema SHALL usar variáveis de ambiente/profile local (nunca hardcoded no código), com um `.env.example` documentando as variáveis exigidas.
10. WHEN as anomalias detectadas pelo pipeline são comparadas ao ground truth do gerador sintético THEN o sistema SHALL calcular precision e recall para o tipo "dose fora de faixa", salvos em relatório de métricas.

**Independent Test**: Rodar o gerador sintético, subir os PDFs no bucket S3 e verificar que (a) cada PDF anômalo por dose gera uma evidência no S3 com o motivo correto, (b) o relatório de precision/recall bate com o ground truth do gerador, e (c) um PDF corrompido proposital não trava o processamento dos demais.

---

### P2: Histórico longitudinal e detecção de mudança abrupta

**User Story**: Como integrante do grupo, quero que o sistema compare cada nova prescrição de um
paciente com o histórico anterior dele em DynamoDB, para detectar mudanças abruptas de dose mesmo
quando a dose individual está dentro da faixa terapêutica.

**Why P2**: Cobre a exigência de "evolução de prescrições (alterações inesperadas no tratamento)"
do enunciado, que a regra de faixa isolada (P1) não captura.

**Acceptance Criteria**:

1. WHEN uma prescrição é processada com sucesso (anômala ou não) THEN o sistema SHALL persistir o registro estruturado no histórico DynamoDB do paciente, usando uma chave de deduplicação que evite duplicar o mesmo evento S3 reentregue.
2. WHEN uma nova prescrição é processada para um paciente que já possui histórico THEN o sistema SHALL comparar a dose atual com o registro anterior mais recente do mesmo medicamento.
3. WHEN a variação de dose entre a prescrição atual e a anterior excede o limiar configurado (default: 50%) THEN o sistema SHALL classificar o registro como anômalo, tipo "mudança abrupta" — mesmo que a dose individual esteja dentro da faixa terapêutica.
4. WHEN é o primeiro registro do paciente para aquele medicamento (sem histórico prévio) THEN o sistema SHALL pular a checagem de mudança abrupta e apenas persistir o registro como baseline, sem gerar falso positivo por ausência de comparação.

**Independent Test**: Processar uma sequência de 3 prescrições sintéticas do mesmo paciente/medicamento com o segundo salto de dose acima do limiar; verificar que apenas o terceiro registro (comparado ao segundo) é sinalizado corretamente conforme o salto configurado, e que o primeiro nunca gera falso positivo.

---

### P3: Alternativa opcional com dados reais do MIMIC-IV

**User Story**: Como grupo, quero poder substituir o gerador sintético pela tabela `prescriptions`
real do MIMIC-IV caso o credenciamento seja aprovado a tempo, para aumentar a fidelidade do caso de
uso sem bloquear o cronograma caso não seja aprovado.

**Why P3**: Melhoria de fidelidade, explicitamente não bloqueante (AD-022) — o sistema já é
demonstrável inteiramente com dado sintético via P1/P2.

**Acceptance Criteria**:

1. WHEN o credenciamento MIMIC-IV é aprovado e os dados estão disponíveis localmente THEN o sistema SHALL oferecer um adaptador que carregue registros da tabela `prescriptions` no mesmo formato estruturado usado pelo parser do Textract (medicamento, dose, frequência, paciente, timestamp).
2. WHEN o credenciamento não é aprovado a tempo THEN o sistema SHALL continuar funcionando inteiramente com o gerador sintético (P1), sem qualquer dependência do MIMIC-IV no caminho crítico.

---

## Edge Cases

- WHEN o PDF de prescrição não contém nenhum medicamento do catálogo de referência THEN o sistema SHALL marcar o registro como "sem referência disponível para faixa terapêutica", nunca como normal ou anômalo por omissão.
- WHEN o mesmo evento S3 é entregue mais de uma vez (reentrega padrão da AWS) THEN o sistema SHALL evitar duplicar o registro no histórico DynamoDB, usando a chave de deduplicação definida nas Assumptions.
- WHEN duas prescrições do mesmo paciente/medicamento chegam quase simultaneamente THEN o comportamento SHALL seguir a política documentada (last-write-wins, ver Assumptions), nunca um resultado indefinido.
- WHEN a Lambda atinge o limite de concorrência do Learner Lab (máx. 10, AD-007) THEN eventos extras SHALL ser retidos pela própria notificação de evento do S3 (comportamento padrão da AWS), sem perda de evento.
- WHEN a extração do Textract retorna campos parcialmente vazios (ex. frequência ausente) THEN o registro SHALL ser marcado como "extração incompleta" e excluído do cálculo de precision/recall, em vez de contar como falso negativo silencioso.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| PRESC-01 | P1: Gerador sintético de prescrições com ground truth | Design | Pending |
| PRESC-02 | P1: Trigger S3 → Lambda | Design | Pending |
| PRESC-03 | P1: Extração via Textract | Design | Pending |
| PRESC-04 | P1: Parser de campos estruturados | Design | Pending |
| PRESC-05 | P1: Regra de dose fora de faixa terapêutica | Design | Pending |
| PRESC-06 | P1: Evidência reproduzível + log CloudWatch | Design | Pending |
| PRESC-07 | P1: Tratamento de falha do Textract | Design | Pending |
| PRESC-08 | P1: Infraestrutura provisionada por script idempotente | Design | Pending |
| PRESC-09 | P1: Credenciais via env/profile, sem segredos no código | Design | Pending |
| PRESC-10 | P1: Métricas precision/recall vs. ground truth | Design | Pending |
| PRESC-11 | P2: Histórico DynamoDB + deduplicação de evento | Design | Pending |
| PRESC-12 | P2: Detecção de mudança abrupta vs. histórico | Design | Pending |
| PRESC-13 | P2: Primeiro registro sem baseline (sem falso positivo) | Design | Pending |
| PRESC-14 | Edge case: medicamento fora do catálogo de referência | Design | Pending |
| PRESC-15 | P3: Adaptador opcional MIMIC-IV (não bloqueante) | Design | Pending |

**ID format:** `PRESC-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 15 total, 0 mapped to tasks, 15 unmapped ⚠️ (aguardando fase Design/Tasks)

---

## Success Criteria

- [ ] Pipeline S3 → Lambda → Textract → classificação roda ponta a ponta com um único comando/script de upload, sem intervenção manual.
- [ ] Precision e recall calculados por tipo de anomalia ("dose fora de faixa", "mudança abrupta") contra o ground truth do gerador sintético, reportados no relatório técnico.
- [ ] Toda anomalia detectada tem evidência (PDF anotado + motivo) reproduzível na saída (critério de aceite global do projeto).
- [ ] Infraestrutura AWS de F4 recriável do zero por script, sem passos manuais no console (AD-014).
- [ ] Nenhuma credencial AWS hardcoded; `.env.example` presente e atualizado.
