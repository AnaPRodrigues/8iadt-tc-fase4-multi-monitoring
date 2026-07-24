# backend/

Código em Python — API, pipelines de análise, motor de fusão de risco e integração com
serviços de nuvem. É a única parte do sistema que processa dados; o `frontend/` apenas
consome a API e não tem lógica própria.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `app/` | API (FastAPI) e o **banco local de pacientes** (SQLite): `db.py`/`repositorio.py` (pacientes, envios, análises, alertas), `armazenamento.py` (arquivos enviados), `analise.py` (dispara a análise da modalidade reusando os pipelines), `servico.py` (monta a linha do tempo de risco e registra alertas), `routes.py` (endpoints). Endpoints: pacientes (CRUD), envio de arquivo, disparo/consulta de análise, timeline consolidada, alertas, evidência por id |
| `common/` | Código compartilhado por todas as análises: formato de evidência (como cada anomalia detectada é registrada com seu artefato visual), métricas, configuração, log |
| `pipelines/vitals/` | Análise de sinais vitais em séries temporais: cardiotocografia (frequência cardíaca fetal, CTU-UHB) e internação adulta (frequência cardíaca e oxigenação/SpO2, BIDMC — `bidmc.py`), com detecção de anomalias |
| `pipelines/audio/` | Análise de áudio: dificuldade respiratória, transcrição, termos clínicos críticos, sinais de fadiga vocal |
| `pipelines/video/` | Análise de vídeo: postura e padrões de movimentação (quedas), detecção de estruturas críticas em cirurgia |
| `pipelines/prescription/` | Leitura de prescrições médicas (PDF) e checagem de dose/variação anômala |
| `fusion/` | Combinação dos sinais das quatro análises acima num único indicador de risco, com alerta automático |
| `aws/` | Modo `aws`: chama só dois serviços gerenciados — Amazon Textract (texto de documentos) e Amazon Rekognition (rótulos de imagem). No modo `local` (padrão) nada aqui é usado. A seleção local/aws é feita por adaptadores intercambiáveis, escolhidos pela variável `ENV` |
| `scripts/` | Utilitários, incluindo o download dos conjuntos de dados públicos |
| `tests/` | Testes automatizados de tudo acima |

## Como rodar os testes

```bash
make test         # suíte completa
make test-unit    # só os testes rápidos (sem tocar em serviços externos)
make lint         # checagem de estilo
```
