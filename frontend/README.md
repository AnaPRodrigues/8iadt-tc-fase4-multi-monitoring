# frontend/

Painel web do sistema de monitoramento multimodal. É uma aplicação de página única
(React + Vite) que **apenas consome a API** do backend — não tem nenhuma lógica de
processamento própria; toda a análise acontece no backend.

## Telas

- **Pacientes** — lista de pacientes com o nível de risco atual de cada um (indicador
  colorido); formulário para cadastrar e ação para remover.
- **Detalhe do paciente** — a tela principal: cabeçalho com o nível de risco atual em
  destaque, envio de arquivos (vídeo, áudio, documento PDF, sinais vitais), um painel
  por modalidade com o último achado em linguagem clínica, a linha do tempo da
  pontuação de risco (com as linhas de atenção e de alerta e marcadores por evento),
  os alertas do paciente e o detalhe da evidência de cada evento.
- **Alertas** — lista de todos os alertas, com filtro por paciente e por nível.

## Pré-requisitos

- [Node.js](https://nodejs.org/) 18 ou mais recente (inclui o `npm`).
- A **API do backend** rodando (ver o `README.md` da raiz do projeto). O painel só
  funciona com a API de pé.

## Como rodar (passo a passo)

A partir da **raiz do projeto**, usando os atalhos do Makefile:

```bash
# 1. Instalar as dependências do painel (só na primeira vez)
make frontend-install

# 2. Em um terminal, subir a API do backend
make serve-api          # fica em http://localhost:8000

# 3. Em outro terminal, subir o painel
make serve-front        # abre em http://localhost:5173
```

Abra `http://localhost:5173` no navegador. Cadastre um paciente, envie um arquivo para
ele e acompanhe a análise, a linha do tempo de risco e os alertas.

> Para popular o painel com pacientes de demonstração já prontos (sem cadastrar à mão),
> veja o comando de carga inicial no `README.md` da raiz.

## Rodar direto pelo npm (alternativa)

Dentro desta pasta:

```bash
npm install            # primeira vez
npm run dev            # servidor de desenvolvimento (http://localhost:5173)
npm run build          # build de produção em dist/
```

O endereço da API é configurável pela variável `API_BASE_URL` (padrão
`http://localhost:8000`); o Vite faz o proxy das chamadas de API para lá.

## Pilha

React, Vite, react-router (navegação) e Recharts (gráfico da linha do tempo). As
chamadas à API usam `fetch`. Dependências propositalmente enxutas — sem renderização no
servidor e sem biblioteca de componentes pesada.
