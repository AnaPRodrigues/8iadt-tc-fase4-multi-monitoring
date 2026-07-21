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

---
---

# EMENDA URFD/BIDMC — Validation

**Date**: 2026-07-21
**Spec**: `.specs/features/data-acquisition/spec.md` (DATA-14, DATA-15)
**Design**: `.specs/features/data-acquisition/design.md` — seção "EMENDA (2026-07-21)"
**Diff range**: `da978fd..cd42c04` (T8, T9, T10), branch `feat/f3-vitals-anomaly`
**Verifier**: independent sub-agent (author ≠ verifier, evidence-or-zero). Núcleo (T1–T7) permanece PASS acima; esta seção cobre só o incremento.

**Verdict**: ✅ **PASS — a emenda pode fechar.** Nenhum bloqueador. Dois riscos residuais aceitos (ver seção de riscos): um gap de teste para "unzip falha" no URFD (espelha o mesmo gap já aceito no núcleo para o ICBHI), e uma folga não-exclusiva no glob de completude do BIDMC (`*.hea` inclui os arquivos de numerics, então a checagem não distingue *só numerics* de *ambos os grupos* num cenário artificial onde a forma de onda falhasse por completo e os numerics sozinhos tivessem sucesso).

---

## Task Completion

| Task | Status | Notas |
| --- | --- | --- |
| T8 (`fetch_urfd` — sentinela por sequência) | ✅ Done | `acd304f` |
| T9 (`fetch_bidmc` — forma de onda + numerics) | ✅ Done | `ec54dfa` |
| T10 (integração ao `main` e ao resumo) | ✅ Done | `cd42c04` |

---

## Achados críticos declarados pelo autor — verificação direta

| Achado alegado | Verificado no código? | Evidência |
| --- | --- | --- |
| URFD: `printf -v i '%02d' "$n"` fixa o padding em 2 dígitos, corrigindo o bug de `seq -w` com N pequeno | ✅ **Sim, código real** (não é só comentário) | `backend/scripts/download_datasets.sh:259,263`; morto por mutação (ver M3 abaixo — 3 testes falham ao trocar por `i="$n"`) |
| BIDMC: `fetch_bidmc` faz DUAS chamadas a `dl_database` (formas de onda `records='all'` via `get_record_list`, depois numerics com nomes `[r+'n' for r in records]`, não hardcoded) | ✅ **Sim, presente no código** — `download_datasets.sh:295-300` | Confirmado por leitura direta. **Porém**: o sensor não consegue discriminar esse comportamento (ver M4 abaixo) porque o stub `PY` usado nos testes é uma caixa-preta que ignora o argumento `-c` — logo a alegação "duas chamadas, nomes derivados" só está provada por leitura de código, não por teste automatizado |
| BIDMC: `.complete` só é escrito quando AMBOS os grupos (forma de onda + numerics) estão presentes | ✅ **Sim, e testado** | `download_datasets.sh:306-313`; `test_download_datasets.py:476-486` (`test_bidmc_sem_numerics_nao_marca_completo`) — morto por M5 abaixo |

---

## Spec-Anchored Acceptance Criteria

| Critério (WHEN X THEN Y) | Desfecho da spec | `file:line` + asserção | Resultado |
| --- | --- | --- | --- |
| **DATA-14** URFD: cada sequência baixada, verificada (`verify_zip`), extraída, com sentinela própria | Sequência completa → `.complete` na própria pasta; conteúdo real extraído | `test_download_datasets.py:404-414` — `assert (urfd/.complete).is_file(); for seq: (urfd/seq/.complete).is_file(); (urfd/seq/registro.wav).is_file()` (unzip real) | ✅ PASS |
| **DATA-14** URFD: sentinela de DATASET só quando TODAS as sequências completam | 1 sequência falha → `data/urfd/.complete` ausente; demais completam normalmente | `test_download_datasets.py:417-431` — `assert rc!=0; status=="falhou"; not (urfd/.complete).exists(); not (urfd/fall-02/.complete).exists(); (urfd/fall-01/.complete).is_file(); (urfd/adl-01/.complete).is_file()` | ✅ PASS |
| **DATA-14** URFD: isolamento de falha entre sequências (uma falha não impede as demais) | Sequências não relacionadas ainda baixam e completam | mesmo teste acima (`:430-431`) — `fall-01`/`adl-01` completam apesar de `fall-02` falhar | ✅ PASS |
| **DATA-14** URFD: sequência já completa não é rebaixada (skip sem rebaixar) | Sequência com `.complete` prévio não aciona `wget` de novo | `test_download_datasets.py:434-445` — `assert "fall-01" not in call_log.read_text().split(); (urfd/fall-02/.complete).is_file()` (log de chamadas via stub confirma que `fall-01` nunca foi baixado) | ✅ PASS |
| **DATA-14** URFD: variáveis no topo (`URFD_BASE_URL`, `URFD_N_FALL`, `URFD_N_ADL`) | Defaults corretos (`fenix.ur.edu.pl`, 30, 40) | `test_download_datasets.py:395-401` — `assert "fenix.ur.edu.pl" in stdout; "30" in stdout; "40" in stdout` | ✅ PASS |
| **DATA-15** BIDMC: exige AMBOS os grupos (forma de onda + numerics) antes de `.complete` | Só forma de onda (sem `*n.hea`) → falha, sem `.complete` | `test_download_datasets.py:476-486` — `assert rc!=0; status=="falhou"; not (bidmc/.complete).exists()` | ✅ PASS |
| **DATA-15** BIDMC: sucesso com ambos os grupos marca completo | Forma de onda + numerics presentes → `.complete` | `test_download_datasets.py:465-473` — `assert rc==0; status=="baixado"; (bidmc/.complete).is_file()` | ✅ PASS |
| **DATA-15** BIDMC: download vazio/falho não marca completo | `wfdb` retorna erro → sem sentinela | `test_download_datasets.py:489-496` — `assert rc!=0; not (bidmc/.complete).exists()` | ✅ PASS |
| **DATA-15** BIDMC: já completo → pula sem rebaixar | Sentinela presente → `python` não é chamado | `test_download_datasets.py:499-510` — `assert rc==0; status=="pulado"; not (dest/STUB_RAN).exists()` | ✅ PASS |
| **T10** `main` chama as 5 fontes; falha de uma não impede as demais; resumo cita as 5 | Resumo final lista `CTU-UHB`/`ICBHI`/`Endoscapes`/`URFD`/`BIDMC` com seus status | `test_download_datasets.py:292-308` (mistura skip/baixa) e `:311-327` (ICBHI falha, as outras 4 completam) — `assert "URFD: baixado" in stderr; "BIDMC: baixado" in stderr; (urfd/.complete).is_file(); (bidmc/.complete).is_file()` | ✅ PASS |
| **T10** checagem de espaço soma estimativas só das fontes ainda não completas (URFD/BIDMC incluídos) | Estimativa absurda de fonte pendente aborta; de fonte já completa é ignorada | `test_download_datasets.py:330-342` (`URFD_EST_BYTES` absurdo + pendente → `RC=1`, "insuficiente"); `:345-355` (mesma estimativa absurda, mas já completo → `RC=0`) | ✅ PASS |

**Status**: ✅ 11/11 critérios ativos da emenda cobertos com evidência `file:line`. Nenhum spec-precision gap novo introduzido pela emenda (a spec define desfechos precisos — sentinela presente/ausente, status de string — e todos os testes miram esses valores exatos, não só "existe uma asserção").

---

## Discrimination Sensor

9 mutações injetadas em `backend/scripts/download_datasets.sh` (working tree real, não scratch — não havia isolamento de git worktree disponível no ambiente; cada mutação foi confirmada via `git diff` como exatamente 1 hunk, testada, e revertida com `git checkout --` antes da próxima). Suíte alvo: `pytest -q backend/tests/integration/test_download_datasets.py -k "urfd or bidmc or main"` (12 testes).

| # | Local | Descrição | Killed? |
| --- | --- | --- | --- |
| 1 | `_fetch_urfd_seq:221` | `if is_complete "$dest"` → `if false && is_complete "$dest"` (nunca reconhece sequência completa, sempre rebaixa) | ✅ Killed (`test_urfd_sequencia_ja_completa_nao_e_rebaixada` falha) |
| 2 | `fetch_urfd:267-271` | Marca `.complete` de dataset mesmo com `rc != 0` (ignora falha de sequência) | ✅ Killed (`test_urfd_sequencia_falha_nao_marca_completo_de_dataset_mas_demais_completam` falha) |
| 3 | `fetch_urfd:259,263` | `printf -v i '%02d' "$n"` → `i="$n"` (remove padding fixo, reexpõe o bug do `seq -w`) | ✅ Killed (3 testes falham: todas-sucesso, sequência-falha, já-completa) |
| 4 | `fetch_bidmc:299-300` | Remove a segunda chamada de `dl_database` (só formas de onda) — achado crítico do BIDMC | ❌ **Survived** — ver análise abaixo |
| 5 | `fetch_bidmc:309` | `[ "$n_hea" -lt 1 ] \|\| [ "$n_numerics" -lt 1 ]` → só `[ "$n_hea" -lt 1 ]` (ignora numerics) | ✅ Killed (`test_bidmc_sem_numerics_nao_marca_completo` falha) |
| 6 | `main:357` | Remove `_run_fetch "BIDMC" fetch_bidmc` da lista de orquestração | ✅ Killed (3 testes de `main` falham; `set -u` gera erro de variável não associada ao acessar `FETCH_RESULT[BIDMC]` no resumo) |
| 7 | `main:344-345` | `is_complete ... \|\| need=$((need + X))` → soma incondicional de `URFD_EST_BYTES`/`BIDMC_EST_BYTES` (ignora se já completo) | ✅ Killed (`test_main_ignora_estimativa_de_fonte_ja_completa` falha) |
| 8 | `_fetch_urfd_seq:235-239` | `mark_complete "$dest"` chamado ANTES do `unzip` (ordem errada — completaria mesmo se o `unzip` falhasse depois) | ❌ **Survived** — ver análise abaixo |
| 9 | `_fetch_urfd_seq:231-234` | Remove `rm -f "$zip"` na falha de `verify_zip` | ❌ **Survived** — ver análise abaixo |

**Sensor depth**: lightweight (feature não-P0), 9 mutações — acima do mínimo de 1–3, cobrindo os alvos de alto valor pedidos.
**Resultado**: 6/9 killed, 3 survived (analisados abaixo — nenhum é bug de idempotência silenciosa; todos são gaps de teste já com padrão equivalente aceito no núcleo).

### Análise dos sobreviventes

- **M4 (BIDMC — remove a 2ª chamada `dl_database`)**: sobrevive porque o stub `PY` usado nos testes é um script fixo que **ignora completamente o argumento `-c`** (não interpreta nem executa o heredoc real) — ele só reage a variáveis de ambiente (`BIDMC_DEST`) para decidir quais arquivos fabricar. Isso significa que nenhuma mutação *dentro* do heredoc Python (seja remover a 2ª chamada, seja hardcodear os nomes dos numerics em vez de derivá-los de `get_record_list`) é detectável pelo harness de teste atual — é uma limitação estrutural do approach de stub-por-substituição-total, não um teste fraco corrigível trivialmente sem executar Python real. O desfecho crítico ("não marca completo sem numerics") **é** verificado, e é verificado independentemente (M5, killed) — então, na prática, se a implementação real deixasse de baixar numerics, o resultado observável (nenhum `*n.hea` no disco) ainda impediria `.complete`. Risco residual: baixo, mas real — a "forma como" a segunda chamada é feita (não hardcoded, derivada de `get_record_list`) só está garantida por leitura de código, nunca por teste automatizado.
- **M8 (URFD — `mark_complete` antes do `unzip`)**: sobrevive porque **nenhum teste do URFD simula um zip que passa em `verify_zip` mas falha no `unzip`** — a fixture de zip é sempre válida (`_zip_fixture`), e o único cenário de "falha de sequência" testado é falha do próprio `wget` (exit 9), não de unzip corrompido. Este é **exatamente o mesmo gap já identificado e aceito no núcleo** para o ICBHI (ver linha 49 da seção do núcleo acima: "zip PK válido mas unzip falha... não testado isoladamente. Risco residual baixo"). A emenda herda o padrão, não introduz um bug novo — mas também não fecha o gap.
- **M9 (URFD — falta `rm -f "$zip"` na falha de `verify_zip`)**: mesma causa raiz de M8 — sem teste de zip inválido para o URFD (diferente do Endoscapes/ICBHI, que têm `test_endoscapes_zip_invalido_nao_marca_completo` e o teste de HTML do ICBHI), este ramo de código nunca é exercitado. Resíduo de arquivo teórico numa retomada futura; risco baixo (a sequência já falhou e não seria marcada completa de qualquer forma — M2 garante isso no nível de dataset).

---

## Achado adicional (fora do escopo de mutação) — verificação por leitura + reprodução

Ao inspecionar a checagem de completude do BIDMC (`download_datasets.sh:306-313`), o padrão de contagem usa dois globs que **não são mutuamente exclusivos**:

```bash
n_hea=$(find "$dest" -maxdepth 1 -name '*.hea' | wc -l)         # inclui bidmcNNn.hea também!
n_numerics=$(find "$dest" -maxdepth 1 -name '*n.hea' | wc -l)
```

Reproduzido isoladamente (`/tmp/bidmc_check`, só arquivos `bidmc01n.hea`/`bidmc01n.dat` presentes): `n_hea=1` e `n_numerics=1` — ambos os testes de completude passam **mesmo sem nenhum arquivo de forma de onda genuíno** (só sufixo `n`). Ou seja, a checagem não verifica de fato "pelo menos 1 arquivo de forma de onda E pelo menos 1 de numerics" como dois conjuntos distintos — ela verifica "pelo menos 1 arquivo `.hea` no total" (que os numerics já satisfazem sozinhos) "E pelo menos 1 terminado em `n.hea`". Um cenário em que a chamada de forma de onda falhasse silenciosamente (sem lançar exceção Python, ex.: `dl_database` engolindo erro por registro) enquanto os numerics tivessem sucesso completo passaria essa checagem incorretamente.

**Por que não é bloqueador**: as duas chamadas estão no mesmo script Python sequencial (`import wfdb; ...; dl_database(records=records); ...; dl_database(records=numerics)`), sem `try/except` — se a primeira chamada lançar exceção, o processo Python inteiro aborta antes de chegar à segunda linha, então o cenário "0 formas de onda, numerics completos" exigiria que `dl_database` silenciosamente não escrevesse nada nem lançasse erro, o que não foi observado no achado empírico documentado no design (`bidmc01` isolado *fez* baixar `.hea`/`.dat` de forma de onda). É uma lacuna teórica de robustez, não um caminho realista dado o comportamento confirmado do `wfdb`.

**Recomendação (não bloqueante)**: trocar o glob de `n_hea` por algo que exclua o sufixo `n` (ex.: `find "$dest" -maxdepth 1 -name '*.hea' ! -name '*n.hea' | wc -l`) para tornar os dois grupos genuinamente exclusivos. Nenhum teste atual cobre esse cenário (nem antes nem depois de um eventual fix), então isso também é uma lacuna de teste a registrar, não só de código.

---

## Vacuous / tautological test check

- Nenhum teste da emenda itera coleção sem asserir efeito. Todos assertam efeito em disco (`.complete`, arquivos extraídos como `registro.wav`) além de `rc`/`status`.
- `test_urfd_sequencia_ja_completa_nao_e_rebaixada` usa um `call_log` real (stub `wget` grava a sequência chamada) para provar ausência de rechamada — não é uma asserção fraca de "não lançou erro", é positiva sobre o que NÃO aconteceu.
- `test_bidmc_sem_numerics_nao_marca_completo` distingue exatamente o cenário do achado crítico (stub que simula "só forma de onda, sem numerics") — não é genérico.
- Nenhum teste assere só `rc==0` sem checar o sistema de arquivos.

**Resultado**: nenhum teste vacuoso encontrado na emenda.

---

## Code Quality

| Princípio | Status |
| --- | --- |
| Código mínimo, sem features além do pedido | ✅ |
| Mudanças cirúrgicas (só `download_datasets.sh` + `test_download_datasets.py`) | ✅ |
| Sem abstração para uso único | ✅ (`_fetch_urfd_seq` é a única abstração nova, e é reusada 70x — justificada) |
| Casa padrões existentes (mesmo contrato `is_complete`/`mark_complete`/`verify_zip` do núcleo) | ✅ |
| Spec-anchored: valores asseridos = desfecho da spec | ✅ |
| Cobertura por camada (integração para aquisição/orquestração, conforme a matriz) | ✅ |
| Todo teste mapeia p/ AC/edge/Done-when — sem testes órfãos | ✅ |
| Guidelines documentadas seguidas | ✅ pytest/ruff; mesmo padrão do núcleo |

---

## Gate Check

- **Gate command**: `make lint && pytest -q`
- **Lint**: `ruff check backend` → All checks passed!
- **Suíte completa**: `pytest -q` → **207 passed, 0 failed, 0 skipped** (~32-36s)
- **Testes só da emenda** (`-k "urfd or bidmc or main"`): **12 passed, 11 deselected**
- **F0 total real**: **42 testes** (32 núcleo + 10 da emenda: 4 URFD + 4 BIDMC + 2 `main`/T10, confirmado via `git diff --stat` do range `da978fd..cd42c04` nos testes: 13→23 no arquivo de integração, mais os 19 unitários do núcleo inalterados)
- **Nota sobre a baseline alegada**: `tasks.md:23` afirma "207 testes verdes (35 de F0)" — a contagem real de testes específicos de F0 é **42**, não 35. Discrepância de documentação (provavelmente uma contagem desatualizada de um estágio intermediário), não um problema de cobertura — a contagem real é maior que a alegada, mesmo padrão observado no núcleo (`validation.md:119` já notou algo similar para "25 de F0" vs. 32 reais). Recomenda-se corrigir o número em `tasks.md`, não bloqueante.
- **Testes deletados/enfraquecidos**: nenhum. Delta é +10 testes líquidos no arquivo de integração.

---

## Requirement Traceability Update

| Requisito | Status anterior | Novo status |
| --- | --- | --- |
| DATA-14 | Pending | ✅ Verified |
| DATA-15 | Pending | ✅ Verified (risco residual documentado: exclusividade do glob de completude — ver seção "Achado adicional") |

---

## Riscos residuais (aceitáveis — não bloqueiam o fechamento)

1. **URFD sem teste de "zip válido mas `unzip` falha"** (M8/M9 sobreviveram). Mesmo padrão já aceito no núcleo para o ICBHI. Recomendação futura: um teste com fixture "arquivo PK válido mas corpo de zip corrompido" para o URFD, espelhando o que falta no ICBHI.
2. **BIDMC: `dl_database` real não é exercitado pelo sensor** (M4 sobreviveu) — o stub `PY` ignora o código Python passado, então a estrutura exata "2 chamadas, nomes derivados de `get_record_list`" só é garantida por leitura de código, não por teste. O desfecho observável (sem numerics → sem `.complete`) está protegido por M5 (killed).
3. **BIDMC: glob `*.hea` não exclui numerics** — a checagem de completude tecnicamente permite (num cenário teórico de falha silenciosa da 1ª chamada) marcar completo com só numerics. Não reproduzível dado o comportamento real confirmado do `wfdb` (chamada única sequencial, sem try/except, falha aborta antes da 2ª chamada). Fix sugerido: glob exclusivo (`! -name '*n.hea'`) — não bloqueante.
4. **Discrepância de contagem de testes em `tasks.md`** ("35 de F0" vs. 42 reais) — documentação desatualizada, não afeta a cobertura real.

**Nenhum sobrevivente representa**: idempotência quebrada, `.complete` marcado sobre download vazio/parcial em um cenário realista, ou perda de isolamento de falha entre fontes. A propriedade central da emenda ("sentinela por sequência + sentinela de dataset só com 100% das sequências" para o URFD; "ambos os grupos antes de completar" para o BIDMC) está coberta e é morta pelas mutações correspondentes (M1/M2/M3 para URFD; M5 para BIDMC).

---

## Summary (Emenda)

**Overall**: ✅ **Ready — a emenda (T8–T10, DATA-14/DATA-15) pode ser fechada.**

**Spec-anchored check**: 11/11 critérios ativos com evidência `file:line`; 0 spec-precision gaps novos
**Sensor**: 9 mutações, 6 killed, 3 survived (todos analisados — gaps de teste equivalentes aos já aceitos no núcleo, nenhum bug de idempotência)
**Gate**: 207 passed, 0 failed; lint limpo; F0 total real = 42 testes (32 núcleo + 10 emenda)

**O que funciona**: sentinela por sequência do URFD (idempotência de grão fino sem rebaixar o que já está pronto); padding fixo de 2 dígitos que corrige o bug real do `seq -w`; sentinela de dataset do URFD só com 100% das sequências; `fetch_bidmc` com 2 chamadas (forma de onda + numerics, nomes derivados de `get_record_list`, confirmado por leitura de código); `.complete` do BIDMC exigindo evidência de numerics (testado e morto por mutação); `main`/resumo/checagem de espaço estendidos corretamente às 5 fontes.

**Gaps não-bloqueantes**: URFD sem teste de zip corrompido (paridade com gap já aceito do ICBHI); estrutura interna do `fetch_bidmc` (número de chamadas, origem dos nomes) não verificável pelo sensor por limitação do stub `PY`; glob de completude do BIDMC não é estritamente exclusivo entre forma de onda e numerics (risco teórico, não reproduzível com o comportamento real confirmado do `wfdb`); `tasks.md` com contagem de testes desatualizada.

**Next steps**: fechar a emenda. Opcional (dívida de teste P2/P3): (a) teste de zip corrompido para URFD; (b) glob exclusivo para `n_hea` no BIDMC; (c) corrigir a contagem em `tasks.md`.
