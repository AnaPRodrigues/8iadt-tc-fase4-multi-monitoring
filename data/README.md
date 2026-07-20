# data/

Diretório populado pelo script de aquisição (F0) — **não versionado** (só este
README e o script entram no Git). Datasets grandes ficam fora do repositório.

## Como reproduzir

```
make data
```

Executa `backend/scripts/download_datasets`, que baixa apenas as fontes abertas,
sem credenciamento (AD-016, AD-031):

| Dataset | Destino | Método | Papel |
| --- | --- | --- | --- |
| CTU-UHB Intrapartum CTG | `data/ctu-uhb/` | `wfdb.dl_database('ctu-uhb-ctgdb', ...)` | F3 — FHR + contração + pH do cordão (rótulo real) |
| ICBHI 2017 Respiratory Sound | `data/icbhi/` | `wget --continue` + `unzip` | F2 — ciclos respiratórios anotados (crackle/wheeze/normal) |
| Endoscapes2023 | `data/endoscapes/` | `wget --continue` (~6 GB) + `unzip` | F1 — frames cirúrgicos reais + bounding boxes COCO (5 anatomias + 1 instrumento) |

O script é idempotente: se o dataset já existe, pula. Downloads interrompidos são
retomados (`--continue`).

## Fontes confirmadas

- ICBHI 2017: `https://bhichallenge.med.auth.gr/sites/default/files/ICBHI_final_database/ICBHI_final_database.zip`
- Endoscapes2023: `https://s3.unistra.fr/camma_public/datasets/endoscapes/endoscapes.zip` (~6 GB, aberto, sem formulário). Substitui o Cholec80-CVS, cujos vídeos exigem CAMMA (AD-033).

## Datasets NÃO usados

MIMIC-III/IV e derivados exigem credenciamento (CITI + DUA) e estão fora do
caminho crítico do prazo (AD-017). Nenhum dado real identificável de paciente.
