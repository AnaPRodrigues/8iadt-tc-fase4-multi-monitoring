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
make data        # 5 datasets principais (~25 GB, shell script)
make data-extra  # datasets complementares (~820 MB, Python)
```

O download é retomável (se cair no meio, rode de novo) e não baixa de novo o
que já existe.

| Dataset | Onde fica | Para que serve |
| --- | --- | --- |
| CTU-UHB (cardiotocografia) | `data/ctu-uhb/` | Frequência cardíaca fetal e contrações uterinas de partos reais, com o desfecho clínico real (pH do cordão umbilical) — usado para detectar sinais de sofrimento fetal |
| ICBHI 2017 (sons respiratórios) | `data/icbhi/` | Gravações reais de ausculta pulmonar, anotadas por especialistas (respiração normal, com estalidos ou com sibilos) — usado para detectar dificuldade respiratória |
| Endoscapes2023 (cirurgia) | `data/endoscapes/` | Imagens reais de cirurgia laparoscópica, com as estruturas anatômicas e instrumentos marcados — usado para treinar e avaliar o detector de estruturas críticas em vídeo |
| UR Fall Detection (postura) | `data/urfd/` | Sequências de imagens reais de pessoas caindo ou realizando atividades do dia a dia — usado para detectar quedas e padrões de movimentação |
| BIDMC (monitor de UTI) | `data/bidmc/` | Sinais reais de monitor de internação (batimentos, oxigenação no sangue, respiração) de pacientes de UTI — usado para detectar alterações nesses sinais vitais |

## Datasets complementares (`make data-extra`)

| Dataset | Onde fica | Para que serve |
| --- | --- | --- |
| Common Voice PT-BR (fala em português) | `data/common-voice-ptbr/` | 20 amostras de fala real em português brasileiro — usado para validar a transcrição (faster-whisper) com voz humana real |
| Laryngeal Voice Disorder (voz patológica) | `data/laryngeal/` | Gravações de vozes saudáveis e com patologia (disfonia, nódulos, paralisia) — usado para validar a detecção de fadiga vocal e alterações acústicas |
| UI-PRMD Skeleton (fisioterapia) | `data/ui-prmd/` | Ângulos articulares de exercícios de fisioterapia executados de forma correta e incorreta — usado para validar regras de desvio angular no MediaPipe |
| KIMORE (fisioterapia clínica) | `data/kimore/` | Esqueleto 3D de pacientes reais (AVC, Parkinson) e saudáveis em exercícios de reabilitação — complementa o UI-PRMD com dados clínicos |
| m2cai16-tool-locations (instrumentos cirúrgicos) | `data/m2cai16/` | 2.532 frames de cirurgia com 7 classes de instrumentos anotados — complementa o Endoscapes para detecção de objetos em vídeo |
| SemClinBr (notas clínicas pt-BR) | `data/semclinbr/` | 1.000 notas clínicas reais em português brasileiro com 65.117 entidades anotadas — usado para validar extração de termos críticos e sentimento |

## Áudio de consulta sintético (`make tts-consulta`)

Gera ≥ 2 áudios sintéticos de consulta médica em português brasileiro
(`data/consultas-tts/`) usando o edge-tts (gratuito). Os áudios contêm
vocabulário clínico real ("falta de ar", "tontura", "dor no peito") e tons
diferentes (calmo vs. preocupado) para exercitar o pipeline completo:
transcrição → termos críticos → sentimento → fadiga vocal.

Nenhum desses conjuntos de dados contém informação identificável de paciente — são
todos anonimizados e de acesso público para pesquisa.

## Fontes exatas

### Datasets principais
- **CTU-UHB**: PhysioNet, banco `ctu-uhb-ctgdb`, baixado via biblioteca `wfdb`.
- **ICBHI 2017**: espelhado no Harvard Dataverse (`10.7910/DVN/HT6PKI`) — o site
  original da competição está fora do ar.
- **Endoscapes2023**: `s3.unistra.fr/camma_public/datasets/endoscapes` (acesso aberto,
  sem formulário).
- **UR Fall Detection**: `fenix.ur.edu.pl/~mkepski/ds` (Universidade de Rzeszów).
- **BIDMC**: PhysioNet, banco `bidmc`.

### Datasets complementares
- **Common Voice PT-BR**: Hugging Face (`mozilla-foundation/common_voice_11_0`, split `pt`).
- **Laryngeal Voice Disorder**: Kaggle (`sree14hari/svd-dataset`), subconjunto curado do
  Saarbrücken Voice Database.
- **UI-PRMD Skeleton**: mirror no GitHub (`avakanski/A-Deep-Learning-Framework-for-
  Assessing-Physical-Rehabilitation-Exercises`). O site oficial
  (`webpages.uidaho.edu/ui-prmd`) está fora do ar.
- **KIMORE**: Google Drive do artigo IEEE TNSRE 2019. Wrapper em
  `github.com/petteriTeikari/KiMoRe_wrapper`.
- **m2cai16-tool-locations**: Stanford (`ai.stanford.edu/~syyeung/resources/
  m2cai16-tool-locations.zip`) ou Roboflow Universe (`camma/m2cai16-tool-locations`).
- **SemClinBr**: artigo no Journal of Biomedical Semantics (2022). Acesso sob
  solicitação aos autores.
