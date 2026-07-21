#!/usr/bin/env bash
# F0 — aquisição idempotente dos datasets abertos do projeto (AD-031, AD-033).
#
# Baixa só fontes abertas sem barreira: CTU-UHB (F3), ICBHI 2017 (F2),
# Endoscapes2023 (F1). Idempotente por sentinela `.complete` por dataset.
# Uso: ./backend/scripts/download_datasets.sh   (ou `make data`)
#
# Sem `set -e`: os fetch tratam falhas explicitamente para que a falha de um
# dataset não derrube os outros.
set -uo pipefail

# ---- Variáveis (DATA-05) — sobrescrevíveis por ambiente (usado nos testes) ----
DATA_DIR="${DATA_DIR:-data}"
PY="${PY:-.venv/bin/python}"
CTU_DB="${CTU_DB:-ctu-uhb-ctgdb}"

# ICBHI: primária no Harvard Dataverse (aberto, responde); alternativa na URL
# original, que exige --no-check-certificate (cert autoassinado) — ver AD/spec.
ICBHI_DATAVERSE_URL="${ICBHI_DATAVERSE_URL:-https://dataverse.harvard.edu/api/access/datafile/7127117}"
ICBHI_ORIGINAL_URL="${ICBHI_ORIGINAL_URL:-https://bhichallenge.med.auth.gr/sites/default/files/ICBHI_final_database/ICBHI_final_database.zip}"
ENDOSCAPES_URL="${ENDOSCAPES_URL:-https://s3.unistra.fr/camma_public/datasets/endoscapes/endoscapes.zip}"

# Estimativas de tamanho (bytes) para a checagem de espaço.
CTU_EST_BYTES="${CTU_EST_BYTES:-600000000}"          # ~0.6 GB
ICBHI_EST_BYTES="${ICBHI_EST_BYTES:-2100000000}"     # ~2.0 GB
ENDOSCAPES_EST_BYTES="${ENDOSCAPES_EST_BYTES:-6500000000}"  # ~6.3 GB
MIN_ZIP_BYTES="${MIN_ZIP_BYTES:-1000}"               # abaixo disso não é um dataset

log() { printf '[data] %s\n' "$*" >&2; }
err() { printf '[data] ERRO: %s\n' "$*" >&2; }

# require_tools — falha nomeando a ferramenta ausente (DATA-11).
require_tools() {
    local missing=0 t
    for t in curl wget unzip; do
        if ! command -v "$t" >/dev/null 2>&1; then
            err "ferramenta ausente: $t (instale pelo gerenciador de pacotes do sistema)"
            missing=1
        fi
    done
    if [ ! -x "$PY" ]; then
        err "python do venv ausente ou não executável: $PY (crie o .venv e instale wfdb)"
        missing=1
    fi
    return "$missing"
}

# verify_zip — aceita só um zip real (DATA-09, DATA-13).
# Rejeita página de erro HTML (o caso do ICBHI 403, que vinha com exit 0) e
# arquivos pequenos demais, checando a assinatura PK\x03\x04 e o tamanho.
verify_zip() {
    local path="$1"
    if [ ! -f "$path" ]; then
        err "arquivo inexistente: $path"
        return 1
    fi
    local size
    size=$(stat -c %s "$path" 2>/dev/null || echo 0)
    if [ "$size" -lt "$MIN_ZIP_BYTES" ]; then
        err "arquivo pequeno demais para ser um dataset ($size bytes): $path"
        return 1
    fi
    local magic
    magic=$(head -c 4 "$path" | od -An -tx1 | tr -d ' \n')
    if [ "$magic" != "504b0304" ]; then
        err "conteúdo não é um zip (assinatura '$magic') — possível página de erro: $path"
        return 1
    fi
    return 0
}

# Idempotência (DATA-07): a sentinela `.complete` é a única coisa que autoriza pular.
is_complete()   { [ -f "$1/.complete" ]; }
mark_complete() { touch "$1/.complete"; }

# check_disk_space (DATA-08): aborta antes de baixar se o livre < necessário.
check_disk_space() {
    local need="$1" avail
    avail=$(df -PB1 "$DATA_DIR" 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -z "$avail" ]; then
        err "não foi possível medir o espaço livre em $DATA_DIR"
        return 1
    fi
    if [ "$avail" -lt "$need" ]; then
        err "espaço insuficiente em $DATA_DIR: precisa de $need bytes, há $avail"
        return 1
    fi
    return 0
}

# fetch_ctu_uhb — CTU-UHB via wfdb (DATA-01). Só marca completo com .hea/.dat presentes.
# CTU_DEST é exportado para o python; o wfdb real usa o argumento do -c, e o stub
# de teste usa o env — o mesmo contrato serve para os dois.
fetch_ctu_uhb() {
    local dest="$DATA_DIR/ctu-uhb"
    if is_complete "$dest"; then
        log "CTU-UHB: já completo — pulando"
        FETCH_STATUS="pulado"
        return 0
    fi
    mkdir -p "$dest"
    log "CTU-UHB: baixando via wfdb.dl_database"
    if ! CTU_DEST="$dest" "$PY" -c "import wfdb; wfdb.dl_database('$CTU_DB', '$dest')"; then
        err "CTU-UHB: falha no wfdb.dl_database"
        FETCH_STATUS="falhou"
        return 1
    fi
    local n_hea n_dat
    n_hea=$(find "$dest" -name '*.hea' | wc -l)
    n_dat=$(find "$dest" -name '*.dat' | wc -l)
    if [ "$n_hea" -lt 1 ] || [ "$n_dat" -lt 1 ]; then
        err "CTU-UHB: download sem .hea/.dat ($n_hea/$n_dat) — não marcando completo"
        FETCH_STATUS="falhou"
        return 1
    fi
    mark_complete "$dest"
    log "CTU-UHB: OK ($n_hea registros)"
    FETCH_STATUS="baixado"
    return 0
}

main() {
    require_tools || return 1
    # fetch_ctu_uhb / fetch_icbhi / fetch_endoscapes e o resumo entram nas próximas tarefas.
    return 0
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
