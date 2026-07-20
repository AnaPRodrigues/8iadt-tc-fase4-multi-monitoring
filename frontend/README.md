# Frontend

App separado que consome a API do `backend/` (AD-029). Sem lógica de
processamento — só apresentação:

- timeline unificada do paciente (verde/amarelo/vermelho);
- replay do cenário de demo;
- visualização de evidências (frame anotado, transcript, gráfico da janela anômala, prescrição anotada).

Consome o contrato REST versionado: `/patients/{id}/timeline`, `/analyze`,
`/alerts`, `/evidence/{id}`.

**Framework a definir** — decisão adiada; não é bloqueante para F0 nem para a
migração de F3. Será registrada como AD quando escolhida.
