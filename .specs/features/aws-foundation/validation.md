# aws-foundation Validation

**Date**: 2026-07-21
**Spec**: `.specs/features/aws-foundation/spec.md`
**Diff range**: `75f421f..9d3ce5c` (branch `feat/f3-vitals-anomaly`)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status  | Notes |
| ---- | ------- | ----- |
| T1   | ✅ Done | `75f421f` — `AwsConfig`/`load_aws_config` |
| T2   | ✅ Done | `76f7c44` — `get_client` + guarda boto3.client |
| T3   | ✅ Done | `ab8ecf5` — dataclasses + Protocols |
| T4   | ✅ Done | `80d0dfa` — registro/resolução por ENV |
| T5   | ✅ Done | `1e7936b` — `TextractExtractor` |
| T6   | ✅ Done | `0f2d8a4` — `RekognitionAnalyzer` + `register_cloud_adapters` |
| T7   | ✅ Done | `b303225` — `ensure_bucket`/`ensure_topic`/`ensure_table` |
| T8   | ✅ Done | `9d3ce5c` — `main()` + `make infra-local` E2E |

All 8 tasks present, committed, and matched by working code + tests. No partial/blocked tasks.

---

## Spec-Anchored Acceptance Criteria

### P1: Factory de cliente por ambiente + config (AWSF-01, AWSF-02)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion expression | Result |
| --- | --- | --- | --- |
| WHEN `ENV=local` THEN factory retorna endpoint LocalStack, região, creds dummy | `endpoint_url=http://localhost:4566`, `region=us-east-1`, creds dummy | `backend/tests/aws/test_clients_get_client.py:6-12` — `assert client.meta.endpoint_url == "http://localhost:4566"`, `assert client.meta.region_name == "us-east-1"` | ⚠️ Partial — endpoint/região cobertos; **credenciais dummy nunca são asseridas** em nenhum teste (verificado que é tecnicamente testável via `client._request_signer._credentials.access_key`) |
| WHEN `ENV=cloud` THEN factory retorna sem `endpoint_url`, região, creds do ambiente | sem `endpoint_url` (AWS real), `region=us-east-1` | `backend/tests/aws/test_clients_get_client.py:15-22` — `assert "localhost" not in client.meta.endpoint_url`; `assert client.meta.region_name == "us-east-1"` | ✅ PASS (creds "do ambiente" — não testável offline por natureza; ⚠️ spec-precision gap aceitável) |
| WHEN `ENV` inválido THEN falha nomeando o valor | `ValueError` citando o valor recebido (ex. `xpto`) | `backend/tests/aws/test_clients_config.py:31-36` — `pytest.raises(ValueError, match="xpto")` | ✅ PASS — confirmado por mutação #1 (morta) |
| WHEN variável obrigatória ausente THEN falha nomeando a variável, antes de chamada AWS | erro cita o nome exato da variável (`LOCALSTACK_ENDPOINT`, `AWS_REGION`, `ENV`) | `backend/tests/aws/test_clients_config.py:39-45,48-53,56-61` — `pytest.raises(ValueError, match="LOCALSTACK_ENDPOINT"/"AWS_REGION"/"ENV")` | ✅ PASS — confirmado por mutação #2 (morta) |
| WHEN config carregada THEN nenhum segredo embutido em código | `.env.local`/`.env.cloud` (gitignored) ou ambiente da sessão; `"test"/"test"` só como dummy documentado | Estrutural: `backend/aws/clients.py:20-24` (`AwsConfig` sem campo de credencial) + `.env.example:5-30` documenta variáveis. Nenhum teste automatizado varre por segredo | ⚠️ Spec-precision gap — não há teste que **prove** ausência de segredo; confirmado só por revisão de código |

### P2: IaC idempotente (AWSF-06, AWSF-07)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion expression | Result |
| --- | --- | --- | --- |
| WHEN `make infra-local`/`infra-cloud` roda THEN cria S3+SNS+DynamoDB com nomes do `.env` | 3 recursos criados, nomes do ambiente, via factory | `backend/tests/integration/test_aws_provision.py:133-142` (`test_main_provisiona_os_tres_recursos`) — `assert rc == 0`; verificação independente via `get_client("s3").head_bucket(...)`, `get_client("dynamodb").describe_table(...)`; `:176-190` (`test_make_infra_local_de_ponta_a_ponta`) roda o alvo `make infra-local` de verdade via `subprocess` | ✅ PASS |
| WHEN provisionamento roda 2ª vez com recursos existentes THEN sucesso sem recriar/erro | `created=False` na 2ª chamada, sem exceção | `backend/tests/integration/test_aws_provision.py:62-69` (bucket), `:112-119` (tabela) — `assert segunda.created is False`; confirmado por mutações #8 e #9 (mortas) | ✅ PASS para bucket/tabela |
| ... idem para SNS | idem | `backend/tests/integration/test_aws_provision.py:89-96` (`test_ensure_topic_segunda_chamada_nao_recria`) | ⚠️ PASS funcional, mas **sensor fraco**: mutação #11 (paginação quebrada em `ensure_topic`, só 1ª página) sobreviveu — ver Discrimination Sensor |
| WHEN cria ou encontra recurso THEN loga nome, tipo, criado/já existia | log estruturado por recurso | `backend/aws/provision.py:29,36,46,49,57,74,104-105` implementa o log; **nenhum teste asserte o conteúdo do log para o caminho de sucesso** (só o caminho de falha é testado via `caplog`, em `test_aws_provision.py:169-173`) | ❌ GAP — comportamento implementado, não coberto por evidência |
| WHEN `ENV=local` e LocalStack fora do ar THEN erro acionável (não traceback cru) | mensagem cita `make localstack-up` | `backend/tests/integration/test_aws_provision.py:162-173` (`test_main_com_localstack_fora_do_ar_falha_com_mensagem_acionavel`) — `assert "localstack-up" in caplog.text.lower()`; confirmado por mutação #12 (morta) | ✅ PASS |

### P3: Interfaces de adapter + seleção por ENV (AWSF-03, AWSF-04, AWSF-05)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion expression | Result |
| --- | --- | --- | --- |
| WHEN código pede `TextExtractor`/`ImageAnalyzer` THEN retorna impl. registrada para o `ENV` ativo | instância correta por ambiente | `backend/tests/aws/test_adapters_registry.py:30-41` (`test_registra_e_resolve_text_extractor_por_env`) — `assert isinstance(local, _FakeLocalExtractor)`, valor de `.extract(...)` distinto por ambiente | ✅ PASS |
| WHEN nenhuma impl. registrada THEN erro claro (nunca `None`) | `ValueError` nomeando o `ENV` | `backend/tests/aws/test_adapters_registry.py:43-45,56-58` — `pytest.raises(ValueError, match="local"/"cloud")`; confirmado por mutação #5 (morta) | ✅ PASS |
| WHEN pipeline consome adapter THEN depende só da interface, nunca `boto3.client` direto | guarda de grep cobre todo o repo exceto `clients.py` | `backend/tests/aws/test_no_direct_boto3_client.py:27-33` — `assert violations == []`; `:36-45` prova detecção real; confirmado por mutação #4 (morta) | ✅ PASS |
| Modelos de dados imutáveis + `Protocol` estrutural | `frozen=True`; duck-typing satisfaz `Protocol` | `backend/tests/aws/test_adapters_types.py:8-13,16-22,25-31` (`AttributeError` em atribuição); `:44-57` (`isinstance` runtime-checkable) | ✅ PASS |
| `TextractExtractor`/`RekognitionAnalyzer` traduzem resposta do provedor corretamente | só `LINE` extraído, na ordem; `.raw` preservado; `Confidence` real preservada | `backend/tests/aws/test_cloud_textract.py:17-28,39-45` (mutação #6 morta); `backend/tests/aws/test_cloud_rekognition.py:17-27,38-44` (mutação #7 morta) | ✅ PASS |
| `register_cloud_adapters()` registra os dois para `env="cloud"` | `get_text_extractor("cloud")`/`get_image_analyzer("cloud")` devolvem as classes cloud | `backend/tests/aws/test_cloud_rekognition.py:55-62` — `assert isinstance(get_text_extractor("cloud"), TextractExtractor)` | ✅ PASS |

**Status**: ⚠️ Gaps presentes — 2 lacunas de evidência (credenciais dummy não asseridas; log de sucesso não asserido) + 1 sensor fraco (paginação de `ensure_topic`). Nenhuma delas é um defeito funcional observado — são lacunas de **cobertura de teste**, não de comportamento incorreto do código em produção.

---

## Discrimination Sensor

Todas as mutações foram aplicadas uma a uma no working tree real, confirmadas via `git diff` (aplicação única e exata), testadas, e revertidas via `git checkout -- <arquivo>` antes da mutação seguinte. `git status` limpo confirmado ao final.

| # | File:line | Description | Killed? |
| - | --------- | ------------ | ------- |
| 1 | `backend/aws/clients.py:37-38` | Removida validação de `ENV` inválido (aceitaria qualquer valor) | ✅ Killed — `test_env_invalido_nomeia_o_valor_recebido` falhou (`DID NOT RAISE`) |
| 2 | `backend/aws/clients.py:44` | `LOCALSTACK_ENDPOINT` não mais exigido quando `env=="local"` (usa `os.environ.get`) | ✅ Killed — `test_env_local_sem_endpoint_nomeia_a_variavel_ausente` falhou |
| 3 | `backend/aws/clients.py:58-69` | `get_client` sempre usa `endpoint_url` fixo, ignorando `cfg.env` | ✅ Killed — `test_get_client_cloud_resolve_sem_endpoint_localstack` falhou (`'localhost' in 'http://localhost:4566'`) |
| 4 | `backend/tests/aws/test_no_direct_boto3_client.py:9` | Regex do guarda trocada para exigir aspas duplas (`boto3\.client\("`), não casando violações reais com aspas simples | ✅ Killed — `test_guarda_detecta_violacao_injetada` falhou (`violations == []`) |
| 5 | `backend/aws/adapters/__init__.py:57-63` | `get_text_extractor` devolve `None` em vez de levantar erro quando nada registrado | ✅ Killed — `test_env_sem_text_extractor_registrado_levanta_erro` falhou |
| 6 | `backend/aws/adapters/cloud.py:28` | `TextractExtractor.extract` inclui blocos `WORD` além de `LINE` | ✅ Killed — `test_extrai_apenas_blocos_do_tipo_line_na_ordem` falhou |
| 7 | `backend/aws/adapters/cloud.py:38-44` | `RekognitionAnalyzer.analyze` troca `Confidence` real por valor fixo (100.0) | ✅ Killed — `test_mapeia_labels_da_resposta` falhou |
| 8 | `backend/aws/provision.py:25-37` | `ensure_bucket` remove `head_bucket` (sempre cria) | ✅ Killed — `test_ensure_bucket_segunda_chamada_nao_recria` falhou (LocalStack real não rejeitou 2ª criação, `created=True` nas duas) |
| 9 | `backend/aws/provision.py:53-60` | `ensure_table` remove checagem `ResourceNotFoundException` (sempre cria) | ✅ Killed — `test_ensure_table_segunda_chamada_nao_recria` falhou com `ResourceInUseException` real do LocalStack |
| 10 | `backend/aws/provision.py:85-88` | `main()` remove a validação explícita de variáveis ausentes | ❌ **Survived** — `test_main_falha_com_variavel_ausente` só verifica `rc == 1`; sem a validação explícita, `ensure_bucket(None)` propaga um `TypeError` genérico que o `try/except` de baixo captura e também retorna `rc == 1` — o teste não distingue "erro nomeado" de "erro genérico" |
| 11 | `backend/aws/provision.py:40-50` | `ensure_topic` troca paginação completa por checagem só da 1ª página (`list_topics()` direto) | ❌ **Survived** — `test_ensure_topic_segunda_chamada_nao_recria` continua passando porque o LocalStack de teste nunca tem tópicos suficientes para forçar 2ª página (SNS pagina a partir de ~100 itens); a suíte não cria volume suficiente para expor a regressão |
| 12 | `backend/aws/provision.py:90-102` | `main()` remove o `try/except` ao redor dos `ensure_*` | ✅ Killed — `test_main_com_localstack_fora_do_ar_falha_com_mensagem_acionavel` falhou com `EndpointConnectionError` não tratada (traceback cru, sem `rc==1` nem mensagem citando `localstack-up`) |

**Sensor depth**: lightweight (12 mutações manuais, acima do mínimo de 8)
**Result**: 10/12 killed — ⚠️ 2 survived (ver Fix Plans)

---

## Code Quality

| Principle | Status |
| --- | --- |
| Minimum code | ✅ |
| Surgical changes | ✅ — greenfield em `backend/aws/`, sem tocar código não relacionado |
| No scope creep | ✅ — adapters locais (Tesseract/YOLOv8) corretamente fora de escopo, só registro cloud |
| Matches patterns | ✅ — reusa `common/logging.get_logger`, mesmo padrão de `AwsConfig` frozen dataclass do design |
| Spec-anchored outcome check (asserted values match spec) | ⚠️ — ver 2 gaps acima (credenciais dummy, log de sucesso) |
| Per-layer Coverage Expectation met (domínio 1:1 ACs; integração happy+edge+erro) | ⚠️ — quase total; falta cobertura de paginação de `ensure_topic` em volume e do conteúdo de log de sucesso |
| Every test maps to a spec requirement — no unclaimed tests | ✅ — todos os testes em `backend/tests/aws/` e `test_aws_provision.py` mapeiam a um AWSF-NN ou Done-when de tarefa |
| Documented guidelines followed | ✅ — nenhuma guideline além de `pyproject.toml`/`ruff.toml`; defaults fortes aplicados (conforme a própria matriz de tasks.md) |

**Nota sobre resolução do conflito de `conftest.py`**: confirmado que existe **apenas um** `conftest.py` em `backend/tests/` (raiz), contendo a fixture autouse `_registro_de_adapters_limpo` que isola `_TEXT_EXTRACTORS`/`_IMAGE_ANALYZERS` via `monkeypatch`. Não há `conftest.py` duplicado em `backend/tests/aws/` (só um `.pyc` órfão em `__pycache__`, sem `.py` correspondente — resíduo inofensivo do conflito já corrigido). A fixture não interfere com `escreve_registro`/fixtures de F3 no mesmo arquivo.

**Nota sobre robustez de `ensure_topic` (sufixo de ARN)**: `topic["TopicArn"].endswith(f":{name}")` é robusto contra falso-positivo tipo "topic" vs "my-topic" — nomes de tópico SNS não contêm `:`, e o ARN sempre tem o nome completo como último segmento após o último `:`. Um ARN terminado em `...:my-topic` nunca casa com `endswith(":topic")` (o caractere antes de "topic" seria "y-", não ":"). Verificado analiticamente; sem teste dedicado, mas o risco é estruturalmente descartado pelo formato do ARN.

---

## Edge Cases

- [x] `ENV=local` mas LocalStack fora do ar → erro acionável citando `make localstack-up` — `backend/tests/integration/test_aws_provision.py:162-173`
- [x] Módulo fora de `clients.py` chamando `boto3.client(...)` direto → teste de guarda falha — `backend/tests/aws/test_no_direct_boto3_client.py`
- [x] Provisionamento interrompido no meio / re-rodado → idempotência cobre (bucket/tabela testados; SNS com sensor fraco, ver acima)
- [x] `ENV` não definido → decisão fixada no Design como "falhar claramente" (não default silencioso) — `test_env_ausente_nomeia_a_variavel` confirma que a ausência de `ENV` é erro, não default `local` silencioso

---

## Gate Check

- **Gate command**: `make lint && pytest -q -m "not integration"` (unitário) + `pytest -q` (completo, com LocalStack de pé)
- **Lint**: `ruff check backend` — **All checks passed!**
- **Unitário** (`pytest -q -m "not integration"`): 209 passed, 45 deselected, 0 failed
- **Completo** (`pytest -q`, LocalStack `healthy`): **254 passed, 0 failed**
- **Testes específicos de aws-foundation**: 47 (36 unitários em `backend/tests/aws/` + 11 de integração em `backend/tests/integration/test_aws_provision.py`) — tasks.md declara "45 de aws-foundation"; contagem real reproduzida é **47**. Discrepância de documentação, não de execução (todos os 47 passam); não bloqueia.
- **Test count before feature**: não determinável neste ambiente (sem baseline pré-feature commitado para comparação); a suíte cheia após a feature (254) bate com o valor declarado em tasks.md
- **Skipped tests**: nenhum skip observado (LocalStack estava de pé; o skip condicional de `test_aws_provision.py` não foi acionado)
- **Failures**: nenhuma

---

## Fix Plans

### Fix 1: `main()` — validação de variáveis ausentes sem cobertura discriminante

- **Root cause**: `test_main_falha_com_variavel_ausente` (`backend/tests/integration/test_aws_provision.py:154-159`) só verifica `rc == 1`. Removendo a checagem explícita de variáveis ausentes em `main()` (`backend/aws/provision.py:85-88`), o código ainda retorna `rc==1` (por acidente, via `TypeError` capturado pelo `try/except` genérico), então o teste não discrimina a implementação correta da incorreta.
- **Fix task**: Reforçar o teste para também afirmar que a mensagem de erro nomeia a variável ausente (ex. `caplog` com `assert "S3_BUCKET" in caplog.text`), do mesmo padrão já usado em `test_main_com_localstack_fora_do_ar_falha_com_mensagem_acionavel`.
- **Priority**: Minor — comportamento em produção já está correto (código valida e nomeia a variável); é lacuna de teste, não de funcionalidade.

### Fix 2: `ensure_topic` — paginação sem cobertura em volume

- **Root cause**: `backend/aws/provision.py:42-47` usa paginação completa (`get_paginator("list_topics").paginate()`), correto por design, mas nenhum teste cria tópicos suficientes (SNS pagina a partir de ~100 itens) para provar que a segunda/enésima página é de fato consultada. Um retrocesso para "só primeira página" passaria despercebido em ambientes com poucos tópicos de teste — que é exatamente o caso do Learner Lab real ao longo do tempo (múltiplas features acumulando tópicos).
- **Fix task**: Teste de integração que popule >100 tópicos (ou mocka o paginador para forçar 2+ páginas) e verifique que `ensure_topic` encontra um tópico existente presente só na 2ª página.
- **Priority**: Minor/Major latente — risco real cresce com o tempo de uso do Learner Lab (mais tópicos acumulados = mais chance da paginação importar), mas não é um bloqueador imediato para fechar a feature agora (o LocalStack/lab atual tem poucos tópicos).

### Fix 3 (menor, não bloqueador): log de sucesso do provisionamento sem asserção

- **Root cause**: AWSF-06 AC3 exige logar "nome, tipo e se foi criado ou já existia"; o código faz isso (`backend/aws/provision.py:29,36,46,49,57,74,104-105`), mas nenhum teste usa `caplog` para confirmar o conteúdo no caminho de sucesso (só no de falha).
- **Fix task**: Adicionar `caplog` a um teste de `ensure_bucket`/`main()` de sucesso, confirmando que o nome do recurso e o status aparecem no log.
- **Priority**: Cosmetic/Minor — puramente lacuna de evidência; comportamento observável (recursos existem de fato) já é verificado por outros meios.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| --- | --- | --- |
| AWSF-01 | Implementing | ⚠️ Verified com ressalva (credenciais dummy não asseridas em teste) |
| AWSF-02 | Implementing | ⚠️ Verified com ressalva (ausência de segredo confirmada só por revisão, não por teste automatizado) |
| AWSF-03 | Implementing | ✅ Verified |
| AWSF-04 | Implementing | ✅ Verified |
| AWSF-05 | Implementing | ✅ Verified |
| AWSF-06 | Implementing | ⚠️ Verified com ressalva (paginação de `ensure_topic` sem cobertura em volume; log de sucesso sem asserção) |
| AWSF-07 | Implementing | ✅ Verified |

---

## Summary

**Overall**: ⚠️ Issues (não bloqueadores) — feature pode fechar com riscos residuais aceitos e documentados

**Spec-anchored check**: 5/7 AC groups totalmente confirmados; 2 com ressalva pontual (AWSF-01/02 credenciais/segredo — gaps de evidência, não de comportamento; AWSF-06 — sensor fraco em paginação de SNS + log de sucesso sem asserção)

**Sensor**: 10/12 mutações mortas (83%); 2 sobreviventes, ambas de baixo risco imediato (ver Fix Plans 1 e 2)

**Gate**: 254 passed, 0 failed, lint limpo; 47 testes específicos de aws-foundation (36 unit + 11 integration) — nota: tasks.md declara 45, contagem real é 47 (discrepância de documentação apenas)

**What works**: Factory único por `ENV` (AWSF-01/03), interfaces + registro de adapters (AWSF-04/05), wrappers cloud Textract/Rekognition testados por duck-typing (AD-035 respeitada), IaC idempotente para S3/DynamoDB provada com LocalStack real via mutação, erro acionável quando LocalStack está fora do ar (AWSF-07), guarda de `boto3.client` direto funcionando e comprovadamente discriminante, conflito de `conftest.py` corretamente resolvido (fixture única na raiz de `tests/`), robustez do sufixo de ARN do SNS confirmada analiticamente.

**Issues found**:
1. Teste de "variável ausente" em `main()` não discrimina validação explícita de falha genérica (Fix 1, Minor)
2. Paginação de `ensure_topic` sem cobertura de volume — risco cresce com uso continuado do lab (Fix 2, Minor/Major latente)
3. Log de sucesso do provisionamento sem asserção de conteúdo (Fix 3, Cosmetic/Minor)
4. Credenciais dummy (`ENV=local`) nunca asseridas diretamente em teste, embora testável (ressalva em AWSF-01)
5. Discrepância de contagem: tasks.md declara "45 de aws-foundation", real é 47 (documentação, não bloqueador)

**Next steps**: Nenhum dos achados é um defeito funcional observado em produção — todos são lacunas de cobertura de teste. Recomenda-se abrir os 3 fix tasks acima como follow-up de baixa prioridade (não bloqueiam o fechamento da feature); a fundação está funcionalmente correta e pronta para ser consumida por F4/F1/F5.
