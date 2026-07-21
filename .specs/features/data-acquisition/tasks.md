# F0 — Data Acquisition Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user.**

---

**Design**: `.specs/features/data-acquisition/design.md`
**Status**: In Progress — 7/7 tarefas implementadas e commitadas; **Verifier pendente** (adiado a pedido do usuário)

## Progresso

| Fase | Tarefas | Status |
| --- | --- | --- |
| 1 — Helpers | T1–T3 | ✅ (`9045e32`, `b5b779c`, `b1ce73a`) |
| 2 — Aquisições | T4–T6 | ✅ (`2a8a832`, `9622662`, `58dc9c1`) |
| 3 — Orquestração | T7 | ✅ (`ee405af`) |

Suíte: 197 testes verdes (25 de F0), lint limpo. Falta o Verifier independente (passo de fechamento).

---

## Test Coverage Matrix

> Gerada do design + stack confirmada. **Guidelines encontradas: nenhuma além de pytest/ruff (config em `pyproject.toml`/`ruff.toml`) — defaults fortes aplicados.** Não há shellcheck nem bats no ambiente; o script shell é testado via **pytest** dando `source` no script e chamando funções com ferramentas de download **dubladas no PATH** (stubs), sem download real.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Helpers puros do script (`verify_zip`, `is_complete`/`mark_complete`, `check_disk_space`, `require_tools`) | unit | Todos os ramos; cada edge case da spec (zip real vs HTML/vazio/pequeno; sentinela presente/ausente; espaço suf./insuf.; ferramenta ausente) | `backend/tests/scripts/test_download_*.py` | `pytest -q -m "not integration"` |
| Aquisições e orquestração (`fetch_ctu_uhb`, `fetch_icbhi` c/ fallback, `fetch_endoscapes`, `main`) | integration | Happy path + skip-se-completo + fonte primária falha→fallback + conteúdo HTML rejeitado + 1 dataset falha não derruba os outros | `backend/tests/integration/test_download_datasets.py` | `pytest -q` |
| Script como entrypoint / variáveis | none | — (coberto pelos testes acima; sem linter de shell disponível) | — | — |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Após tarefas só com testes unitários | `pytest -q -m "not integration"` |
| Full | Após tarefas com testes de integração | `pytest -q` |
| Build | Fim de fase / tarefas de config | `make lint && pytest -q` (ruff cobre os testes `.py`; o script `.sh` não tem linter disponível) |

---

## Execution Plan

7 tarefas em 3 fases; cabe num único batch (≤8) → execução inline, sem sub-agentes. O Verifier roda ao final de qualquer forma.

### Phase 1: Helpers testáveis

```
T1 → T2 → T3
```

### Phase 2: Aquisições (com stubs)

```
T4 → T5 → T6
```

### Phase 3: Orquestração

```
T7
```

---

## Task Breakdown

### T1: Esqueleto sourceable + variáveis + `require_tools`

**What**: Criar `download_datasets.sh` sourceable (guard que só roda `main` se executado, não se `source`), variáveis de URL/paths no topo (DATA-05), e `require_tools` (DATA-11).
**Where**: `backend/scripts/download_datasets.sh`, `backend/tests/scripts/test_download_tools.py`
**Depends on**: None
**Requirement**: DATA-05, DATA-11

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `[ "${BASH_SOURCE[0]}" = "$0" ] && main "$@"` — sourceável sem efeitos
- [ ] Variáveis no topo: `DATA_DIR`, `ICBHI_DATAVERSE_URL`, `ICBHI_ORIGINAL_URL`, `ENDOSCAPES_URL`, `CTU_DB`, estimativas de tamanho
- [ ] `require_tools` falha nomeando a ferramenta ausente (`curl`/`unzip`/`python`), exit ≠ 0
- [ ] Testes (pytest sourcing): todas as ferramentas presentes → ok; cada uma ausente (PATH stub) → erro nomeando-a
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f0): esqueleto do script de dados, variaveis e require_tools`

---

### T2: `verify_zip` — assinatura PK + tamanho

**What**: Função que aceita um arquivo só se for zip real (magic bytes `PK\x03\x04`) e acima de um tamanho mínimo; rejeita HTML/0-byte (DATA-13; lição L-020).
**Where**: `backend/scripts/download_datasets.sh` (modificar), `backend/tests/scripts/test_download_verify.py`
**Depends on**: T1
**Requirement**: DATA-09, DATA-13

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `verify_zip <path>` retorna 0 só para zip real; ≠ 0 para HTML, arquivo vazio e arquivo menor que o mínimo
- [ ] Testes: fixture zip real (gerado com `zip`/`python zipfile`), página HTML 403 salva como `.zip`, arquivo 0-byte, arquivo pequeno não-zip
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f0): verify_zip por assinatura PK e tamanho`

---

### T3: Sentinela + checagem de espaço

**What**: `is_complete`/`mark_complete` (contrato de idempotência, DATA-07) e `check_disk_space` (DATA-08).
**Where**: `backend/scripts/download_datasets.sh` (modificar), `backend/tests/scripts/test_download_state.py`
**Depends on**: T2
**Requirement**: DATA-07, DATA-08, DATA-09

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `is_complete <dir>` verdadeiro só com `.complete` presente; `mark_complete` cria a sentinela
- [ ] `check_disk_space <min_bytes>` falha (exit ≠ 0) quando o livre < mínimo, passa quando ≥
- [ ] Testes: sentinela ausente/presente; espaço suficiente vs. um mínimo absurdo (ex.: 999 TB) que força a falha
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f0): sentinela de idempotencia e checagem de espaco`

---

### T4: `fetch_ctu_uhb`

**What**: Baixar CTU-UHB via `wfdb.dl_database` e só marcar `.complete` após confirmar contagem mínima de `.hea`/`.dat` (DATA-01, DATA-09).
**Where**: `backend/scripts/download_datasets.sh` (modificar), `backend/tests/integration/test_download_datasets.py`
**Depends on**: T3
**Requirement**: DATA-01, DATA-09

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] Chama `.venv/bin/python -c "import wfdb; wfdb.dl_database(...)"` para `data/ctu-uhb/`
- [ ] Verifica presença de `.hea`/`.dat` antes de `mark_complete`; sem eles → falha sem sentinela
- [ ] Já completo → pula
- [ ] Testes (integration, `python`/`wfdb` dublado no PATH gerando `.hea`/`.dat` fake): sucesso marca `.complete`; download vazio não marca; skip quando já completo
- [ ] Gate: `pytest -q` · Test count: ≥ 3

**Tests**: integration · **Gate**: full
**Commit**: `feat(f0): aquisicao do CTU-UHB com verificacao de completude`

---

### T5: `fetch_icbhi` — Dataverse + fallback SSL

**What**: Baixar ICBHI do Dataverse (`curl -L -C -`); se falhar, tentar a URL original com `--no-check-certificate`; `verify_zip` antes de `unzip`; `.complete` só após verificar (DATA-02, DATA-06, DATA-13).
**Where**: `backend/scripts/download_datasets.sh` (modificar), `backend/tests/integration/test_download_datasets.py` (modificar)
**Depends on**: T4
**Requirement**: DATA-02, DATA-06, DATA-13

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] Primária Dataverse; ao falhar, fallback para `ICBHI_ORIGINAL_URL` com `--no-check-certificate`
- [ ] `verify_zip` roda antes de `unzip`; conteúdo HTML (403) é rejeitado e não vira `.complete`
- [ ] Testes (integration, `curl` dublado): primária entrega zip → ok; primária falha → fallback entrega zip → ok; primária entrega HTML → rejeita e tenta fallback; ambas falham → erro sem `.complete`
- [ ] Gate: `pytest -q` · Test count: ≥ 4

**Tests**: integration · **Gate**: full
**Commit**: `feat(f0): aquisicao do ICBHI com fonte dupla e verificacao`

---

### T6: `fetch_endoscapes`

**What**: Baixar Endoscapes via `wget --continue`, `verify_zip`, `unzip`, `.complete` (DATA-03, DATA-06).
**Where**: `backend/scripts/download_datasets.sh` (modificar), `backend/tests/integration/test_download_datasets.py` (modificar)
**Depends on**: T5
**Requirement**: DATA-03, DATA-06

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `wget --continue` para `data/endoscapes/endoscapes.zip`; `verify_zip`; `unzip`
- [ ] Zip corrompido/parcial → sem `.complete`, elegível a retomada
- [ ] Testes (integration, `wget`/`unzip` dublados): sucesso; zip inválido rejeitado; skip quando completo
- [ ] Gate: `pytest -q` · Test count: ≥ 3

**Tests**: integration · **Gate**: full
**Commit**: `feat(f0): aquisicao do Endoscapes2023`

---

### T7: `main` — orquestração, resumo e `make data`

**What**: `main` roda checagens globais, chama os três `fetch_*` sem que a falha de um derrube os outros, imprime resumo (baixado/pulado/falhou) e define exit code (DATA-10). Confirmar que `make data` chama o script.
**Where**: `backend/scripts/download_datasets.sh` (modificar), `backend/tests/integration/test_download_datasets.py` (modificar)
**Depends on**: T6
**Requirement**: DATA-07, DATA-10

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `main` executa os três fetch em sequência; falha de um não interrompe os demais; exit ≠ 0 se qualquer um falhou
- [ ] Resumo final lista, por dataset, se foi baixado, pulado ou falhou
- [ ] Dois completos + um pendente → só o pendente baixa (idempotência ponta a ponta)
- [ ] `make data` invoca `backend/scripts/download_datasets.sh`
- [ ] Testes (integration, todos os downloaders dublados): cenário misto skip/baixa; um fetch falha → exit≠0 mas os outros rodam e o resumo reflete
- [ ] Gate: `pytest -q` · Test count: ≥ 2

**Tests**: integration · **Gate**: full
**Commit**: `feat(f0): orquestracao main, resumo e make data`

---

## Phase Execution Map

```
Phase 1:  T1 → T2 → T3
Phase 2:  T4 → T5 → T6
Phase 3:  T7
```

7 tarefas, um único batch → execução inline (sem oferta de sub-agentes). Verifier independente ao final.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1 | esqueleto + vars + 1 função | ✅ Granular |
| T2 | 1 função (`verify_zip`) | ✅ Granular |
| T3 | 2 funções coesas (estado) | ✅ Granular |
| T4 | 1 função de aquisição | ✅ Granular |
| T5 | 1 função de aquisição | ✅ Granular |
| T6 | 1 função de aquisição | ✅ Granular |
| T7 | 1 função de orquestração + wiring | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (corpo) | Diagrama | Status |
| --- | --- | --- | --- |
| T1 | None | início Phase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T3 | Phase 2 após Phase 1 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | Phase 3 após Phase 2 | ✅ |

---

## Test Co-location Validation

| Task | Camada | Matriz exige | Tarefa diz | Status |
| --- | --- | --- | --- | --- |
| T1 | Helpers puros | unit | unit | ✅ |
| T2 | Helpers puros | unit | unit | ✅ |
| T3 | Helpers puros | unit | unit | ✅ |
| T4 | Aquisição | integration | integration | ✅ |
| T5 | Aquisição | integration | integration | ✅ |
| T6 | Aquisição | integration | integration | ✅ |
| T7 | Orquestração | integration | integration | ✅ |

Nenhuma violação.

---

## Requirement Traceability

| Requirement | Tarefas | Status |
| --- | --- | --- |
| DATA-01 | T4 | Mapeado |
| DATA-02 | T5 | Mapeado |
| DATA-03 | T6 | Mapeado |
| DATA-05 | T1 | Mapeado |
| DATA-06 | T5, T6 | Mapeado |
| DATA-07 | T3, T7 | Mapeado |
| DATA-08 | T3 | Mapeado |
| DATA-09 | T2, T3, T4 | Mapeado |
| DATA-10 | T7 | Mapeado |
| DATA-11 | T1 | Mapeado |
| DATA-12 | — | **Diferido (P3 opcional)** — verificação de checksum; o Dataverse expõe md5 e pode ser usado numa iteração futura |
| DATA-13 | T2, T5 | Mapeado |

**Coverage:** 12 de 13 requisitos mapeados; DATA-12 diferido explicitamente (P3 opcional, não bloqueia a demo).
