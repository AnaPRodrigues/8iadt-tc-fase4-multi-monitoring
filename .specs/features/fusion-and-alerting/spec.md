# F5 — Fusion and Alerting Specification

## Problem Statement

A equipe médica precisa de uma visão consolidada de risco por paciente, combinando os sinais já
processados por vídeo (F1), áudio (F2), sinais vitais (F3) e prescrições (F4), em vez de revisar
cada fonte isoladamente. Como cada feature usa um dataset real distinto e sem identidade de
paciente em comum (AD-016), F5 define um **paciente-demo** que agrupa manualmente um registro real
de cada modalidade (AD-024), permitindo demonstrar a fusão multimodal e o fluxo de alerta
ponta a ponta exigidos pelo desafio.

## Goals

- [ ] Calcular um risk score ponderado por janela de tempo, combinando os sinais/anomalias de F1–F4 para o paciente-demo.
- [ ] Classificar o risco em verde/amarelo/vermelho com regras de escalonamento documentadas (incluindo histerese).
- [ ] Disparar alerta explicável (Lambda → SNS e-mail) com links para as evidências no S3, quando o risco cruza o limiar configurado.
- [ ] Fornecer um dashboard Streamlit com timeline unificada do paciente-demo e replay controlado do cenário.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Correlação clínica real entre vídeo/áudio/vitais/prescrição de um paciente de verdade | AD-024: o paciente-demo é uma composição didática documentada, não uma correlação clínica real |
| Descoberta automática de qual registro de cada dataset "pertence" ao mesmo paciente | A associação é manual/curada por config, nunca inferida algoritmicamente |
| Múltiplos pacientes-demo rodando simultaneamente em produção contínua | Fora do roteiro (AD-008); pode haver mais de um cenário de demo, mas cada um roda isoladamente |
| Step Functions como requisito obrigatório | Permanece opcional (AD-004); P1/P2 funcionam sem orquestração visual |
| Autenticação/autorização de usuários no dashboard | É uma demo local/apresentação, não um produto multiusuário |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Vínculo entre modalidades | Paciente-demo = 1 registro real de F1 + 1 de F2 + 1 de F3 + 1 histórico de F4, associados manualmente via config declarativa e documentados no relatório | AD-024 (decisão já confirmada com o usuário) | y |
| Pesos das modalidades no risk score | Soma ponderada configurável (default inicial: pesos iguais entre as 4 modalidades), documentada e ajustável no relatório | Sem dado histórico para calibrar pesos "ótimos"; pesos iguais é o ponto de partida mais defensável, sujeito a ajuste ao observar o cenário de demo | n — proposta do agente, calibrável no Design/Execute |
| Limiares de nível (verde/amarelo/vermelho) | Score normalizado 0–1: verde < 0.3, amarelo 0.3–0.7, vermelho > 0.7, com histerese de ±0.05 para evitar oscilação na fronteira | Necessário ter um ponto de partida concreto para implementar e testar; documentado como heurística ajustável, não validado clinicamente | n — proposta do agente, calibrável no Design/Execute |
| Janela/decaimento temporal do risk score | Sinais perdem peso gradualmente com o tempo (ex.: decaimento exponencial) em vez de permanecer com peso total indefinidamente | "Risk score ponderado por... janela de tempo" (brief) implica que sinais antigos não devem pesar como sinais recentes; evita nível "preso" em vermelho por um evento antigo já resolvido | y |
| Modo de replay do dashboard | Reprodução em velocidade acelerada ou passo a passo controlado pelo usuário, não em tempo real 1:1 | Precisa caber no vídeo de demo de até 15 min (entregável obrigatório) | n — proposta do agente, grupo pode preferir outro modo de replay |
| Destinatários do alerta SNS | E-mails dos integrantes do grupo cadastrados como inscritos do tópico SNS, representando a "equipe médica" para fins de demo | Não há equipe médica real destinatária em um projeto acadêmico; inscritos reais permitem demonstrar o e-mail chegando de fato | y |

**Open questions:** none — todas resolvidas ou registradas acima. Itens marcados "confirmed: n" são parâmetros calibráveis, não decisões de produto em aberto — serão ajustados ao observar o comportamento do paciente-demo real durante Execute.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Sinais de entrada de cada modalidade devem estar no formato/intervalo esperado (score numérico, timestamp válido) antes de entrar na fusão — ver FUSION-01 |
| Failure / partial-failure states | Modalidade sem dado disponível para a janela é tratada explicitamente (não vira risco zero silencioso) — ver FUSION-04 |
| Idempotency / retry / duplicate handling | Mesmo evento de anomalia de origem não gera alerta SNS duplicado — ver FUSION-08 |
| Auth boundaries & rate limits | Lambda usa `LabRole`; tópico SNS tem inscritos definidos (equipe do grupo); respeita limite de concorrência de Lambda (AD-007) |
| Concurrency / ordering | Eventos de modalidades diferentes chegando fora de ordem cronológica são reordenados por timestamp antes de atualizar o risk score — ver FUSION-02 |
| Data lifecycle / expiry | Decaimento temporal explícito dos sinais no risk score (ver Assumptions); não é um "N/A" nesta feature — é o núcleo do comportamento de fusão |
| Observability | Toda transição de nível (verde/amarelo/vermelho) é logada com os sinais contribuintes, para auditoria/explicabilidade — ver FUSION-06 |
| External-dependency failure | Falha no envio ao SNS é registrada e sinalizada no dashboard como "alerta não confirmado", nunca assumida como sucesso silencioso — ver FUSION-09 |
| State-transition integrity | Transições de nível seguem regras documentadas com histerese, evitando oscilação constante entre níveis adjacentes — ver FUSION-05, edge case de oscilação |

---

## User Stories

### P1: Risk score fundido e classificação verde/amarelo/vermelho ⭐ MVP

**User Story**: Como integrante do grupo validando a fusão, quero combinar os eventos já
detectados por F1–F4 para o paciente-demo em um risk score por janela de tempo e classificá-lo em
verde/amarelo/vermelho, para provar a lógica central de fusão multimodal antes de conectar o
alerta e o dashboard.

**Why P1**: É o núcleo conceitual do desafio ("fusão de diferentes tipos de dados médicos") e a
peça que transforma quatro pipelines isolados em uma história de monitoramento único.

**Acceptance Criteria**:

1. WHEN um paciente-demo é definido (config linkando um registro de cada modalidade F1–F4) THEN o sistema SHALL carregar os eventos/anomalias já produzidos por cada feature para esse paciente-demo.
2. WHEN eventos de múltiplas modalidades chegam fora de ordem cronológica THEN o sistema SHALL reordená-los por timestamp antes de atualizar o risk score.
3. WHEN o risk score é calculado para uma janela de tempo THEN o sistema SHALL combinar os sinais disponíveis das modalidades usando pesos configuráveis e documentados, aplicando decaimento temporal aos sinais mais antigos.
4. WHEN uma modalidade não tem dado disponível para a janela THEN o sistema SHALL calcular o risk score apenas com os sinais disponíveis, marcando explicitamente a modalidade ausente — nunca assumir risco zero silenciosamente para o sinal faltante.
5. WHEN o risk score cruza os limiares configurados THEN o sistema SHALL classificar o paciente-demo em verde, amarelo ou vermelho, seguindo regras de escalonamento documentadas, incluindo histerese para evitar oscilação entre níveis adjacentes.
6. WHEN o nível classificado muda THEN o sistema SHALL registrar a transição (nível anterior, novo nível, sinais contribuintes, timestamp) para auditoria/explicabilidade.

**Independent Test**: Alimentar a fusão com uma sequência conhecida de eventos das 4 modalidades (incluindo uma lacuna proposital em uma delas) e verificar que o risk score e o nível resultante batem com o cálculo manual esperado, incluindo a marcação correta da modalidade ausente.

---

### P2: Alerta explicável via SNS

**User Story**: Como equipe médica (simulada pelo grupo), quero receber um alerta por e-mail
quando o paciente-demo atinge um nível de risco elevado, com links para as evidências que
motivaram o alerta, para fechar o fluxo de "alerta automático à equipe médica" exigido pelo desafio.

**Why P2**: Cobre a exigência obrigatória de "alertar a equipe médica em tempo real"; depende do
risk score (P1) já estar funcionando.

**Acceptance Criteria**:

1. WHEN o paciente-demo atinge o nível configurado para disparo (ex.: vermelho) THEN o sistema SHALL disparar uma Lambda que publica no tópico SNS um payload explicável: ID do paciente-demo, nível, sinais contribuintes com links das evidências no S3.
2. WHEN o mesmo evento de anomalia de origem já motivou um alerta anteriormente THEN o sistema SHALL evitar duplicar o envio do alerta (dedupe por ID do evento de origem).
3. WHEN o envio ao SNS falha THEN o sistema SHALL registrar a falha no CloudWatch e sinalizar no dashboard que o alerta não foi confirmado como enviado, em vez de assumir sucesso silenciosamente.

**Independent Test**: Simular uma sequência que cruza o limiar de disparo duas vezes seguidas pelo mesmo evento de origem e verificar que apenas um e-mail é enviado; simular falha de credencial SNS e verificar que o dashboard sinaliza o alerta como não confirmado.

---

### P3: Dashboard Streamlit com timeline unificada e replay

**User Story**: Como grupo apresentando a demo, quero um dashboard com a timeline unificada do
paciente-demo e um replay controlado do cenário, para conduzir o vídeo de até 15 minutos de forma
clara e navegável.

**Why P3**: É a camada de apresentação sobre P1/P2 — a lógica de fusão e alerta já é validável sem
UI, mas o dashboard é essencial para o vídeo de demonstração.

**Acceptance Criteria**:

1. WHEN o dashboard é aberto para um paciente-demo THEN o sistema SHALL exibir uma timeline unificada com os eventos das 4 modalidades, o risk score ao longo do tempo e o nível (verde/amarelo/vermelho) correspondente.
2. WHEN o usuário aciona o replay do cenário THEN o sistema SHALL reproduzir a timeline em modo controlado (passo a passo ou velocidade acelerada configurável), sem exigir que o usuário aguarde a duração real do cenário.
3. WHEN um evento da timeline é selecionado THEN o sistema SHALL exibir a evidência correspondente (frame anotado, transcript com termo destacado, gráfico da janela anômala, ou prescrição anotada, conforme a modalidade de origem).

**Independent Test**: Abrir o dashboard com o paciente-demo configurado, acionar o replay, e confirmar que a timeline, o risk score e os detalhes de evidência por evento são exibidos corretamente e de forma navegável.

---

## Edge Cases

- WHEN nenhuma das 4 modalidades tem evento novo para uma janela THEN o sistema SHALL manter o último nível conhecido (não resetar silenciosamente para verde por ausência de dado).
- WHEN o risk score oscila perto de um limiar (ex.: entra e sai de amarelo repetidamente) THEN a histerese configurada SHALL evitar alertas repetidos para a mesma oscilação.
- WHEN o paciente-demo referenciado na config não tem os 4 registros vinculados (ex.: falta o vídeo) THEN o sistema SHALL rodar a fusão com as modalidades disponíveis e sinalizar claramente no dashboard quais estão ausentes.
- WHEN o dashboard é aberto sem nenhum paciente-demo configurado THEN o sistema SHALL exibir uma mensagem clara de configuração pendente, nunca uma tela vazia sem explicação.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| FUSION-01 | P1: Carga de eventos do paciente-demo por modalidade | Design | Pending |
| FUSION-02 | P1: Reordenação cronológica cross-modal | Design | Pending |
| FUSION-03 | P1: Cálculo do risk score ponderado com decaimento | Design | Pending |
| FUSION-04 | P1: Tratamento de modalidade ausente na janela | Design | Pending |
| FUSION-05 | P1: Classificação verde/amarelo/vermelho com histerese | Design | Pending |
| FUSION-06 | P1: Log de transição de nível (auditoria) | Design | Pending |
| FUSION-07 | P2: Alerta SNS explicável com links de evidência | Design | Pending |
| FUSION-08 | P2: Dedupe de alerta por evento de origem | Design | Pending |
| FUSION-09 | P2: Tratamento de falha de envio SNS | Design | Pending |
| FUSION-10 | P3: Dashboard com timeline unificada | Design | Pending |
| FUSION-11 | P3: Replay controlado do cenário | Design | Pending |
| FUSION-12 | P3: Detalhe de evidência por evento selecionado | Design | Pending |
| FUSION-13 | Edge: nível mantido quando não há dado novo na janela | Design | Pending |
| FUSION-14 | Edge: paciente-demo com modalidade ausente | Design | Pending |

**ID format:** `FUSION-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 14 total, 0 mapped to tasks, 14 unmapped ⚠️ (aguardando fase Design/Tasks)

---

## Success Criteria

- [ ] Risk score e classificação verde/amarelo/vermelho calculados corretamente para o paciente-demo, com decaimento temporal e histerese funcionando conforme documentado.
- [ ] Ao menos um alerta SNS disparado com sucesso durante a demo, com payload explicável e sem duplicação.
- [ ] Dashboard exibe a timeline unificada e permite replay do cenário completo dentro do tempo do vídeo (≤ 15 min).
- [ ] Toda transição de nível é auditável (sinais contribuintes visíveis), fechando o fluxo "análise → detecção → alerta" ponta a ponta.
