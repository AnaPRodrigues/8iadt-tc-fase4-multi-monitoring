# backend/

Código em Python — API, pipelines de análise, motor de fusão de risco e integração com
serviços de nuvem. É a única parte do sistema que processa dados; o `frontend/` apenas
consome a API e não tem lógica própria.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `app/` | API (FastAPI): rotas, contratos de entrada/saída, ponto de entrada do servidor. Rotas: timeline do paciente, análise, alertas, evidência de um evento |
| `common/` | Código compartilhado por todas as análises: formato de evidência (como cada anomalia detectada é registrada com seu artefato visual), métricas, configuração, log |
| `pipelines/vitals/` | Análise de sinais vitais (frequência cardíaca, oxigenação, batimentos) e detecção de anomalias |
| `pipelines/audio/` | Análise de áudio: dificuldade respiratória, transcrição, termos clínicos críticos, sinais de fadiga vocal |
| `pipelines/video/` | Análise de vídeo: postura e padrões de movimentação (quedas), detecção de estruturas críticas em cirurgia |
| `pipelines/prescription/` | Leitura de prescrições médicas (PDF) e checagem de dose/variação anômala |
| `fusion/` | Combinação dos sinais das quatro análises acima num único indicador de risco, com alerta automático |
| `aws/` | Integração com serviços de nuvem (armazenamento, mensageria, banco de dados) — funciona tanto contra a nuvem real quanto contra um simulador local, sem precisar de conta na nuvem para desenvolver/testar |
| `scripts/` | Utilitários, incluindo o download dos conjuntos de dados públicos |
| `tests/` | Testes automatizados de tudo acima |

## Como rodar os testes

```bash
make test         # suíte completa
make test-unit    # só os testes rápidos (sem tocar em serviços externos)
make lint         # checagem de estilo
```
