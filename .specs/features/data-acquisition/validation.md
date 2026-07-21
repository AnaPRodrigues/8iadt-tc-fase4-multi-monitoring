# F0 — Data Acquisition Validation

**Date**: 2026-07-20
**Spec**: `.specs/features/data-acquisition/spec.md`
**Diff range**: `b1ce73a^..ee405af` (T1–T7), branch `feat/f3-vitals-anomaly`
**Verifier**: independent sub-agent (author ≠ verifier, evidence-or-zero)

**Verdict**: ✅ **PASS — F0 pode ser fechada.** Nenhum bloqueador. Riscos residuais em cobertura de resume (DATA-06) e redundância de defesa em profundidade — ver seção Riscos.

---

## Task Completion

| Task | Status | Notas |
| --- | --- | --- |
| T1 (esqueleto + vars + require_tools) | ✅ Done | `9045e32` |
| T2 (verify_zip) | ✅ Done | `b5b779c` |
| T3 (sentinela + espaço) | ✅ Done | `b1ce73a` |
| T4 (fetch_ctu_uhb) | ✅ Done | `2a8a832` |
| T5 (fetch_icbhi + fallback) | ✅ Done | `9622662` |
| T6 (fetch_endoscapes) | ✅ Done | `58dc9c1` |
| T7 (main + resumo + make data) | ✅ Done | `ee405af` |

---

## Spec-Anchored Acceptance Criteria

Cobertura ancorada na spec (evidence-or-zero). Todos os `file:line` conferidos.

| Requisito / AC (WHEN → THEN) | Desfecho da spec | `file:line` + asserção | Resultado |
| --- | --- | --- | --- |
| **DATA-01** CTU-UHB via `wfdb.dl_database` → `data/ctu-uhb/` | Baixa e marca `.complete` só com `.hea`/`.dat` | `test_download_datasets.py:81-84` — `assert rc==0; status=="baixado"; (ctu-uhb/.complete).is_file(); (ctu-uhb/1001.hea).is_file()` | ✅ PASS |
| **DATA-02** ICBHI do Dataverse c/ resume + `unzip` | Zip extraído, `.complete` escrito | `test_download_datasets.py:146-149` — `assert rc==0; status=="baixado"; (icbhi/.complete).is_file(); (icbhi/registro.wav).is_file()` (unzip real) | ✅ PASS |
| **DATA-03** Endoscapes via `wget --continue` + `unzip` | Zip extraído, `.complete` escrito | `test_download_datasets.py:218-221` — `assert rc==0; status=="baixado"; (endoscapes/.complete).is_file(); (endoscapes/registro.wav).is_file()` | ✅ PASS |
| **DATA-05** URLs/paths como variáveis no topo | Defaults presentes p/ Dataverse, Endoscapes, CTU_DB, DATA_DIR | `test_download_tools.py:53-56` — `assert "dataverse.harvard.edu" in stdout; "endoscapes.zip" in stdout; "ctu-uhb-ctgdb" in stdout` | ✅ PASS |
| **DATA-06** Retomada de download interrompido (`-C -` / `--continue`) | Segunda execução retoma, não recomeça | — **sem asserção** (stubs `cp`/`wget` não exercitam resume; nenhum teste verifica os flags) | ⚠️ **Coverage gap** (mutantes M10/M11 sobreviveram) |
| **DATA-07** Idempotência por dataset (pula se `.complete`) | Dataset completo é pulado, não rebaixado | `test_download_datasets.py:118-120` — `assert rc==0; status=="pulado"; not (STUB_RAN).exists()`; `:284-288` main mistura | ✅ PASS |
| **DATA-08** Checagem de espaço antes de baixar | Aborta se livre < necessário | `test_download_state.py:34-35` — `assert rc!=0; "insuficiente" in stderr` (need 999 TB); `:27` espaço suf. → rc 0 | ✅ PASS |
| **DATA-09** `.complete` só em sucesso; parcial ≠ completo | Falha não deixa sentinela | `test_download_datasets.py:93-95` (ctu vazio), `:104-105` (py falha), `:178-180` (icbhi ambas falham), `:229-231` (endo zip inválido) — `assert not .complete.exists()` | ✅ PASS |
| **DATA-10** Log por dataset + resumo (baixado/pulado/falhou) | Resumo final lista cada dataset | `test_download_datasets.py:286-288` — `assert "CTU-UHB: pulado"/"ICBHI: pulado"/"Endoscapes: baixado" in stderr`; `:298-300` (baixado/falhou/baixado) | ✅ PASS |
| **DATA-11** Ferramenta ausente falha nomeando-a | Exit ≠ 0 + nome da ferramenta | `test_download_tools.py:17-18,26-27,35-36,44-45` — `assert rc!=0; "curl"/"wget"/"unzip"/"python" in stderr` | ✅ PASS |
| **DATA-12** Checksum quando disponível (P3) | — | **Diferido** (tasks.md:285, spec Out-of-Scope). Não bloqueia demo. | ⏭️ Diferido OK |
| **DATA-13** ICBHI primária+alt; validar zip PK real; `--no-check-certificate` só na alt | HTML (403) rejeitado, cai no fallback; `.complete` só sobre zip real | `test_download_datasets.py:162-170` (dataverse HTML → fallback zip → OK); `test_download_verify.py:22-30` (HTML rejeitado); `:14-19` (zip real aceito) | ✅ PASS (⚠️ ver nota) |

**Nota DATA-13**: a cláusula "`--no-check-certificate` só na alternativa" é garantida estruturalmente no código (`download_datasets.sh:154`, flag só no ramo `elif` do fallback), mas nenhum teste assere que a chamada primária ao Dataverse NÃO recebe o flag — spec-precision gap menor, não bloqueante.

**Edge cases da spec**:
- Diretório sem `.complete` (parcial) → refaz: coberto indiretamente (is_complete só reconhece a sentinela — M3 mata).
- Zip ICBHI corrompido (verify PK ok mas unzip falha) → sem `.complete`: **não testado isoladamente** (fixture é sempre zip válido; o caso "PK ok + unzip falha" não tem teste). Risco residual baixo.
- HTML 403 disfarçado de sucesso → rejeitado por assinatura: ✅ coberto (`test_download_datasets.py:162`, `test_download_verify.py:22`).
- Sem rede → falha cedo sem sentinela: coberto via `fail` mode (`:178-180`).

**Status**: ✅ 11/11 ACs ativos com evidência (DATA-06 com coverage gap flagado; DATA-12 diferido).

---

## Discrimination Sensor

Mutações injetadas em `backend/scripts/download_datasets.sh`, cada uma validada por `git diff` (exatamente 1 hunk) ANTES de julgar, e revertida com `git checkout --`.

| # | Local | Descrição | Testes | Killed? |
| --- | --- | --- | --- | --- |
| M1 | `verify_zip:65` | `!= "504b0304"` → `== "504b0304"` (inverte magic) | verify | ✅ Killed (2 fail) |
| M2 | `verify_zip:59` | tamanho `-lt` → `-gt` | verify | ✅ Killed (4 fail) |
| M3 | `is_complete:73` | `[ -f .complete ]` → `true` (sempre completo) | state + integ | ✅ Killed (12 fail) |
| M4 | `check_disk_space:84` | `-lt` → `-gt` (inverte espaço) | state | ✅ Killed (2 fail) |
| M5 | `fetch_ctu_uhb:111` | `-lt 1` → `-lt 0` (pula checagem `.hea`/`.dat`, marca vazio) | integ (ctu) | ✅ Killed (1 fail) |
| M6 | `fetch_icbhi:154` | fallback `elif` → `elif false` (remove fonte alternativa) | integ (icbhi) | ✅ Killed (2 fail) |
| M7 | `_run_fetch:217` | `FETCH_RC=1` → `FETCH_RC=0` (não sinaliza falha no exit) | integ (main) | ✅ Killed (1 fail) |
| M8 | `fetch_endoscapes:190` | remove `verify_zip` (só `unzip`) | integ (endoscapes) | ❌ **Survived** |
| M9 | `_curl_zip:134` | remove `rm -f "$out"` na falha de verify | integ (todos) | ❌ **Survived** |
| M10 | `fetch_endoscapes:184` | remove `--continue` (resume wget) | integ (todos) | ❌ **Survived** |
| M11 | `_curl_zip:128` | remove `-C -` (resume curl) | integ (todos) | ❌ **Survived** |

**Sensor depth**: P1/data-integrity — 11 mutações (7 nomeadas + 4 vizinhos não nomeados).
**Resultado**: 7/11 killed. Os 4 sobreviventes são analisados abaixo — nenhum é bug de script nem `.complete` sobre lixo.

### Análise dos sobreviventes (nenhum bloqueia o fechamento)

- **M8 (endoscapes `verify_zip` redundante)**: `unzip` é backstop — conteúdo não-zip faz `unzip` falhar de qualquer modo, então o desfecho crítico (`.complete` NÃO escrito sobre lixo) se mantém. O teste `endoscapes_zip_invalido` usa `"not a zip"`, que morre no `unzip`. Falta um teste com HTML/200 servido ao endoscapes que distinga `verify_zip` de `unzip`. **Defesa em profundidade não testada, desfecho preservado.** Risco residual baixo.
- **M9 (`_curl_zip` sem `rm -f` na falha de verify)**: no mundo real, um HTML residual poderia corromper um `curl -C -` de retomada da fonte seguinte; com stubs `cp` o fallback sobrescreve limpo, então nenhum teste detecta. Ligado ao gap de resume. Risco residual.
- **M10/M11 (flags de resume `--continue` / `-C -`)**: **DATA-06 (retomada) não tem cobertura comportamental** — os flags estão corretos e presentes no script (verificado por leitura: `:184` e `:128`), mas nenhum teste assere que são passados. Stubs `cp` não modelam resume. É gap de teste, não bug de código.

---

## Vacuous / tautological test check

- Nenhum teste itera coleção sem asserir efeito. Todos os testes de integração assertam **efeito no filesystem** (`.complete`, `registro.wav`/`1001.hea`) ALÉM de `rc` e `FETCH_STATUS` — não só código de saída.
- `verify_zip`: fixture é `os.urandom(5000)` (incompressível → mantém tamanho > `MIN_ZIP_BYTES` e header `PK`). Não-tautológico.
- `test_make_data_invoca_o_script`: assere substring no Makefile; alvo `data:` confirmado real (`Makefile:9-10` executa o script), não comentário.
- Nenhum teste assere a negação do literal do mutante em vez do valor correto.

**Resultado**: nenhum teste vacuoso encontrado.

---

## Code Quality

| Princípio | Status |
| --- | --- |
| Código mínimo, sem features além do pedido | ✅ |
| Mudanças cirúrgicas, só o script + testes | ✅ |
| Sem abstração para uso único | ✅ |
| Casa padrões existentes (pytest + stubs no PATH) | ✅ |
| Spec-anchored: valores asseridos = desfecho da spec | ✅ (1 spec-precision gap menor em DATA-13) |
| Cobertura por camada (helpers unit; aquisições integração) | ✅ |
| Todo teste mapeia p/ AC/edge/Done-when — sem testes órfãos | ✅ |
| Guidelines documentadas seguidas | ✅ pytest/ruff (`pyproject.toml`/`ruff.toml`); sem shellcheck/bats no ambiente |

---

## Gate Check

- **Gate command**: `make lint && pytest -q`
- **Lint**: `ruff check backend` → All checks passed!
- **Unitários F0**: `pytest -q -m "not integration" backend/tests/scripts` → **19 passed**
- **Integração F0**: `pytest -q -m integration` (test_download_datasets) → **13 passed**
- **Suíte completa**: `pytest -q` → **197 passed, 0 failed, 0 skipped** (37.4s)
- **F0 total**: **32 testes** (19 unit + 13 integração). A tasks.md alega "25 de F0" — a contagem real é maior (32); mais cobertura que o alegado, não menos. Sem testes deletados/enfraquecidos.

---

## Requirement Traceability Update

| Requisito | Status anterior | Novo status |
| --- | --- | --- |
| DATA-01 | Implementing | ✅ Verified |
| DATA-02 | Implementing | ✅ Verified |
| DATA-03 | Implementing | ✅ Verified |
| DATA-05 | Implementing | ✅ Verified |
| DATA-06 | Implementing | ⚠️ Verified c/ coverage gap (resume sem teste; flags corretos no código) |
| DATA-07 | Implementing | ✅ Verified |
| DATA-08 | Implementing | ✅ Verified |
| DATA-09 | Implementing | ✅ Verified |
| DATA-10 | Implementing | ✅ Verified |
| DATA-11 | Implementing | ✅ Verified |
| DATA-12 | Pending | ⏭️ Diferido (P3 opcional) |
| DATA-13 | Implementing | ✅ Verified (spec-precision gap menor: `--no-check-certificate`-só-na-alt não asserido) |

---

## Riscos residuais (aceitáveis — não bloqueiam o fechamento)

1. **DATA-06 resume sem teste comportamental** (M10/M11 sobreviveram). Flags `-C -`/`--continue` corretos e presentes; harness com stubs `cp` não modela retomada. Recomendação futura: stub `curl`/`wget` que verifique presença do flag ou simule byte-range.
2. **`verify_zip` do endoscapes e `rm -f` de falha do `_curl_zip` não testados isoladamente** (M8/M9). São defesa em profundidade; o desfecho crítico (`.complete` nunca sobre não-zip) permanece garantido por outros caminhos (`unzip` backstop; M1 mata a inversão de assinatura).
3. **Edge case "zip PK válido mas `unzip` falha" (ICBHI corrompido)** não tem teste dedicado. Baixo risco: `unzip` retorna ≠ 0 e o código não marca `.complete` (`fetch_icbhi:162-166`).
4. **Spec-precision (DATA-13)**: ausência de asserção de que o Dataverse não recebe `--no-check-certificate`. Garantido estruturalmente.

**Nenhum sobrevivente representa**: bug de script, aquisição que marca `.complete` sobre lixo, ou quebra de idempotência. A propriedade de integridade central ("`.complete` só sobre zip PK real, só em sucesso") é morta por M1 e coberta por `test_pagina_html`/`test_icbhi_*_html`.

---

## Summary

**Overall**: ✅ **Ready — F0 pode ser fechada.**

**Spec-anchored check**: 11/11 ACs ativos com evidência (DATA-06 flagado como coverage gap; DATA-12 diferido; 1 spec-precision gap menor em DATA-13)
**Sensor**: 11 mutações, 7 killed, 4 survived (todos analisados — defesa-em-profundidade/resume, não bugs)
**Gate**: 197 passed, 0 failed; lint limpo

**O que funciona**: aquisição idempotente das três fontes; sentinela `.complete` só em sucesso; rejeição de HTML/403 por assinatura PK; fallback do ICBHI; isolamento de falha (um dataset falho não derruba os outros, exit ≠ 0); checagem de espaço e de ferramentas; `make data` fiado ao script; `data/` gitignored com `README.md` versionado.

**Gaps (não bloqueantes)**: resume (DATA-06) sem teste; verificações de defesa-em-profundidade do endoscapes/`_curl_zip` não isoladas; edge "PK-ok-mas-unzip-falha" sem teste dedicado.

**Next steps**: fechar F0. Opcional (dívida de teste P2): adicionar stub que verifique flags de resume e um teste de HTML servido ao endoscapes.
