# Monitoramento Hospitalar Multimodal

Sistema que combina quatro fontes de dados de um paciente — **vídeo, áudio, sinais
vitais e prescrições médicas** — para gerar um indicador único de risco e alertar a
equipe automaticamente quando algo preocupante é detectado.

> Tech Challenge — Fase 4 (POSTECH 8IADT). O enunciado completo do desafio está em
> [`docs/8IADT-Fase-4-Tech-challenge.md`](docs/8IADT-Fase-4-Tech-challenge.md); o
> relatório técnico com resultados e decisões de projeto está em
> [`docs/relatorio-tecnico.md`](docs/relatorio-tecnico.md).

---

## O que o sistema faz

| Modalidade | O que analisa | Técnica / modelo |
| --- | --- | --- |
| **Vídeo — movimentação** | Postura, quedas (detecção em 2 estágios com validação temporal), desvios posturais, ângulos articulares, inclinação de tronco, agitação, saída do leito, convulsão | MediaPipe Pose + detector de pessoas (YOLOv8n / YOLO-NAS ONNX) + tracking IoU com gate de distância + validação dinâmica $V_y$ normalizada por altura corporal + restrições temporais (descida sustentada, deslocamento líquido) + escalonamento por FPS |
| **Vídeo — cirurgia** | Estruturas anatômicas críticas em vídeo cirúrgico (keyframes a cada 2s) | YOLOv8 fine-tuned (Endoscapes) com evidência anotada (bboxes) |
| **Áudio** | Sons respiratórios (com anotação ICBHI) ou consultas (transcrição, termos críticos, fadiga vocal) — dispatch automático | Random Forest + faster-whisper + Parselmouth (jitter/shimmer/HNR) |
| **Sinais vitais** | Séries temporais: cardiotocografia fetal (CTU-UHB) e internação adulta com HR/SpO2 (BIDMC) | z-score móvel + Isolation Forest sobre janelas |
| **Prescrições** | Lê receitas em PDF, verifica dose, classificação ANVISA (A1/A2/B1/C1), princípio ativo e variação abrupta; geração avulsa de prescrições sintéticas | Extração de texto (pdfplumber/Textract) + regras clínicas + catálogo ANVISA (Portaria 344/98) + gerador standalone |
| **Fusão e alerta** | Combina as análises num indicador de risco (verde/amarelo/vermelho) com alerta explicável local | Late fusion ponderada com decaimento temporal + histerese |
| **Painel** | Pacientes, envios, linha do tempo de risco, alertas e drill-down de evidência | React + Vite sobre a API |

**Princípio central — evidência sempre reproduzível.** Cada anomalia detectada gera um
artefato (imagem anotada, trecho de áudio, gráfico da janela, PDF marcado) junto de um
descritor `JSON`. O sistema nunca aponta um risco sem mostrar o porquê — e essa
evidência é a única "cola" entre as análises e a camada de fusão.

---

## Arquitetura

O sistema é organizado em camadas, cada uma consumindo apenas a de baixo por um
contrato explícito. As quatro análises são **independentes** entre si (não se importam
umas às outras); o único ponto de contato é o **arquivo de evidência** que cada uma
grava em `output/<análise>/<execução>/`, e que a fusão depois lê.

```mermaid
flowchart TB
    subgraph FE["Apresentação"]
        ST["Painel React<br/>(frontend/)"]
    end

    subgraph API["API (FastAPI — backend/app/)"]
        R["Rotas REST<br/>timeline · analyze · alerts · evidence"]
    end

    subgraph FUSION["Motor de fusão (backend/pipelines/fusion/)"]
        LO["loader"] --> RE["risk_engine<br/>peso · decaimento"]
        RE --> HY["hysteresis<br/>verde/amarelo/vermelho"]
        HY --> AL["alerta explicável<br/>(gerado localmente)"]
    end

    subgraph PIPES["Análises independentes (backend/pipelines/)"]
        V["vídeo<br/>pose + YOLOv8"]
        A["áudio<br/>respiração + fala"]
        VI["vitais<br/>anomalia em série"]
        PR["prescrição<br/>PDF + regras"]
    end

    subgraph EVID["Evidência (contrato comum)"]
        E["output/&lt;análise&gt;/&lt;run&gt;/<br/>artefato + sidecar JSON"]
    end

    subgraph CLOUD["Nuvem — só no modo aws (dois serviços)"]
        TX["Amazon Textract<br/>(texto de PDF)"]
        RK["Amazon Rekognition<br/>(rótulos de imagem)"]
    end

    ST -->|HTTP| R
    R --> FUSION
    V --> E
    A --> E
    VI --> E
    PR --> E
    LO -.lê.-> E
    PR -.modo aws.-> TX
    V -.modo aws.-> RK
```

**Fluxo de dados**: cada arquivo enviado a um paciente é analisado pelo pipeline da sua
modalidade, que grava evidência real em disco; o resultado (achado em linguagem clínica
+ pontuação + evidência) fica no banco local. O motor de fusão carrega os achados do
paciente, calcula um risk score por janela de tempo (soma ponderada com decaimento
exponencial), classifica em verde/amarelo/vermelho com histerese e, ao cruzar o limiar
de disparo, gera um alerta explicável **localmente** (registrado no banco e exibido pela
interface — não há envio por serviço de notificação). A API expõe esse resultado; o
painel só consome a API por HTTP. As análises são 100% locais; só o modo `aws` chama
dois serviços gerenciados (Textract para PDF, Rekognition para imagem), com o resultado
voltando ao processamento local.

### Estrutura de pastas

```
backend/
├── app/          API REST (FastAPI) + banco local de pacientes (SQLite): pacientes,
│                 envios de arquivo, análises, linha do tempo de risco e alertas
├── common/       Compartilhado: contrato de evidência, métricas, config, log
├── pipelines/
│   ├── video/        Postura (MediaPipe) + detecção de objetos (YOLOv8)
│   ├── audio/        Respiração (ICBHI), transcrição, termos críticos, fadiga vocal
│   ├── vitals/       Detecção de anomalia em séries temporais de sinais vitais
│   ├── prescription/ Leitura de PDF + regras de dose
│   └── fusion/       Motor de fusão de risco + alerta explicável (local)
├── aws/          Modo aws: só Textract e Rekognition; adapters intercambiáveis por ENV
├── scripts/      Utilitários (download de datasets, carga de pacientes de demonstração)
└── tests/        Testes automatizados (unitários + integração)

frontend/     Painel web (React + Vite) — consome só a API, sem lógica de processamento própria
training/     Treino do detector YOLOv8 (roda à parte, numa GPU; ver training/README.md)
models/       Pesos treinados prontos para uso (baixados, não versionados)
data/         Datasets públicos + banco local (app.db) e arquivos enviados (uploads/) — não versionados
docs/         Enunciado do desafio e relatório técnico
.specs/       Especificações, decisões de arquitetura (AD-NNN) e relatórios de verificação
```

### Padrões de desenvolvimento adotados

- **Dois modos por adapter, escolhidos por `ENV`.** Cada capacidade que pode ser local
  ou de nuvem (extração de PDF, rótulos de imagem) tem duas implementações atrás de uma
  interface comum: `local` (pdfplumber, YOLOv8) e `aws` (Textract, Rekognition). Trocar
  de modo é trocar uma variável, sem `if` espalhado. No modo `local` não há nenhuma
  chamada de nuvem; nenhum módulo instancia um cliente `boto3` direto (há teste que
  garante isso).
- **Treino desacoplado da inferência.** `training/` é um mundo à parte: nada em
  `backend/` importa `training/` e vice-versa. O sistema em produção **nunca treina** —
  só carrega o peso pronto (`models/best.pt`) e faz inferência. Isso mantém o ambiente
  de produção 100% CPU, sem dependências de GPU.
- **Evidência como contrato único entre camadas.** As análises não se conhecem; a fusão
  não conhece o interior de nenhuma. Todas falam o mesmo formato de evidência
  (`backend/common/evidence.py`), o que permite adicionar/trocar uma análise sem tocar
  nas outras nem na fusão.
- **Config declarativa por análise, campo desconhecido = erro.** Cada pipeline lê sua
  própria config YAML validada estritamente — nada de parâmetro mágico silencioso.
- **Verificação independente (author ≠ verifier).** Cada funcionalidade fechada tem um
  relatório de verificação em `.specs/features/<nome>/validation.md`, produzido por uma
  passada independente que inclui um *sensor de discriminação* (injeta defeitos e
  confirma que os testes os pegam). Ver a seção de resultados no relatório técnico.
- **Commits atômicos e rastreáveis.** Uma tarefa = um commit; cada decisão de
  arquitetura relevante fica registrada como `AD-NNN` em `.specs/STATE.md`.

O sistema roda inteiro num processador comum (CPU) — nenhuma GPU é necessária para o
uso diário. Só o treino do detector de estruturas cirúrgicas (`training/`) se beneficia
de uma GPU, e roda uma única vez, à parte.

---

## Pré-requisitos

- Python 3.12 ou mais recente
- Cerca de 30 GB de espaço livre em disco para os datasets públicos (a maior parte é o
  conjunto de imagens de cirurgia, usado para treinar/avaliar o detector)

Não é preciso Docker nem conta na nuvem: no modo padrão (`local`) tudo roda na máquina.

---

## Início rápido

```bash
# 1. Instalar
python3 -m venv .venv
source .venv/bin/activate
make install

# 2. Baixar os datasets públicos (retomável; não rebaixa o que já existe)
make data

# 3. Baixar o modelo de detecção já treinado (publicado no Hugging Face)
make models-fetch

# 4. Rodar os testes
make test
```

---

## Rodar o painel localmente (API + interface)

São **dois processos**, cada um num terminal:

```bash
# Terminal 1 — a API (fica em http://localhost:8000)
make serve-api

# Terminal 2 — a interface (abre em http://localhost:5173; rode make frontend-install antes na 1a vez)
make serve-front
```

Abra `http://localhost:5173`, cadastre um paciente e envie arquivos para ele — ou rode
`make seed-demo` para já ter 3 pacientes com dados reais (queda + monitoramento fetal,
cirurgia + prescrição, ausculta + internação), sem precisar cadastrar nada na mão. As
portas são ajustáveis: `make serve-api API_PORT=9000` e `make serve-front API_PORT=9000`
sobem o par noutra porta.

**Log de atividade no terminal.** Enquanto a API roda, o terminal mostra, de forma
legível, o que o sistema está fazendo — arquivo recebido, início/fim de cada análise,
cálculo de risco e alertas — com a **origem do processamento marcada**: `[LOCAL]` quando
resolvido na própria máquina, `[AWS]` quando houve chamada a um serviço gerenciado (com
o serviço, a duração e o id da resposta). Exemplo:

```
14:32:07 [paciente:p-0007] arquivo recebido — modalidade=áudio, consulta_01.wav (2.3 MB)
14:32:11 [áudio][LOCAL] classificando ciclos respiratórios (treino sob demanda)
14:32:12 [risco] pontuação 0.31 -> 0.55 — nível AMARELO
14:35:04 [prescrição][AWS] 34 blocos extraídos em 1.8s — requestId=a1b2c3d4
```

---

## Rodar as análises individualmente

Cada análise tem um ponto de entrada próprio que produz evidência real em `output/`:

```bash
# Sinais vitais (cenário de demonstração ponta a ponta)
make demo

# Vídeo — raia de postura/quedas (URFD)
PYTHONPATH=backend .venv/bin/python -m pipelines.video.cli --config <config>

# Áudio — respiração/transcrição/fadiga (ICBHI + áudio de consulta)
PYTHONPATH=backend .venv/bin/python -m pipelines.audio.cli --config <config>
```

### Pipeline de vídeo — configuração do detector de pessoas

A raia de postura/quedas suporta **três backends** de detecção de pessoas,
configuráveis por variável de ambiente ou programaticamente:

| Backend | Variável `POSE_DETECTOR_BACKEND` | O que precisa | Peso |
| --- | --- | --- | --- |
| YOLOv8n | `yolov8n` *(default)* | `ultralytics` (já instalado) | ~6 MB |
| YOLO-NAS S (ONNX) | `yolo_nas_s` | `onnxruntime` (já instalado); modelo descarregado automaticamente | ~47 MB |
| YOLO-NAS M (ONNX) | `yolo_nas_m` | mesmo que acima | ~80 MB |
| YOLO-NAS (SuperGradients) | `yolo_nas_s` ou `yolo_nas_m` | `pip install super-gradients` (requer GPU ou ambiente com cmake) | gerido pelo pacote |

O modelo ONNX do YOLO-NAS é descarregado automaticamente na primeira utilização
e cached em `models/yolo_nas_s.onnx` (não versionado). Se o download automático
falhar, basta colocar o ficheiro `.onnx` manualmente nesse diretório.

**Exemplos:**

```bash
# Usar YOLO-NAS S via ONNX (recomendado — não precisa de GPU)
POSE_DETECTOR_BACKEND=yolo_nas_s \
  PYTHONPATH=backend .venv/bin/python -m pipelines.video.cli \
  --config backend/pipelines/video/configs/demo.yaml

# Usar YOLOv8n (default — não precisa de configurar nada)
PYTHONPATH=backend .venv/bin/python -m pipelines.video.cli \
  --config backend/pipelines/video/configs/demo.yaml
```

**No código Python:**

```python
from pipelines.video.pose import set_detector_backend

set_detector_backend("yolo_nas_s")   # ativa YOLO-NAS
set_detector_backend("yolov8n")      # volta ao default
```

### Rastreamento de identidade em cenas multi-pessoa

Quando há mais de uma pessoa na cena (ex.: paciente + profissionais de saúde),
o sistema mantém um **tracking persistente de identidade** via matching IoU entre
frames consecutivos:

- Cada esqueleto recebe um `track_id` estável ao longo da sequência.
- Ao detetar uma queda, o sistema regista o `track_id` da pessoa que caiu.
- A imagem de evidência (`save_fall_evidence`) usa **estritamente** o esqueleto
  da pessoa com o `track_id` que disparou o evento — eliminando a possibilidade
  de desenhar a pessoa errada quando a ordem da lista de poses muda entre frames.
- O rastreador é reiniciado automaticamente entre sequências distintas.

Não requer configuração adicional — o tracking está sempre ativo.

### Algoritmo de deteção de quedas

O detector de quedas opera em dois estágios com múltiplas vias de deteção e restrições temporais:

**Estágio 1 — Amplitude do centro de massa**: calcula a amplitude máxima do centro de massa (ponto médio dos quadris) em janelas deslizantes de 30 frames com 50% de overlap. Se alguma janela exceder o limiar (0.25, em coordenadas normalizadas), avança para o Estágio 2.

**Estágio 2 — Validação dinâmica**: confirma a queda verificando três condições simultâneas:
- **Velocidade vertical ($V_y$)**: pico de $V_y$ sustentado por ≥2 frames consecutivos (filtra glitches de deteção)
- **Deslocamento total**: soma dos $V_y$ positivos (descida acumulada)
- **Inclinação do tronco**: ângulo da espinha ≥ 25° (single) / 35° (multi-pessoa)

**Via complementar Vy-primary**: para quedas lentas onde a amplitude não atinge o limiar, uma via alternativa dispara se $V_y$ ≥ 0.04, deslocamento total ≥ 0.30, deslocamento líquido em Y ≥ 0.15, e a pessoa termina recumbent — sempre exigindo ≥2 frames consecutivos de descida.

**Normalização e robustez**:
- **$V_y$ e deslocamento normalizados pela altura do tronco** (`torso_height`): os limiares são independentes da distância da câmara e do tamanho da pessoa
- **Escalonamento por FPS**: os limiares são calibrados a 30 fps; vídeos a 120 fps têm $V_y$ compensado automaticamente (multiplicado por 4×)
- **Resiliência a gaps de deteção**: mantém a última posição conhecida por até 5 frames durante falhas de deteção (comum em vídeos de baixa qualidade)
- **Cap físico**: $V_y$ limitado a 0.5 alturas-de-tronco por frame — valores acima são glitches de deteção
- **Gate `was_initially_recumbent`**: pessoas já deitadas no início do vídeo são excluídas (janela inicial de 30 frames, alargada para 90 se necessário)

**Resultados validados**:
- **URFD** (10 sequências): 80% recall (4/5 quedas detectadas), 100% precisão (5/5 ADL sem falsos positivos). A sequência `fall-05` (queda lenta com amplitude 0.19) está abaixo do limiar de 0.25 — documentado como limitação conhecida.
- **Vídeos reais** de vigilância (120 fps, 720p): quedas detectadas, paciente acamado sem falsos positivos

Detalhes de cada análise em [`backend/README.md`](backend/README.md).

---

## Usar o modelo de detecção já treinado

O detector de estruturas cirúrgicas (YOLOv8) é treinado à parte e publicado no
[Hugging Face Hub](https://huggingface.co/AnaPRodrigues/endoscapes-surgical-detector).
Para baixá-lo:

```bash
make models-fetch
```

Para treinar o seu próprio do zero (numa GPU gratuita do Google Colab, comparando
YOLOv8n vs. YOLOv8s e publicando o melhor), veja
[`training/README.md`](training/README.md) e [`models/README.md`](models/README.md).

---

## Comandos principais (Makefile)

| Comando | O que faz |
| --- | --- |
| `make install` | Instala o projeto e as dependências de desenvolvimento |
| `make data` | Baixa os datasets públicos (retomável, idempotente) |
| `make models-fetch` | Baixa o detector YOLOv8 já treinado do Hugging Face |
| `make serve-api` | Sobe a API (FastAPI) em `http://localhost:8000` |
| `make serve-front` | Sobe o painel (React/Vite) em `http://localhost:5173` |
| `make seed-demo` | Cria 3 pacientes de demonstração com dados reais (idempotente) |
| `make gen-presc` | Gera uma prescrição avulsa em PDF (ex.: `make gen-presc ARGS="--drug paracetamol --dose 500"`) |
| `make demo` | Roda a análise de sinais vitais ponta a ponta |
| `make bidmc-scan` | Lista registros de internação (BIDMC) com evento clínico |
| `make test` / `make test-unit` | Roda a suíte completa / só os testes rápidos |
| `make lint` / `make fmt` | Checagem / formatação de estilo |
| `make clean` | Limpa `output/`, caches e `__pycache__` |

---

## Dois modos de operação (`ENV`)

O sistema tem dois modos, escolhidos pela variável de ambiente `ENV`:

- **`local` (padrão)** — todo o processamento roda na máquina, **sem nenhuma chamada de
  nuvem**: extração de PDF por pdfplumber, rótulos de imagem pelo modelo YOLOv8 local.
  Não precisa de credencial, rede nem Docker. É o modo usado para desenvolver, testar e
  rodar a demonstração completa.
- **`aws`** — usa **exatamente dois serviços gerenciados**, chamados de forma síncrona
  com o arquivo embutido na requisição (sem bucket intermediário): **Amazon Textract**
  (`analyze_document`) para extrair texto/campos de prescrições e **Amazon Rekognition**
  (`detect_labels`) para rótulos de objetos em quadros de vídeo. O resultado volta para
  o processamento local. Nenhum outro serviço de nuvem é usado.

Trocar de modo é trocar a variável `ENV` — o resto do código é idêntico.

> **Nota sobre a nuvem.** O enunciado sugere Azure Cognitive Services; este projeto usa
> **AWS** (Textract/Rekognition) como equivalente gerenciado. A justificativa e o
> mapeamento serviço-a-serviço estão no relatório técnico
> ([`docs/relatorio-tecnico.md`](docs/relatorio-tecnico.md)).

---

## Sobre os dados usados

Todas as análises usam datasets **públicos, reais e anonimizados** (nunca dados
sintéticos ou fabricados, exceto onde documentado explicitamente) — ver
[`data/README.md`](data/README.md) para a origem exata de cada um. Nenhum contém
informação identificável de paciente.

---

## Testes e qualidade

```bash
make test         # suíte completa (unitários + integração; sem Docker nem nuvem)
make test-unit    # só os rápidos
make lint         # checagem de estilo (ruff)
```

Cada funcionalidade fechada tem um relatório de verificação independente em
`.specs/features/<nome>/validation.md` (cobertura por critério de aceite + sensor de
mutação). O estado atual e as decisões de arquitetura ficam em `.specs/STATE.md`.
