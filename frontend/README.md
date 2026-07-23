# frontend/

Painel de visualização (Streamlit) que consome a API do `backend/` — sem nenhuma
lógica de processamento própria, só apresentação:

- linha do tempo unificada do paciente, com o nível de risco (verde/amarelo/vermelho)
  ao longo do tempo;
- reprodução controlada de um cenário de demonstração;
- visualização da evidência de cada evento (frame de vídeo anotado, transcrição com o
  termo destacado, gráfico do sinal vital anômalo, prescrição anotada — conforme a
  origem do evento).

Fala com o backend só por HTTP, consumindo as rotas: linha do tempo do paciente,
análise, alertas e evidência de um evento.
