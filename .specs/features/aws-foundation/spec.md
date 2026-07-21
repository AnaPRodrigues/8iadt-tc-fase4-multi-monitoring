# aws-foundation Specification

## Problem Statement

As features com nuvem (F4 prescrições, F1 vídeo, F5 fusão/alerta) precisam falar com serviços AWS,
mas o Learner Lab tem credenciais que rotacionam por sessão, budget limitado e não pode ser usado
para dev/teste rotineiro. Esta feature entrega a **fundação compartilhada** que permite construir e
testar todo o fluxo AWS **offline** (LocalStack) e promovê-lo ao lab real trocando só uma variável:
um factory único de cliente boto3 por ambiente, interfaces de adapter para os serviços que o
LocalStack Community não cobre (Textract/Rekognition), e IaC idempotente que provisiona os mesmos
recursos nos dois ambientes.

## Goals

- [ ] Um factory único de cliente boto3 selecionado por `ENV` (`local` → LocalStack; `cloud` → AWS real), sem `boto3.client(...)` direto em pipeline nenhum.
- [ ] Interfaces de adapter (`TextExtractor`, `ImageAnalyzer`) com seleção por `ENV`, isolando Textract/Rekognition (indisponíveis no LocalStack Community).
- [ ] IaC idempotente que provisiona os recursos compartilhados (bucket S3, tópico SNS, tabela DynamoDB) igual nos dois ambientes — só muda o endpoint.
- [ ] Config por `.env` sem segredo em código; LocalStack sobe por `docker-compose`.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Implementações concretas dos adapters **locais** (Tesseract/pdfplumber para OCR; YOLOv8 para labels) | Pertencem às features que as consomem: F4 traz o extractor local, F1 traz o analyzer local. A fundação define a interface + a seleção por `ENV` |
| Handlers de Lambda de negócio (parser de prescrição, alerta) | F4/F5 |
| Lógica de prescrição, vídeo, fusão | features respectivas |
| Provisionar serviços fora do fluxo compartilhado (ex.: Step Functions, API Gateway) | Entram quando F5/backend `app/` precisarem; a fundação cobre S3/SNS/DynamoDB do fluxo event-driven |
| Deploy automatizado para o lab | AD-013: CI não faz deploy (credenciais rotacionam) |

---

## Assumptions & Open Questions

| Assumption / decisão | Default escolhido | Rationale | Confirmado? |
| --- | --- | --- | --- |
| Ambientes | `ENV=local` (LocalStack, endpoint `http://localhost:4566`, creds `test/test`) e `ENV=cloud` (AWS real, sem `endpoint_url`) | AD-034 | y |
| Backend de teste de integração | **LocalStack real** (Docker), não moto | Escolha do usuário; fidelidade ao ambiente-alvo | y |
| Recursos compartilhados provisionados | bucket S3 (`S3_BUCKET`), tópico SNS (`SNS_TOPIC`), tabela DynamoDB (`DYNAMODB_TABLE`) — nomes vindos do `.env` | São os recursos do fluxo event-driven de alerta (AD-004) usados por F4/F5 | y |
| Linguagem da IaC | Script boto3 idempotente (`backend/aws/provision.py`), não CloudFormation | AD-014 admite boto3 idempotente; o mesmo código roda nos dois ambientes via o factory, o que CloudFormation não faria tão diretamente | y |
| Role de execução de Lambda | `LabRole` fixa no cloud (AD-007); no local, o LocalStack aceita qualquer ARN | Não é possível criar roles no lab | y |
| "Nunca `boto3.client` direto" | Verificado por teste que faz grep no código fora de `clients.py` | AD-034 exige o factory único; um teste torna a regra executável, não só convenção | y |
| Credenciais do cloud | Vêm da sessão do lab (env/CLI), nunca do Git; `.env.cloud` não carrega segredo real | AD-007/AD-037 | y |

**Open questions:** none. Docker é pré-requisito operacional do Execute (P2/P3), não uma ambiguidade de spec.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Variáveis de ambiente obrigatórias validadas na carga; `ENV` fora de {local,cloud} rejeitado — ver AWSF-02 |
| Failure / partial-failure states | LocalStack fora do ar (local) → erro claro, não stack trace de socket — ver AWSF-07/edge; provisionar recurso já existente não falha (idempotência) — ver AWSF-06 |
| Idempotency / retry / duplicate handling | Núcleo da IaC: re-rodar `provision` não recria nem erra — ver AWSF-06 |
| Auth boundaries & rate limits | `local` usa creds dummy; `cloud` usa credenciais temporárias do lab e `LabRole` fixa (AD-007) — ver AWSF-01 |
| Concurrency / ordering | N/A because a fundação é setup/config; concorrência (10 Lambdas) é restrição das features que a usam |
| Data lifecycle / expiry | Recursos do lab persistem entre sessões e devem ser recriáveis por script; sem TTL na fundação — decisão explícita (AD-014) |
| Observability | Factory e provisionamento logam ambiente ativo, endpoint e recursos criados/existentes — ver AWSF-06 |
| External-dependency failure | LocalStack (local) ou AWS (cloud) indisponível → erro acionável nomeando o ambiente e o que checar — ver edge cases |
| State-transition integrity | N/A because a fundação não tem máquina de estados; idempotência cobre o "já existe → não recria" |

---

## User Stories

### P1: Factory de cliente por ambiente + config ⭐ MVP

**User Story**: Como desenvolvedor construindo F4/F1/F5, quero obter clientes boto3 já configurados
para o ambiente ativo por uma única função, para nunca instanciar `boto3.client` direto nem
espalhar endpoints/credenciais pelos pipelines.

**Why P1**: Tudo que toca AWS depende disto; é testável offline (sem Docker) porque criar um cliente
boto3 configurado não faz chamada de rede.

**Acceptance Criteria**:

1. WHEN `ENV=local` THEN o factory SHALL retornar clientes boto3 com `endpoint_url=http://localhost:4566`, região `us-east-1` e credenciais dummy.
2. WHEN `ENV=cloud` THEN o factory SHALL retornar clientes boto3 **sem** `endpoint_url` (AWS real), região `us-east-1`, usando as credenciais do ambiente.
3. WHEN `ENV` não é `local` nem `cloud` THEN o factory SHALL falhar com erro claro nomeando o valor inválido.
4. WHEN uma variável de ambiente obrigatória está ausente THEN a carga de config SHALL falhar nomeando a variável, antes de qualquer chamada AWS.
5. WHEN a config é carregada THEN nenhum segredo SHALL estar embutido em código — só em `.env.local`/`.env.cloud` (gitignored) ou no ambiente da sessão.

**Independent Test**: Chamar o factory com `ENV=local` e `ENV=cloud` e inspecionar a config resolvida do cliente (endpoint, região) sem nenhuma chamada de rede; `ENV=xpto` levanta erro.

---

### P2: IaC idempotente dos recursos compartilhados

**User Story**: Como grupo recriando o ambiente a cada sessão do lab, quero provisionar os recursos
compartilhados (S3, SNS, DynamoDB) com um comando idempotente que roda igual no local e no cloud,
para não configurar nada à mão no console.

**Why P2**: Critério de aceite global (recursos recriáveis por script, AD-014); F4/F5 dependem
desses recursos existirem.

**Acceptance Criteria**:

1. WHEN `make infra-local` ou `make infra-cloud` é executado THEN o sistema SHALL criar o bucket S3, o tópico SNS e a tabela DynamoDB com os nomes do `.env`, via o factory (endpoint conforme `ENV`).
2. WHEN o provisionamento roda uma segunda vez com os recursos já existentes THEN o sistema SHALL terminar com sucesso sem recriar nem lançar erro (idempotência).
3. WHEN o provisionamento cria ou encontra um recurso THEN o sistema SHALL logar o nome, o tipo e se foi criado ou já existia.

**Independent Test** (LocalStack): subir o LocalStack, rodar `make infra-local` duas vezes; a primeira cria, a segunda é no-op; conferir via boto3 que os três recursos existem.

---

### P3: Interfaces de adapter + seleção por ambiente

**User Story**: Como autor de F4/F1, quero interfaces `TextExtractor`/`ImageAnalyzer` cuja
implementação (cloud AWS ou local OSS) é escolhida pelo `ENV`, para meu pipeline depender só da
interface e rodar nos dois ambientes.

**Why P3**: Habilita F4/F1 offline (LocalStack Community não tem Textract/Rekognition, AD-035); mas
as implementações concretas vêm com as features, então aqui é a interface + o mecanismo de seleção.

**Acceptance Criteria**:

1. WHEN o código pede um `TextExtractor`/`ImageAnalyzer` THEN a fundação SHALL retornar a implementação registrada para o `ENV` ativo (local ou cloud), atrás de uma interface única.
2. WHEN nenhuma implementação está registrada para o `ENV` ativo THEN a fundação SHALL falhar com erro claro (em vez de retornar `None`).
3. WHEN um pipeline consome o adapter THEN ele SHALL depender só da interface abstrata, nunca da classe concreta nem de `boto3.client` direto.

**Independent Test**: Registrar implementações fake para local e cloud, resolver por `ENV` e confirmar que vem a correta; `ENV` sem impl registrada levanta erro.

---

## Edge Cases

- WHEN `ENV=local` mas o LocalStack não está no ar THEN uma operação AWS SHALL falhar com erro acionável ("LocalStack não responde em :4566 — rode `make localstack-up`"), não um traceback cru de conexão recusada.
- WHEN qualquer módulo fora de `backend/aws/clients.py` instancia `boto3.client(...)` direto THEN um teste SHALL falhar apontando o arquivo (guarda da regra AD-034).
- WHEN o provisionamento é interrompido no meio THEN re-rodar SHALL completar sem erro (idempotência cobre o estado parcial).
- WHEN `ENV` não está definido THEN o sistema SHALL assumir `local` como default documentado (dev offline) ou falhar claramente se preferir explícito — **decisão a fixar no Design**.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| AWSF-01 | P1: Factory de cliente por `ENV` | T1, T2 | Verified |
| AWSF-02 | P1: Config validada, sem segredo em código | T1 | Verified |
| AWSF-03 | P3/Edge: guarda "sem `boto3.client` direto" | T2 | Verified |
| AWSF-04 | P3: Interfaces `TextExtractor`/`ImageAnalyzer` | T3, T5, T6 | Verified |
| AWSF-05 | P3: Seleção de adapter por `ENV` | T4, T5, T6 | Verified |
| AWSF-06 | P2: IaC idempotente dos recursos compartilhados | T7, T8 | Verified |
| AWSF-07 | P2/Edge: LocalStack via docker-compose + erro se fora do ar | T2, T8 | Verified |

**ID format:** `AWSF-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 7 de 7 requisitos Verified (Verifier PASS: 47 testes — 36 unit + 11 integração contra LocalStack real; 10/12 mutantes mortos). 2 sobreviventes aceitos como dívida de teste, não bugs (ver validation.md): teste de variável ausente passa por acidente (comportamento de produção correto); paginação de `ensure_topic` nunca forçada (risco latente, cresce com o tempo, não bloqueador). **aws-foundation FECHADA.**

---

## Success Criteria

- [ ] `ENV=local` e `ENV=cloud` resolvem clientes corretos (endpoint/creds) por uma única função; nenhum `boto3.client` direto no repo (teste de guarda passa).
- [ ] `make infra-local` provisiona S3+SNS+DynamoDB no LocalStack e é idempotente na segunda execução.
- [ ] `TextExtractor`/`ImageAnalyzer` resolvem a implementação por `ENV`; pipelines dependem só da interface.
- [ ] Nenhum segredo em código; `.env.example` documenta as variáveis; `docker-compose` sobe o LocalStack.
