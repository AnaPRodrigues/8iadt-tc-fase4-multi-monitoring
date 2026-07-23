# Frontend

App separado que consome a API do `backend/` (AD-029). Sem lógica de
processamento — só apresentação:

- timeline unificada do paciente (verde/amarelo/vermelho);
- replay do cenário de demo;
- visualização de evidências (frame anotado, transcript, gráfico da janela anômala, prescrição anotada).

Consome o contrato REST versionado: `/patients/{id}/timeline`, `/analyze`,
`/alerts`, `/evidence/{id}`.

**Framework: Streamlit** (AD-044) — cliente fino consumindo `backend/app/`
(FastAPI), sem lógica de processamento própria.
