# F0 — Data Acquisition Specification

## Problem Statement

Todas as features de dados reais (F1 vídeo, F2 áudio, F3 sinais vitais) dependem de datasets
públicos grandes que não entram no Git. Para que o avaliador e o próprio grupo reproduzam o
projeto com um comando — critério de aceite global — a aquisição precisa ser um script idempotente
e versionado, nunca um download manual. F0 é a primeira fatia do plano de 7 dias porque destrava
todas as demais e os downloads (GB) rodam em paralelo enquanto o resto do SDD é montado.

## Goals

- [ ] Baixar as fontes abertas sem barreira por um único comando (`make data`): CTU-UHB, ICBHI 2017, Endoscapes2023, **URFD** (pose/movimento, AD-039) e **BIDMC** (vitais UTI, AD-040).
- [ ] Ser idempotente: re-executar não rebaixa o que já existe.
- [ ] Retomar downloads interrompidos em vez de recomeçar do zero.
- [ ] Manter `data/` fora do Git, versionando apenas o script e `data/README.md`.
- [ ] Falhar de forma clara e acionável quando falta espaço, rede ou uma dependência.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Datasets com credenciamento (MIMIC-III/IV e derivados) | AD-017: CITI+DUA fora do caminho crítico do prazo |
| Cholec80 original e Cholec80-CVS como fonte de vídeo | AD-033: vídeos do Cholec80 exigem CAMMA; o Cholec80-CVS aberto é só anotações. Substituídos pelo Endoscapes2023 |
| Pré-processamento / conversão dos dados | F0 só adquire; parsing e features pertencem a F1/F2/F3 |
| Versionar os datasets no Git | AD-031: datasets são grandes; `data/` é gitignored |
| Verificação de integridade por checksum oficial | Depende de o dataset publicar hashes; tratado como melhoria opcional (P3), não bloqueante |
| Subsetting do Endoscapes no download | O zip (~6 GB) é baixado inteiro; a seleção de frames/vídeos relevantes é feita por F1, não por F0 |

---

## Assumptions & Open Questions

| Assumption / decisão | Default escolhido | Rationale | Confirmado? |
| --- | --- | --- | --- |
| Método CTU-UHB | `wfdb.dl_database('ctu-uhb-ctgdb', 'data/ctu-uhb')` | `wfdb` já é dependência de F3; API oficial do PhysioNet | y |
| Fonte do ICBHI 2017 | **Primária**: Harvard Dataverse, DOI `10.7910/DVN/HT6PKI` → `https://dataverse.harvard.edu/api/access/datafile/7127117` (zip único, ~1.9 GB, HTTP 206/resume) → `data/icbhi/`. **Alternativa**: a URL original `bhichallenge.med.auth.gr` (variável no topo), que exige `--no-check-certificate` por ter cert SSL autoassinado — do ambiente atual o site retorna HTTP 403, mas a alternativa fica pronta para redes onde ele responde | Dataverse é aberto/citável e funciona daqui; a alternativa cobre quem quiser a fonte original. Mesmo `ICBHI_final_database.zip` nas duas | y |
| Trade-off de segurança do `--no-check-certificate` | Só aplicado à fonte alternativa do ICBHI; obrigatório verificar o zip baixado (assinatura PK + tamanho, e checksum se disponível) antes de escrever `.complete` | Baixar por TLS não verificado exige confirmar que o conteúdo é o zip esperado, não um interceptador/página de erro — ver DATA-12, DATA-13 | y |
| Âncora de vídeo/frames (raia objeto de F1) | **Endoscapes2023** via `wget --continue` de `https://s3.unistra.fr/camma_public/datasets/endoscapes/endoscapes.zip` (~6 GB) → `data/endoscapes/`, seguido de `unzip`. Substitui o Cholec80-CVS (AD-033) | Cholec80-CVS aberto é só anotações (24 KB xlsx); vídeos exigem CAMMA. Endoscapes é aberto, por URL direta, com frames+bbox COCO reais | y |
| Fonte de pose/movimento (raia pose de F1, AD-039) | **URFD** — `~70` zips por sequência em `https://fenix.ur.edu.pl/~mkepski/ds/data/{fall,adl}-NN-cam0-rgb.zip` (fall 01–30, adl 01–40), `wget --continue` + `unzip` para `data/urfd/`. Verificado: HTTP 206, `application/zip`, magic `PK`. No mínimo câmera 0 RGB | Único dataset aberto de vídeo de corpo inteiro com rótulo real (fall/ADL); habilita MediaPipe (Req.1 postura + Req.3 movimentação) | y |
| Fonte de vitais UTI (segundo caso de F3, AD-040) | **BIDMC** via `wfdb.dl_database('bidmc', 'data/bidmc')`. Verificado: página PhysioNet HTTP 200 | Aberto (subconjunto liberado do MIMIC-II, sem credenciamento); traz HR e SpO2 reais de internação | y |
| Endoscapes na lista da emenda | **Confirmado pelo usuário: manter.** F0 baixa 5 fontes no total (CTU-UHB, ICBHI, Endoscapes, URFD, BIDMC) | F1 (raia objeto) depende do Endoscapes | y |
| Subconjunto do Endoscapes para a demo | Usar Endoscapes-BBox201 (1933 frames com bbox COCO) como base do YOLOv8; frames de CVS201 conforme F1 precisar | Bbox201 é o que dá rótulo de detecção real; definição fina fica com F1 | y |
| Linguagem do script | Shell (`download_datasets.sh`) chamando Python só onde precisa (`wfdb`) | Idempotência, `wget --continue` e `unzip` são naturais em shell; a AD-031 admite `.sh` ou `.py` | y |
| Limiar de espaço em disco | Estimar o total das três fontes e abortar se o livre for menor que esse total + margem | Evita download parcial que corrompe a idempotência ("existe mas incompleto") | y |
| Marcador de conclusão por dataset | Um arquivo-sentinela (ex.: `data/<ds>/.complete`) escrito só ao fim de cada download bem-sucedido | Distinguir "baixado por completo" de "baixado pela metade" — presença do diretório não basta | y |
| `wget`, `unzip`, `python`/`wfdb` disponíveis | Assumidos presentes; script verifica e falha com instrução se faltar. (`git`/`git-lfs` não são mais necessários após AD-033) | Ambiente é notebook Linux; dependências comuns, mas a ausência precisa de mensagem clara | y |

**Open questions:** none — as três fontes estão confirmadas e testadas: CTU-UHB (`wfdb`), ICBHI (Harvard Dataverse, após a URL original 403), Endoscapes2023 (URL direta aberta). A fonte alternativa do ICBHI com bypass de SSL é decisão confirmada do usuário.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | URLs/paths como variáveis validadas no topo; espaço em disco checado antes de baixar — ver DATA-05, DATA-08 |
| Failure / partial-failure states | Download interrompido é retomado, não recomeçado; sentinela `.complete` distingue parcial de completo — ver DATA-06, DATA-09 |
| Idempotency / retry / duplicate handling | Núcleo da feature: "já existe (completo)? pula" por dataset — ver DATA-07 |
| Auth boundaries & rate limits | N/A because só fontes públicas abertas, sem autenticação (AD-016) |
| Concurrency / ordering | Datasets são independentes; ordem não importa. Duas execuções simultâneas do script ficam fora de escopo (uso é sequencial) |
| Data lifecycle / expiry | `data/` é efêmero e recriável; sem retenção/TTL — é o próprio ponto de não versionar |
| Observability | Cada dataset loga início, método, destino e sucesso/erro; resumo final do que foi baixado/pulado — ver DATA-10 |
| External-dependency failure | Rede, ferramenta ausente (`wget`/`unzip`/`wfdb`) ou URL inválida param aquele dataset com erro claro, sem deixar `.complete` — ver DATA-09, DATA-11 |
| State-transition integrity | Transição "ausente → parcial → completo" governada pela sentinela; nunca marca completo sem o download terminar — ver DATA-09 |

---

## User Stories

### P1: Aquisição reprodutível das três fontes ⭐ MVP

**User Story**: Como avaliador ou integrante do grupo, quero baixar CTU-UHB, ICBHI 2017 e
Endoscapes2023 com um único comando idempotente, para reproduzir o ambiente de dados sem passos
manuais.

**Why P1**: Destrava F1, F2 e F3; é o critério de aceite global de reprodutibilidade aplicado aos dados.

**Acceptance Criteria**:

1. WHEN `make data` (ou `backend/scripts/download_datasets.sh`) é executado THEN o sistema SHALL baixar CTU-UHB para `data/ctu-uhb/` via `wfdb.dl_database`.
2. WHEN o script roda THEN o sistema SHALL baixar o ICBHI 2017 para `data/icbhi/` do Harvard Dataverse (DOI `10.7910/DVN/HT6PKI`) com retomada (`curl -C -` / `wget --continue`), seguido de `unzip`.
3. WHEN o script roda THEN o sistema SHALL baixar o Endoscapes2023 para `data/endoscapes/` via `wget --continue` da URL definida como variável no topo, seguido de `unzip`.
4. WHEN um dataset já foi baixado por completo (sentinela `.complete` presente) THEN o sistema SHALL pular esse dataset e registrar que foi pulado.
5. WHEN todas as URLs/paths são referenciados THEN o sistema SHALL defini-los como variáveis no topo do script, não espalhados no corpo.
6. WHEN o download de um dataset termina com sucesso THEN o sistema SHALL escrever a sentinela de conclusão daquele dataset e SHALL NOT escrevê-la em caso de falha.

**Independent Test**: Rodar `make data` em `data/` vazio e verificar que os três diretórios são populados e ganham `.complete`; rodar de novo e verificar que os três são pulados sem rebaixar nada.

---

### P2: Robustez a falhas de download

**User Story**: Como usuário em rede instável ou disco apertado, quero que o script retome
downloads interrompidos e me avise cedo sobre falta de espaço ou de ferramentas, para não perder
tempo com um download parcial silencioso.

**Why P2**: Datasets de GB em rede acadêmica falham no meio; sem retomada e sem checagem de espaço,
a idempotência quebra ("existe mas incompleto").

**Acceptance Criteria**:

1. WHEN um download do ICBHI é interrompido e o script roda de novo THEN o sistema SHALL retomar de onde parou (`wget --continue`), não recomeçar.
2. WHEN o espaço livre em disco é menor que o total estimado das fontes a baixar mais uma margem THEN o sistema SHALL abortar antes de baixar, com mensagem indicando o espaço necessário e o disponível.
3. WHEN uma ferramenta necessária (`wget`, `unzip`, `python`/`wfdb`) está ausente THEN o sistema SHALL falhar com mensagem que nomeia a ferramenta e como instalá-la, sem deixar sentinela `.complete`.
4. WHEN o download de um dataset falha (rede, URL inválida, unzip corrompido) THEN o sistema SHALL registrar o erro daquele dataset e continuar tentando os demais, retornando código de saída não-zero ao final.

**Independent Test**: Simular ferramenta ausente (PATH restrito) e confirmar mensagem acionável sem `.complete`; interromper o ICBHI no meio e confirmar retomada na segunda execução.

---

### P3: Verificação de integridade (opcional)

**User Story**: Como grupo preocupado com dados corrompidos, quero verificar a integridade do que
foi baixado quando o dataset publica hashes, para confiar que o `.complete` reflete um download íntegro.

**Why P3**: Aumenta a confiança, mas os datasets nem sempre publicam checksums; não bloqueia a demo.

**Acceptance Criteria**:

1. WHEN um dataset publica um checksum de referência THEN o sistema SHALL comparar o arquivo baixado ao checksum antes de escrever a sentinela.
2. WHEN o checksum não confere THEN o sistema SHALL descartar o download daquele dataset e não escrever a sentinela.

---

## Edge Cases

- WHEN `data/` já contém um diretório de dataset SEM a sentinela `.complete` (download anterior parcial) THEN o sistema SHALL retomar/refazer aquele dataset, nunca tratá-lo como pronto.
- WHEN o zip do ICBHI baixa mas está corrompido (unzip falha) THEN o sistema SHALL reportar erro e não escrever a sentinela, deixando o dataset elegível para nova tentativa.
- WHEN o zip do Endoscapes baixa parcialmente e o `unzip` falha THEN o sistema SHALL reportar erro e não escrever a sentinela, deixando o dataset elegível para retomada via `wget --continue`.
- WHEN o script roda sem rede THEN o sistema SHALL falhar cedo com mensagem clara, sem sentinelas.
- WHEN uma fonte responde com página HTML de erro (ex.: 403) em vez do arquivo — mesmo com HTTP 200 e exit 0 — THEN o sistema SHALL detectar pela assinatura/Content-Type (não é zip PK), NÃO escrever `.complete`, e cair para a fonte alternativa quando houver (caso do ICBHI).
- WHEN a fonte alternativa do ICBHI é usada (`--no-check-certificate`) THEN o sistema SHALL verificar o zip baixado antes de aceitá-lo, para não confiar cegamente numa conexão TLS não verificada.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| DATA-01 | P1: Download CTU-UHB (wfdb) | T4 | Verified |
| DATA-02 | P1: Download ICBHI (Dataverse + unzip) | T5 | Verified |
| DATA-03 | P1: Download Endoscapes2023 (wget --continue + unzip) | T6 | Verified |
| DATA-05 | P1: URLs/paths como variáveis no topo | T1 | Verified |
| DATA-06 | P2: Retomada de download interrompido | T5, T6 | Verified (flags `-C -`/`--continue` corretos; retomada **não testada comportamentalmente** — dívida P2 aceita, L-021) |
| DATA-07 | P1: Idempotência por dataset (pula se completo) | T3, T7 | Verified (também confirmado com `make data` real) |
| DATA-08 | P2: Checagem de espaço em disco antes de baixar | T3 | Verified |
| DATA-09 | P1/P2: Sentinela `.complete` só em sucesso; parcial ≠ completo | T2, T3, T4 | Verified |
| DATA-10 | P1: Log por dataset + resumo final (baixado/pulado/falhou) | T7 | Verified |
| DATA-11 | P2: Ferramenta ausente falha com mensagem acionável | T1 | Verified |
| DATA-12 | P3: Verificação de checksum quando disponível | Design | Pending |
| DATA-13 | P1/P2: Fonte primária + alternativa do ICBHI; validar zip real (assinatura PK); `--no-check-certificate` só na alternativa | T2, T5 | Verified |
| DATA-14 | Emenda: download idempotente do URFD (~70 zips de sequência, câmera 0 RGB) → `data/urfd/`, com `verify_zip` e `.complete` (AD-039) | T8 (a criar) | Pending |
| DATA-15 | Emenda: download idempotente do BIDMC via `wfdb.dl_database` → `data/bidmc/`, com verificação de completude (AD-040) | T9 (a criar) | Pending |

**ID format:** `DATA-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** DATA-01..11,13 Verified (Verifier F0 PASS: 32 testes; DATA-12/checksum diferido P3). **DATA-14 (URFD) e DATA-15 (BIDMC) pendentes** — a emenda (AD-039/040) **REABRE a F0** para dois novos fetchers (T8 `fetch_urfd`, T9 `fetch_bidmc`), que precisam de Design/Tasks/Execute + nova verificação. O núcleo fechado permanece; só se acrescenta.

---

## Success Criteria

- [ ] `make data` popula `data/ctu-uhb/`, `data/icbhi/` e `data/endoscapes/` a partir do zero, sem passo manual.
- [ ] Re-executar `make data` pula os três datasets já completos sem rebaixar.
- [ ] `data/` permanece fora do Git; só `data/README.md` e o script são versionados.
- [ ] Falta de espaço, de ferramenta ou de rede produz mensagem acionável, sem deixar dataset parcial marcado como completo.
