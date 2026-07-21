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

# URFD (AD-039): ~70 zips por sequência, um por fall-NN/adl-NN. Contagens da AD-039.
URFD_BASE_URL="${URFD_BASE_URL:-https://fenix.ur.edu.pl/~mkepski/ds/data}"
URFD_N_FALL="${URFD_N_FALL:-30}"
URFD_N_ADL="${URFD_N_ADL:-40}"

# BIDMC (AD-040): mesmo padrão de aquisição do CTU-UHB via wfdb.
BIDMC_DB="${BIDMC_DB:-bidmc}"

# Estimativas de tamanho (bytes) para a checagem de espaço.
CTU_EST_BYTES="${CTU_EST_BYTES:-600000000}"          # ~0.6 GB
ICBHI_EST_BYTES="${ICBHI_EST_BYTES:-2100000000}"     # ~2.0 GB
ENDOSCAPES_EST_BYTES="${ENDOSCAPES_EST_BYTES:-6500000000}"  # ~6.3 GB
URFD_EST_BYTES="${URFD_EST_BYTES:-3000000000}"       # ~3 GB (estimativa; tamanho não documentado)
BIDMC_EST_BYTES="${BIDMC_EST_BYTES:-300000000}"       # ~0.3 GB
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

# _curl_zip url out [opts...] — baixa com retomada e só retorna 0 se for zip real.
# Remove o arquivo em falha para não contaminar uma retomada seguinte (o HTML de
# uma fonte não pode virar prefixo do download da próxima).
_curl_zip() {
    local url="$1" out="$2"
    shift 2
    if ! curl -sS -L -C - "$@" -o "$out" "$url"; then
        err "download falhou: $url"
        rm -f "$out"
        return 1
    fi
    if ! verify_zip "$out"; then
        rm -f "$out"
        return 1
    fi
    return 0
}

# fetch_icbhi — Dataverse (primária) com fallback para a URL original via
# --no-check-certificate (cert autoassinado) (DATA-02, DATA-06, DATA-13).
fetch_icbhi() {
    local dest="$DATA_DIR/icbhi" zip
    if is_complete "$dest"; then
        log "ICBHI: já completo — pulando"
        FETCH_STATUS="pulado"
        return 0
    fi
    mkdir -p "$dest"
    zip="$dest/ICBHI_final_database.zip"

    if _curl_zip "$ICBHI_DATAVERSE_URL" "$zip"; then
        log "ICBHI: obtido do Harvard Dataverse"
    elif _curl_zip "$ICBHI_ORIGINAL_URL" "$zip" --no-check-certificate; then
        log "ICBHI: obtido da fonte original (TLS não verificado — conteúdo verificado)"
    else
        err "ICBHI: ambas as fontes falharam"
        FETCH_STATUS="falhou"
        return 1
    fi

    if ! unzip -o -q "$zip" -d "$dest"; then
        err "ICBHI: unzip falhou"
        FETCH_STATUS="falhou"
        return 1
    fi
    mark_complete "$dest"
    log "ICBHI: OK"
    FETCH_STATUS="baixado"
    return 0
}

# fetch_endoscapes — Endoscapes2023 via wget --continue (DATA-03, DATA-06).
fetch_endoscapes() {
    local dest="$DATA_DIR/endoscapes" zip
    if is_complete "$dest"; then
        log "Endoscapes: já completo — pulando"
        FETCH_STATUS="pulado"
        return 0
    fi
    mkdir -p "$dest"
    zip="$dest/endoscapes.zip"
    log "Endoscapes: baixando (~6 GB) com retomada"
    if ! wget --continue -q -O "$zip" "$ENDOSCAPES_URL"; then
        err "Endoscapes: download falhou"
        rm -f "$zip"
        FETCH_STATUS="falhou"
        return 1
    fi
    if ! verify_zip "$zip"; then
        rm -f "$zip"
        FETCH_STATUS="falhou"
        return 1
    fi
    if ! unzip -o -q "$zip" -d "$dest"; then
        err "Endoscapes: unzip falhou"
        FETCH_STATUS="falhou"
        return 1
    fi
    mark_complete "$dest"
    log "Endoscapes: OK"
    FETCH_STATUS="baixado"
    return 0
}

# _fetch_urfd_seq — baixa uma sequência do URFD; sentinela PRÓPRIA da sequência
# (não confundir com a sentinela de dataset de fetch_urfd).
_fetch_urfd_seq() {
    local seq="$1" dest zip
    dest="$DATA_DIR/urfd/$seq"
    if is_complete "$dest"; then
        return 0
    fi
    mkdir -p "$dest"
    zip="$dest/$seq-cam0-rgb.zip"
    if ! wget --continue -q -O "$zip" "$URFD_BASE_URL/$seq-cam0-rgb.zip"; then
        err "URFD $seq: download falhou"
        rm -f "$zip"
        return 1
    fi
    if ! verify_zip "$zip"; then
        rm -f "$zip"
        return 1
    fi
    if ! unzip -o -q "$zip" -d "$dest"; then
        err "URFD $seq: unzip falhou"
        return 1
    fi
    mark_complete "$dest"
    return 0
}

# fetch_urfd — 70 sequências (fall+adl) do URFD (DATA-14). Idempotência em DOIS
# níveis: por sequência (evita rebaixar 69 zips já prontos por causa de 1) e por
# dataset (só marca completo quando TODAS as sequências completam).
fetch_urfd() {
    local dataset_dest="$DATA_DIR/urfd"
    if is_complete "$dataset_dest"; then
        log "URFD: já completo — pulando"
        FETCH_STATUS="pulado"
        return 0
    fi
    mkdir -p "$dataset_dest"

    # Padding fixo em 2 dígitos: é a convenção real de nomes do dataset (fall-01,
    # adl-01, ...), independente de N — `seq -w` erraria isso para N<10 (ex.: testes).
    local rc=0 n i
    for n in $(seq 1 "$URFD_N_FALL"); do
        printf -v i '%02d' "$n"
        _fetch_urfd_seq "fall-$i" || rc=1
    done
    for n in $(seq 1 "$URFD_N_ADL"); do
        printf -v i '%02d' "$n"
        _fetch_urfd_seq "adl-$i" || rc=1
    done

    if [ "$rc" -ne 0 ]; then
        err "URFD: uma ou mais sequências falharam — dataset não marcado completo"
        FETCH_STATUS="falhou"
        return 1
    fi
    mark_complete "$dataset_dest"
    log "URFD: OK (todas as sequências completas)"
    FETCH_STATUS="baixado"
    return 0
}

# fetch_bidmc — BIDMC via wfdb (DATA-15).
#
# Achado verificado (não presumir de novo): os arquivos de "numerics" (HR,
# PULSE, RESP, SpO2 a 1 Hz — o sinal que AD-040 realmente quer) são
# REGISTROS SEPARADOS com sufixo 'n' (ex. bidmc01n) que NÃO aparecem no
# RECORDS do dataset. `dl_database(records='all')` baixa só as 53 formas de
# onda (125 Hz); os numerics exigem uma segunda chamada explícita com os
# nomes derivados de get_record_list(...) + 'n' (nunca hardcoded).
fetch_bidmc() {
    local dest="$DATA_DIR/bidmc"
    if is_complete "$dest"; then
        log "BIDMC: já completo — pulando"
        FETCH_STATUS="pulado"
        return 0
    fi
    mkdir -p "$dest"
    log "BIDMC: baixando via wfdb.dl_database (formas de onda + numerics)"
    if ! BIDMC_DEST="$dest" "$PY" -c "
import wfdb
records = wfdb.get_record_list('$BIDMC_DB')
wfdb.dl_database('$BIDMC_DB', '$dest', records=records)
numerics = [r + 'n' for r in records]
wfdb.dl_database('$BIDMC_DB', '$dest', records=numerics)
"; then
        err "BIDMC: falha no wfdb.dl_database"
        FETCH_STATUS="falhou"
        return 1
    fi
    local n_hea n_numerics
    n_hea=$(find "$dest" -maxdepth 1 -name '*.hea' | wc -l)
    n_numerics=$(find "$dest" -maxdepth 1 -name '*n.hea' | wc -l)
    if [ "$n_hea" -lt 1 ] || [ "$n_numerics" -lt 1 ]; then
        err "BIDMC: download incompleto (hea=$n_hea, numerics=$n_numerics) — não marcando completo"
        FETCH_STATUS="falhou"
        return 1
    fi
    mark_complete "$dest"
    log "BIDMC: OK ($n_hea registros, $n_numerics numerics)"
    FETCH_STATUS="baixado"
    return 0
}

declare -A FETCH_RESULT
FETCH_RC=0

# _run_fetch nome função — executa um fetch sem deixar a falha derrubar os demais.
_run_fetch() {
    local name="$1" fn="$2"
    FETCH_STATUS=""
    if "$fn"; then
        FETCH_RESULT["$name"]="${FETCH_STATUS:-baixado}"
    else
        FETCH_RESULT["$name"]="${FETCH_STATUS:-falhou}"
        FETCH_RC=1
    fi
}

# main — checagens globais, os três fetch, resumo e exit code (DATA-07, DATA-10).
main() {
    require_tools || return 1

    # Espaço: soma das estimativas só dos datasets ainda não completos.
    local need=0
    is_complete "$DATA_DIR/ctu-uhb"    || need=$((need + CTU_EST_BYTES))
    is_complete "$DATA_DIR/icbhi"      || need=$((need + ICBHI_EST_BYTES))
    is_complete "$DATA_DIR/endoscapes" || need=$((need + ENDOSCAPES_EST_BYTES))
    if [ "$need" -gt 0 ]; then
        mkdir -p "$DATA_DIR"
        check_disk_space "$need" || return 1
    fi

    FETCH_RESULT=()
    FETCH_RC=0
    _run_fetch "CTU-UHB" fetch_ctu_uhb
    _run_fetch "ICBHI" fetch_icbhi
    _run_fetch "Endoscapes" fetch_endoscapes

    log "resumo:"
    local k
    for k in "CTU-UHB" "ICBHI" "Endoscapes"; do
        log "  $k: ${FETCH_RESULT[$k]}"
    done
    return "$FETCH_RC"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
