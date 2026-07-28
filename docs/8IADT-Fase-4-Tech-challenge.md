# TECH CHALLENGE - FASE 4

O Tech Challenge é o projeto que engloba os conhecimentos obtidos em todas as disciplinas desta fase. Esta atividade deve ser desenvolvida em grupo e é obrigatória, valendo 90% da nota de todas as disciplinas da fase.

## Desafio

Com a IA integrada aos processos médicos da instituição — analisando exames, documentos e apoiando decisões clínicas — o hospital agora deseja **monitorizar continuamente os pacientes por meio de dados multimodais** (áudio, vídeo e texto) para identificar sinais precoces de risco.

Além de processar laudos e exames, o sistema passará a:
* Analisar vídeos de cirurgias ou sessões de fisioterapia para identificar padrões anómalos.
* Processar gravações de voz de pacientes em consultas, detetando sintomas relacionados à fala (fadiga, disartria).
* Detetar anomalias em sinais vitais, prescrições e evolução clínica, alertando a equipa médica em tempo real.
* Integrar tudo isso com serviços geridos em nuvem, como Azure Cognitive Services.

## Objetivo

* Realizar a análise e fusão de diferentes tipos de dados médicos (texto, áudio, vídeo).
* Utilizar serviços em nuvem para ampliar a capacidade de processamento e inteligência.
* Aplicar técnicas de deteção de anomalias em tempo real para monitoramento preventivo.

---

## Requisitos Obrigatórios - Entregas Técnicas

### 1. Análise de Vídeo
* Processar vídeos clínicos (ex: sessões de fisioterapia ou cirurgias gravadas).
* Detetar movimentos ou eventos fora do padrão esperado, utilizando modelos como:
    * **MediaPipe Pose** para análise postural.
    * **YOLOv8** para deteção de objetos e áreas críticas.
* Gerar relatórios automáticos indicando desvios ou falhas no procedimento.

### 2. Análise de Áudio
* Processar áudios de consultas médicas.
* Detetar alterações vocais indicativas de condições médicas (ex: cansaço, dificuldades respiratórias).
* Utilizar **faster-whisper** para transcrever e analisar os áudios localmente.
* Identificar termos críticos e sentimentos com análise local.

### 3. Deteção de Anomalias
* Aplicar técnicas de deteção de anomalias em:
    * Séries temporais de sinais vitais (batimentos, pressão arterial, oxigenação).
    * Evolução de prescrições (alterações inesperadas no tratamento).
    * Padrões de movimentação do paciente durante a internação.
* Gerar alertas automáticos para a equipa médica com base nas anomalias detetadas.

---

## Sugestão de Datasets
* [PhysioNet](https://physionet.org/).
* [Google AudioSet](https://research.google.com/audioset/).

---

## Entregáveis da Fase 4

### Repositório Git:
* Código-fonte completo da solução.
* **Relatório técnico** contendo:
    * Descrição do fluxo multimodal.
    * Modelos aplicados em cada tipo de dado.
    * Resultados obtidos e exemplos de anomalias detetadas.

### Vídeo de demonstração:
* Duração de até **15 minutos**, hospedado no YouTube ou Vimeo.
* O vídeo deve demonstrar:
    * Processamento multimodal (exemplo prático de áudio e vídeo).
    * Deteção e resposta a anomalias.
    * Integração dos serviços AWS.
    * Fluxo final do alerta à equipa médica.

---

# Roteiro de Apresentação (Vídeo ≤ 15 min)

## Estrutura geral

| Bloco | Duração | Conteúdo |
| --- | --- | --- |
| 1. Abertura | 0:00–2:00 | Contexto do desafio, visão geral da solução |
| 2. Arquitetura | 2:00–4:00 | Explicação da arquitetura, modos local/AWS, decisões |
| 3. Paciente 1 | 4:00–7:00 | Fisioterapia + sinais vitais — ROM limitada e bradicardia |
| 4. Paciente 2 | 7:00–10:00 | Consulta respiratória + prescrição — sibilo e interação medicamentosa |
| 5. Paciente 3 | 10:00–12:30 | Cirurgia + evolução — visão crítica incompleta e sangramento |
| 6. Nuvem | 12:30–13:30 | Demonstração AWS: Textract + Rekognition (contexto de cena) |
| 7. Encerramento | 13:30–15:00 | Resultados, limitações, conclusão |

---

## Bloco 1 — Abertura (0:00–2:00)

**Objetivo:** Contextualizar o problema e apresentar a solução.

**O que mostrar:**
- Tela inicial do painel React com a lista de pacientes.
- Explicar que o sistema processa **4 fontes de dados** (vídeo, áudio, sinais vitais, prescrições) e as funde num **indicador único de risco**.
- Mencionar que o sistema funciona em **dois modos**: local (100% CPU, sem nuvem) e AWS (Textract + Rekognition).

**Fala sugerida:**
> "Este é o Monitoramento Hospitalar Multimodal, desenvolvido para o Tech Challenge da Fase 4. O desafio pede um sistema que processe dados de vídeo, áudio, sinais vitais e texto para monitorizar pacientes continuamente e alertar a equipa médica quando algo anómalo é detetado. Vamos ver como isto funciona na prática, com 3 pacientes e 6 eventos reais."

---

## Bloco 2 — Arquitetura e decisões (2:00–4:00)

**Objetivo:** Explicar a arquitetura da solução e as principais decisões de projeto.

**O que mostrar:**
- Diagrama da arquitetura (local e AWS) — pode ser o Mermaid do README projetado ou um slide.
- Terminal mostrando o log de atividade com `[LOCAL]` / `[AWS]`.

**Pontos a cobrir:**
1. **4 pipelines independentes** — cada um processa a sua modalidade e grava evidência. Não se conhecem.
2. **Evidência como contrato único** — toda anomalia gera artefato visual + JSON. "Nunca apontamos um risco sem mostrar o porquê."
3. **Motor de fusão** — late fusion com peso por modalidade, decaimento temporal e histerese para evitar oscilação.
4. **Modo local vs AWS** — tudo roda em CPU localmente. No modo AWS, dois serviços gerenciados (Textract e Rekognition) são usados como complemento. O Rekognition foi redirecionado de cirurgia para contexto de cena porque os seus labels genéricos não reconhecem anatomia.
5. **Porquê AWS e não Azure?** O ambiente do curso é AWS Academy. A arquitetura por adapter permite trocar o serviço sem mexer no código.

**Fala sugerida:**
> "Antes de vermos os pacientes, quero explicar como o sistema funciona por dentro. São 4 pipelines independentes — vídeo, áudio, sinais vitais e prescrições. Cada um processa a sua modalidade e grava uma evidência: um artefato visual mais um JSON descritor. A fusão lê essas evidências e calcula um risk score único. O sistema funciona 100% em CPU no modo local. No modo AWS, usamos dois serviços gerenciados — Textract para PDFs e Rekognition para contexto de cena na pipeline de postura. E aqui está uma decisão importante: o Rekognition era originalmente usado para cirurgia, mas descobrimos que os labels genéricos dele não reconhecem anatomia — ele diz 'Surgery', 'Hospital', não 'cystic_artery'. Por isso movemos o Rekognition para a pipeline de postura, onde ele analisa o ambiente ao redor do paciente — a cama, a cadeira de rodas, o equipamento médico. A cirurgia ficou sempre com YOLOv8 local."

---

## Bloco 3 — Paciente 1: Fisioterapia e monitoramento (4:00–7:00)

**Storyline:** Dona Helena, 72 anos, internada após fratura de fémur. Está em fisioterapia de reabilitação. O sistema monitoriza a sua amplitude de movimento e sinais vitais.

**O que mostrar:**

### 3a. Vídeo — Sessão de fisioterapia (4:00–5:30)
- Enviar um vídeo de fisioterapia (URFD ADL ou KIMORE) pelo painel.
- A pipeline de pose deteta **amplitude de flexão do joelho reduzida** (ROM < 30°) e **assimetria entre pernas** (>20°).
- Mostrar o frame anotado com os ângulos articulares.
- Mostrar o log do terminal: `[vídeo][LOCAL] avaliando postura e movimentação com MediaPipe Pose`.
- Se `ENV=aws`, mostrar o contexto de cena: `[vídeo][AWS] Rekognition detect_labels — cena` + `[vídeo][LOCAL] contexto clínico: Cadeira de Rodas (98%), Andador (95%)`.

### 3b. Sinais vitais — Bradicardia (5:30–7:00)
- Carregar um registo BIDMC com evento de bradicardia (HR < 60 bpm).
- Mostrar o gráfico da janela anómala com o心率 abaixo do limiar.
- A fusão combina os dois sinais: ROM reduzida (score 0.5) + bradicardia (score 0.6) → risco AMARELO (0.55).

**Fala sugerida:**
> "A Dona Helena está a recuperar de uma fratura de fémur. O sistema recebeu o vídeo da sessão de fisioterapia e o MediaPipe Pose analisou os ângulos articulares — aqui vemos o joelho esquerdo com flexão limitada a 28°, quando o esperado seria pelo menos 90°. Também foi detetada assimetria de 24° entre as pernas. Ao mesmo tempo, os sinais vitais mostram um episódio de bradicardia — a frequência cardíaca caiu para 52 bpm, abaixo do limiar de 60. A fusão combinou estes dois sinais e elevou o risco para AMARELO."
>
> *[Se ENV=aws]:* "Reparem no terminal: o Rekognition foi chamado para analisar o contexto de cena e identificou uma cadeira de rodas e um andador no quarto — informação que enriquece o contexto clínico."

> **Espaço para print — Paciente 1**
>
> *[Screenshot do painel mostrando a timeline da Dona Helena com os 2 eventos]*

---

## Bloco 4 — Paciente 2: Consulta respiratória e prescrição (7:00–10:00)

**Storyline:** Seu Carlos, 58 anos, asmático, veio à consulta com queixa de falta de ar. O sistema processa o áudio da consulta e cruza com o histórico de prescrições.

**O que mostrar:**

### 4a. Áudio — Consulta com sibilo (7:00–8:30)
- Enviar um áudio de consulta (TTS ou gravado pelo grupo) com termos críticos: "falta de ar", "cansaço", "chiado no peito".
- Mostrar a transcrição (faster-whisper) e os termos críticos detetados.
- Enviar também um áudio respiratório ICBHI com wheeze (sibilo).
- Mostrar a classificação: Random Forest → wheeze (confiança 96%).
- Log: `[áudio][LOCAL] classificando ciclos respiratórios` → `[áudio] análise concluída — Sibilo detectado (confiança 96%)`.

### 4b. Prescrição — Interação medicamentosa (8:30–10:00)
- Enviar uma prescrição com corticoide (ex.: prednisona 60 mg) quando o histórico do paciente já tinha outro fármaco (ex.: ibuprofeno).
- Mostrar o Textract a extrair o texto do PDF (se `ENV=aws`).
- O sistema deteta a escalada de dose e a interação entre AINE e corticoide.
- Mostrar o PDF anotado com os campos extraídos.
- Fusão: sibilo (score 0.7) + prescrição com interação (score 0.8) → risco VERMELHO → alerta gerado.

**Fala sugerida:**
> "O Seu Carlos é asmático e veio à consulta com falta de ar. O áudio da consulta foi transcrito pelo faster-whisper e os termos 'falta de ar' e 'chiado no peito' foram identificados. Em paralelo, o sistema analisou o áudio respiratório e o Random Forest classificou como sibilo com 96% de confiança. Quando a nova prescrição de prednisona chegou, o sistema comparou com o histórico e detetou uma interação com o ibuprofeno que o paciente já tomava — risco de hemorragia gastrointestinal. A fusão elevou o risco a VERMELHO e um alerta foi gerado automaticamente."
>
> *[Se ENV=aws]:* "O texto da prescrição foi extraído pelo Amazon Textract — vejam o requestId no log, é uma chamada real à nuvem."

> **Espaço para print — Paciente 2**
>
> *[Screenshot do painel mostrando a timeline do Seu Carlos com evento de áudio + prescrição + alerta VERMELHO]*

---

## Bloco 5 — Paciente 3: Cirurgia e evolução pós-operatória (10:00–12:30)

**Storyline:** Paciente Joana, 34 anos, colecistectomia laparoscópica. O sistema analisa o vídeo cirúrgico e monitoriza a evolução pós-operatória.

**O que mostrar:**

### 5a. Vídeo cirúrgico — Visão crítica incompleta (10:00–11:15)
- Enviar um frame ou vídeo cirúrgico do Endoscapes onde o YOLOv8 **não encontra a placa cística** — visão crítica de segurança incompleta.
- Mostrar o frame anotado com as bboxes: artéria cística ✓, ducto cístico ✓, placa cística ✗.
- Explicar: em colecistectomia, a CVS (Critical View of Safety) exige as 3 estruturas — a ausência de uma é um achado relevante.
- Log: `[vídeo cirúrgico][LOCAL] avaliando keyframes do vídeo cirúrgico com YOLOv8`.

### 5b. Sinais vitais — Taquicardia pós-operatória (11:15–12:30)
- Carregar um registo CTU-UHB (ou BIDMC) com taquicardia (>100 bpm).
- Mostrar o gráfico com FHR/HR elevado.
- Fusão: CVS incompleta (score 0.6) + taquicardia (score 0.5) → risco AMARELO (0.55).

**Fala sugerida:**
> "A Joana foi submetida a uma colecistectomia. O YOLOv8 fine-tuned analisou o vídeo cirúrgico e encontrou a artéria e o ducto císticos, mas não a placa cística — a visão crítica de segurança está incompleta. Isto é um achado cirúrgico relevante, documentado com evidência. No pós-operatório, os sinais vitais mostram taquicardia sustentada acima de 110 bpm. A fusão sobe o risco para AMARELO."
>
> "Reparem que a análise cirúrgica é sempre local — não usamos Rekognition aqui. O YOLOv8 foi treinado especificamente para estas 6 estruturas anatómicas. O Rekognition genérico não sabe o que é uma 'cystic_artery'."

> **Espaço para print — Paciente 3**
>
> *[Screenshot do painel mostrando a timeline da Joana com evento cirúrgico + vitais]*

---

## Bloco 6 — Demonstração da nuvem AWS (12:30–13:30)

**Objetivo:** Mostrar que as chamadas AWS são reais — exibir o terminal com os logs `[AWS]`.

**O que mostrar:**
- Terminal com a API a correr em modo `ENV=aws`.
- Enviar uma prescrição e mostrar o log do Textract: `[prescrição][AWS] Textract analyze_document — 148 blocos extraídos em 4.1s — requestId=b32c62b9...`.
- Enviar um vídeo de postura e mostrar o Rekognition a analisar o contexto de cena: `[vídeo][AWS] Rekognition detect_labels — cena (45321 bytes)` → `[vídeo][AWS] 23 rótulos reconhecidos em 0.8s — requestId=3a77ddf4...` → `[vídeo][LOCAL] contexto clínico: Cadeira de Rodas (98%), Cama (99%)`.

**Fala sugerida:**
> "Vamos confirmar que as chamadas à nuvem são reais. Aqui está o terminal com ENV=aws. Ao enviar esta prescrição, o Textract processa o PDF na nuvem — 148 blocos extraídos, e aqui está o requestId da AWS que comprova a chamada. No vídeo de postura, o Rekognition analisa o ambiente e identifica 'Cadeira de Rodas' com 98% e 'Cama' com 99% de confiança — labels filtrados pelo nosso mapa clínico de 35 objetos relevantes. Isto enriquece o resultado da análise postural com contexto ambiental. Tudo o resto — pose, áudio, sinais vitais — continua 100% local."

---

## Bloco 7 — Encerramento (13:30–15:00)

**Objetivo:** Resumir resultados, reconhecer limitações, concluir.

**O que mostrar:**
- Visão geral do painel com os 3 pacientes e os seus níveis de risco.
- Tabela resumo: 3 pacientes, 6 eventos, 478 testes, zero falhas.

**Pontos a cobrir:**
1. **Resultados:** 3 pacientes monitorizados com 6 eventos reais. Deteção de quedas com 80% recall, 100% precisão. YOLOv8s com mAP@50-95 de 0.3837. 478 testes passando.
2. **Limitações transparentes:** Pressão arterial (trabalho futuro — VitalDB). Disartria (sem dataset pt-BR rotulado). Queda lenta `fall-05` abaixo do limiar (documentado).
3. **Decisões fundamentadas:** AWS em vez de Azure (ambiente do curso). MediaPipe em vez de OpenPose (CPU-friendly). faster-whisper em vez de Azure Speech (local, sem custo). Rekognition redirecionado para contexto de cena (labels genéricos não servem para anatomia).
4. **O que faríamos diferente:** Com mais tempo, integraríamos a pressão arterial via VitalDB e treinaríamos um detector de disartria com dados em português.

**Fala sugerida:**
> "Para resumir: demonstrámos 3 pacientes com 6 eventos reais processados por 4 pipelines independentes, fundidos num único indicador de risco. O sistema tem 478 testes, zero falhas, e funciona 100% em CPU no modo local. As limitações estão documentadas com transparência no relatório técnico. Cada decisão de arquitetura tem um porquê registado. Obrigado."

---

## Preparação para a gravação

- [ ] `make install && make data && make models-fetch` — ambiente pronto
- [ ] `make seed-demo` — pacientes de demonstração criados (se já existirem, é idempotente)
- [ ] `make serve-api` (Terminal 1) — API a correr em `localhost:8000`
- [ ] `make serve-front` (Terminal 2) — Painel em `localhost:5173`
- [ ] Para o Bloco 6 (AWS): configurar `.env` com `ENV=aws`, exportar credenciais AWS, reiniciar a API
- [ ] Gravar os 3 áudios de consulta (Blocos 3-5) ou gerar com `make tts-consulta`
- [ ] Ter o relatório técnico aberto para referência durante a gravação

## Dicas para o vídeo

- **Mostra, não descrevas.** O terminal a fazer logging em tempo real vale mais que 5 slides.
- **O terminal é o teu aliado.** Os logs `[LOCAL]`/`[AWS]` são a prova visual de cada etapa.
- **15 minutos é o máximo, não a meta.** Se conseguires contar a história em 12, melhor.
- **Prepara os prints antes.** Coloca os screenshots do painel nos espaços marcados neste roteiro para poderes fazer cut durante a edição.
- **Faz o fluxo AWS por último** — assim aproveitas o mesmo terminal com as credenciais ainda válidas.
