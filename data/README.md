# data/

Pasta onde ficam os conjuntos de dados públicos usados pelo sistema. **Não é
versionada no Git** — só este README fica no repositório; os dados em si são baixados
sob demanda, pois são grandes demais para viver num repositório de código.

Além dos datasets, esta pasta guarda dois artefatos de execução, também fora do Git:
- `app.db` — o banco local de pacientes (SQLite), criado automaticamente na primeira
  execução da API;
- `uploads/<paciente>/<modalidade>/` — os arquivos enviados de cada paciente.

## Como baixar

```bash
make data
```

Baixa todos os conjuntos de dados abaixo, de fontes públicas e sem necessidade de
cadastro/aprovação prévia. O download é retomável (se cair no meio, `make data` de
novo continua de onde parou) e não baixa de novo o que já existe.

| Dataset | Onde fica | Para que serve |
| --- | --- | --- |
| CTU-UHB (cardiotocografia) | `data/ctu-uhb/` | Frequência cardíaca fetal e contrações uterinas de partos reais, com o desfecho clínico real (pH do cordão umbilical) — usado para detectar sinais de sofrimento fetal |
| ICBHI 2017 (sons respiratórios) | `data/icbhi/` | Gravações reais de ausculta pulmonar, anotadas por especialistas (respiração normal, com estalidos ou com sibilos) — usado para detectar dificuldade respiratória |
| Endoscapes2023 (cirurgia) | `data/endoscapes/` | Imagens reais de cirurgia laparoscópica, com as estruturas anatômicas e instrumentos marcados — usado para treinar e avaliar o detector de estruturas críticas em vídeo |
| UR Fall Detection (postura) | `data/urfd/` | Sequências de imagens reais de pessoas caindo ou realizando atividades do dia a dia — usado para detectar quedas e padrões de movimentação |
| BIDMC (monitor de UTI) | `data/bidmc/` | Sinais reais de monitor de internação (batimentos, oxigenação no sangue, respiração) de pacientes de UTI — usado para detectar alterações nesses sinais vitais |

Nenhum desses conjuntos de dados contém informação identificável de paciente — são
todos anonimizados e de acesso público para pesquisa.

## Fontes exatas

- **CTU-UHB**: PhysioNet, banco `ctu-uhb-ctgdb`, baixado via biblioteca `wfdb`.
- **ICBHI 2017**: espelhado no Harvard Dataverse (`10.7910/DVN/HT6PKI`) — o site
  original da competição está fora do ar.
- **Endoscapes2023**: `s3.unistra.fr/camma_public/datasets/endoscapes` (acesso aberto,
  sem formulário).
- **UR Fall Detection**: `fenix.ur.edu.pl/~mkepski/ds` (Universidade de Rzeszów).
- **BIDMC**: PhysioNet, banco `bidmc`.
