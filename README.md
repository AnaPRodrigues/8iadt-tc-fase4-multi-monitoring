# Monitoramento Hospitalar Multimodal

Sistema que combina quatro fontes de dados de um paciente — vídeo, áudio, sinais vitais
e prescrições médicas — para gerar um indicador único de risco e alertar a equipe
automaticamente quando algo preocupante é detectado.

## O que o sistema faz

- **Vídeo**: analisa a postura e os padrões de movimentação do paciente (detectando
  quedas, por exemplo) e, em contexto cirúrgico, identifica estruturas anatômicas
  críticas em imagens de cirurgia.
- **Áudio**: identifica sinais de dificuldade respiratória em gravações de ausculta,
  transcreve consultas, destaca termos clínicos críticos mencionados e estima sinais de
  fadiga vocal.
- **Sinais vitais**: monitora frequência cardíaca, oxigenação e outros sinais contínuos,
  detectando anomalias em tempo quase real.
- **Prescrições**: lê receitas médicas (PDF) automaticamente e verifica se a dose
  prescrita está fora da faixa segura ou mudou abruptamente em relação ao histórico do
  paciente.
- **Fusão e alerta**: combina os sinais das quatro análises acima num único indicador de
  risco (verde/amarelo/vermelho) ao longo do tempo, e dispara um alerta por e-mail para
  a equipe quando o risco ultrapassa um limiar, com links para a evidência que motivou
  o alerta.
- **Painel**: um painel visual mostra a linha do tempo do paciente, permite reproduzir
  um cenário de demonstração e ver o detalhe de cada evento detectado.

Cada anomalia detectada gera uma evidência reproduzível (uma imagem, um trecho de
áudio destacado, um gráfico) — o sistema nunca aponta um risco sem mostrar o porquê.

## Como o sistema é organizado

```
backend/    API e toda a lógica de processamento (Python)
frontend/   Painel visual (Streamlit), consome só a API do backend
training/   Treino do modelo de detecção de estruturas cirúrgicas (roda à parte, numa GPU)
models/     Modelos já treinados, prontos para uso (baixados, não gerados aqui)
data/       Conjuntos de dados públicos usados pelas análises (baixados, não versionados)
```

O sistema roda inteiro num processador comum (CPU) — nenhuma GPU é necessária para usar
o sistema no dia a dia. Só o treino do modelo de detecção de estruturas cirúrgicas
(pasta `training/`) se beneficia de uma GPU, e roda separadamente, uma única vez.

Os serviços de nuvem usados (armazenamento de arquivos, envio de alertas, banco de
dados) rodam contra um **simulador local** por padrão — não é preciso ter uma conta na
AWS para instalar, rodar os testes ou executar a demonstração completa.

## Pré-requisitos

- Python 3.12 ou mais recente
- [Docker](https://www.docker.com/) (para o simulador local de nuvem)
- Cerca de 30 GB de espaço livre em disco para os conjuntos de dados públicos (a maior
  parte é o conjunto de imagens de cirurgia, usado para treinar/avaliar o detector de
  estruturas críticas)

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

## Baixar os dados

```bash
make data
```

Baixa os conjuntos de dados públicos usados pelas análises (detalhes em
`data/README.md`). Pode levar alguns minutos, dependendo da conexão.

## Subir o simulador de nuvem

```bash
make localstack-up
```

Sobe, via Docker, um simulador local dos serviços de nuvem usados pelo sistema
(armazenamento, mensageria, banco de dados) — assim é possível rodar tudo sem uma conta
AWS de verdade. Para desligar depois: `make localstack-down`.

## Rodar os testes

```bash
make test
```

## Usar o modelo de detecção já treinado

O sistema depende de um modelo treinado para detectar estruturas cirúrgicas em vídeo.
Para baixar um modelo já treinado e publicado (mais simples, recomendado para só
experimentar o sistema):

```bash
make models-fetch
```

Para treinar o seu próprio modelo do zero (leva algumas horas, numa GPU gratuita do
Google Colab), veja o passo a passo em `training/README.md`.

## Rodar a demonstração ponta a ponta

```bash
make demo
```

Roda a análise de sinais vitais sobre um cenário de exemplo, do início ao fim, e grava
as evidências geradas em `output/`. A análise de áudio também tem um comando próprio
(`backend/pipelines/audio/cli.py`) que pode ser rodado da mesma forma — veja
`backend/README.md` para os detalhes de cada análise, incluindo as que ainda não têm um
comando de demonstração dedicado.

## Sobre os dados usados

Todas as análises usam conjuntos de dados públicos, reais e anonimizados (nunca dados
sintéticos ou fabricados, exceto onde documentado explicitamente) — ver `data/README.md`
para a origem exata de cada um.
