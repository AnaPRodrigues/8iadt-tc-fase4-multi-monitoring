# Roteiro de Apresentação — Vídeo de Demonstração (≤ 15 min)

**Tech Challenge — Fase 4 · POSTECH 8IADT**
**Sistema:** Monitoramento Hospitalar Multimodal

---

## Estrutura do vídeo (13–15 min)

| Bloco | Duração | O que cobre |
|---|---|---|
| 1. Abertura — o problema e a solução | 0:00–1:30 | 1 min 30 s |
| 2. Demonstração ao vivo — paciente A (queda + vitais) | 1:30–5:30 | 4 min |
| 3. Demonstração — paciente B (cirurgia + prescrição) | 5:30–8:30 | 3 min |
| 4. Demonstração — paciente C (ausculta + internação) | 8:30–11:00 | 2 min 30 s |
| 5. Nuvem — processamento com AWS Textract/Rekognition | 11:00–12:30 | 1 min 30 s |
| 6. Arquitetura e decisões de projeto | 12:30–14:00 | 1 min 30 s |
| 7. Encerramento — resultados, limitações e conclusão | 14:00–15:00 | 1 min |

---

## Bloco 1 — Abertura: o problema e a solução (0:00–1:30)

**Tela:** Slide de título ou README do projeto.

**Fala sugerida:**

> "Um paciente internado gera dados o tempo todo — vídeo de monitoramento, áudio de
> consultas, sinais vitais contínuos, prescrições que evoluem ao longo dos dias. Mas
> esses dados estão em silos. O vídeo está numa estação de enfermagem, o áudio noutro
> sistema, os vitais num monitor de beira de leito, a prescrição num prontuário
> eletrônico. Nenhum deles conversa com os outros.
>
> O que a gente construiu foi um sistema que **unifica essas quatro fontes** num único
> indicador de risco que evolui no tempo. Se o risco cruza um limiar, o sistema gera um
> alerta automático — e o médico consegue clicar no alerta e ver **exatamente** qual
> evidência disparou aquilo, em qual modalidade.
>
> Este vídeo mostra o sistema funcionando ao vivo: três pacientes diferentes, dados
> reais de 6 datasets públicos, quatro modalidades de análise, fusão de risco e alerta.
> As análises rodam 100% na minha máquina; a nuvem entra como um complemento — dois
> serviços gerenciados da AWS que eu mostro a seguir."

**Transição:** "Vamos começar pelo paciente A."

---

## Bloco 2 — Paciente A: queda + monitoramento fetal (1:30–5:30)

**Objetivo:** Mostrar as duas raias de vídeo (pose) e sinais vitais (CTG), a fusão das
duas modalidades e o drill-down de evidência.

### 2.1 Painel inicial e paciente A (1:30–2:30)

**Tela:** Painel React (`localhost:5173`), ecrã de lista de pacientes.

**Ações:**
1. Mostrar a lista de pacientes (3 pacientes criados por `make seed-demo`)
2. Clicar no **Paciente A — Queda e monitoramento fetal**
3. Apontar o indicador de risco (deve estar amarelo ou vermelho por causa dos eventos)
4. Mostrar o cabeçalho: nome, nível de risco em destaque com cor

**Fala sugerida:**

> "O painel lista os pacientes cadastrados, cada um com um indicador de risco colorido.
> Começo pelo Paciente A. Ele tem dois eventos registrados: uma queda detectada por
> vídeo e uma anomalia nos sinais vitais fetais.
>
> Reparem no indicador de risco aqui em cima — está em atenção. Esse número não é um
> palpite: ele é a soma ponderada dos eventos do paciente. Cada evento tem um peso, e
> eventos antigos perdem força com o tempo."

### 2.2 Envio de vídeo e detecção de queda (2:30–3:30)

**Tela:** Ecrã de detalhe do Paciente A, área de envio, depois o resultado.

**Ações:**
1. Se já tiver o evento de vídeo (URFD `fall-01`), mostrar o painel de modalidade
   "Vídeo" com o achado: "Queda detectada — score de movimento 0.31"
2. Clicar no botão de evidência → mostrar o frame anotado (se disponível)
3. Explicar que o MediaPipe Pose extrai 33 keypoints por frame e o sistema detecta a
   queda pela variação brusca do centro de massa
4. Se quiser mostrar o envio ao vivo: arrastar a pasta `data/urfd/fall-01/` para a
   área de envio e ver o progresso (recebido → processando → concluído)

**Fala sugerida:**

> "Esse paciente tem um vídeo da raia de postura. O sistema usou o MediaPipe Pose —
> mesmo tipo de modelo que o OpenPose sugerido no enunciado, mas mais leve para CPU —
> para extrair o esqueleto frame a frame. A queda foi detectada pela variação brusca do
> centro de massa.
>
> Se eu clicar na evidência, o sistema mostra o frame exato onde a queda foi detectada.
> Isso é uma regra do projeto: **toda anomalia é reproduzível**. Nenhum alerta é gerado
> sem uma evidência que o justifique."

### 2.3 Sinais vitais fetais (CTG) (3:30–4:30)

**Tela:** Painel de modalidade "Sinais Vitais" do Paciente A.

**Ações:**
1. Mostrar o achado: "Janela anômala detectada — pH real do registo = 7.14 (acidose
   fetal)"
2. Clicar na evidência → gráfico da janela anômala com destaque
3. Explicar o gráfico: frequência cardíaca fetal (FHR) e contrações uterinas (UC), com
   a janela anômala destacada a vermelho

**Fala sugerida:**

> "Na modalidade de sinais vitais, este paciente tem um registo de cardiotocografia —
   o exame que monitora o batimento cardíaco do feto e as contrações durante o parto.
> O sistema correu dois detectores: um z-score móvel, que procura valores muito
> distantes da janela local, e uma Isolation Forest, que detecta combinações anômalas
> de características.
>
> O importante aqui: o pH real deste registo é 7.14 — abaixo de 7.05 é acidose fetal.
> O rótulo de referência é **clínico e real**, não foi injetado por nós. Isso dá
> métricas de precisão e recall honestas, que estão no relatório técnico."

### 2.4 Fusão das duas modalidades (4:30–5:30)

**Tela:** Linha do tempo de risco (gráfico Recharts) e painel de alertas.

**Ações:**
1. Descer até à linha do tempo de risco
2. Apontar os marcadores de evento (queda, anomalia CTG) no eixo horizontal
3. Mostrar como a curva de risco sobe a cada evento
4. Apontar as linhas de atenção (amarelo) e alerta (vermelho)
5. Mostrar o alerta gerado: nível, modalidades contribuintes, links de evidência
6. Clicar num evento da linha do tempo → drill-down para a evidência

**Fala sugerida:**

> "Agora a fusão. Cada evento do paciente — a queda e a anomalia fetal — contribui
> para um risk score único. O gráfico mostra a linha do tempo: a linha azul é o score
> de risco, que sobe quando um evento novo aparece e decai exponencialmente com o
> tempo. As faixas de atenção e alerta estão marcadas.
>
> O classificador usa histerese: ele só sobe de verde para amarelo quando o score cruza
> 0,30, e para vermelho quando cruza 0,70. Mas para descer, precisa cair abaixo do
> limiar menos uma banda de histerese. Isso evita que o nível fique oscilando na
> fronteira — algo que aconteceria se fosse um simples `if score > 0.7`.
>
> Quando o nível cruza o limiar de disparo, o sistema gera um alerta. Ele diz qual é o
> nível, quais modalidades contribuíram e dá o link direto para a evidência. O médico
> não recebe só 'o paciente está em risco' — recebe 'está em risco por causa destes
> dois eventos, e aqui estão as imagens e os gráficos que provam'."

**Transição:** "Vamos para o paciente B, que cobre as outras duas modalidades."

---

## Bloco 3 — Paciente B: cirurgia + prescrição (5:30–8:30)

**Objetivo:** Mostrar a raia de objetos (YOLOv8), a prescrição (PDF) e o contraste entre
processamento local e de nuvem.

### 3.1 Vídeo cirúrgico — detecção de estruturas críticas (5:30–6:30)

**Tela:** Ecrã de detalhe do Paciente B.

**Ações:**
1. Clicar no Paciente B — Pós-operatório e prescrição
2. Mostrar o painel "Vídeo" → achado: estruturas anatómicas identificadas
3. Clicar na evidência → frame cirúrgico com bounding boxes (artéria cística, ducto
   cístico, placa cística)
4. Mencionar que o modelo YOLOv8 foi fine-tuned no Endoscapes2023 e está publicado no
   Hugging Face

**Fala sugerida:**

> "O Paciente B tem um quadro de vídeo cirúrgico laparoscópico. Este é um caso bem
> diferente do paciente A: aqui o sistema usa o nosso detector YOLOv8, treinado sobre
> o dataset Endoscapes2023, para identificar estruturas anatómicas críticas.
>
> Na evidência, o frame original aparece com as caixas delimitadoras: artéria cística,
> ducto cístico, placa cística — as estruturas da visão crítica de segurança. O modelo
> é um YOLOv8s com 100 épocas de treino, e o peso treinado está publicado no Hugging
> Face Hub. Qualquer pessoa pode baixar com `make models-fetch`."

### 3.2 Prescrição — PDF com dose fora da faixa (6:30–7:30)

**Tela:** Painel "Prescrição" do Paciente B.

**Ações:**
1. Mostrar o achado: "Digoxina 1,5 mg — dose acima da faixa terapêutica [0,125; 0,5] mg"
2. Explicar que é uma prescrição sintética gerada para demonstração (a única fonte
   sintética do projeto, justificada no relatório)
3. Se o PDF anotado estiver disponível como evidência, mostrar

**Fala sugerida:**

> "A outra análise deste paciente é uma prescrição. O sistema leu o PDF, extraiu os
> campos — fármaco, dose, frequência — e comparou com as faixas terapêuticas de
> referência. A digoxina apareceu com 1,5 miligramas, quando a faixa segura é de 0,125
> a 0,5. Isso disparou um alerta de 'dose fora da faixa'.
>
> Esta é a única fonte sintética do projeto — porque não existe dataset público de
> prescrições reais com erros de dose anotados sem credenciamento hospitalar. O
> documento é sintético, mas a regra clínica é real. O relatório técnico documenta isso
> com transparência."

### 3.3 Fusão no paciente B (7:30–8:30)

**Tela:** Linha do tempo do Paciente B, mostrando o risco composto.

**Ações:**
1. Mostrar a linha do tempo com os dois eventos (estrutura crítica + dose fora da faixa)
2. Mostrar o alerta combinado
3. Destacar que o painel mostra o último achado de cada modalidade em **linguagem
   clínica**, não em formato técnico (ex.: "Estrutura anatómica crítica identificada",
   não "mAP@50 = 0.6046")

**Fala sugerida:**

> "Reparem que o painel traduz cada achado para linguagem clínica. O médico não vê
> 'mAP @ 0.50 = 0.6046' — isso está no relatório técnico para quem quiser auditar. O
> médico vê 'Estrutura anatómica crítica identificada em quadro cirúrgico', com um link
> para a imagem anotada."

**Transição:** "O paciente C mostra o pipeline de áudio e o segundo caso de sinais
vitais."

---

## Bloco 4 — Paciente C: ausculta + internação (8:30–11:00)

**Objetivo:** Mostrar o pipeline de áudio (ICBHI), os sinais vitais de UTI adulta
(BIDMC) e a cobertura de SpO2.

### 4.1 Áudio — dificuldade respiratória (8:30–9:30)

**Tela:** Ecrã de detalhe do Paciente C.

**Ações:**
1. Clicar no Paciente C — Ausculta e internação
2. Mostrar o painel "Áudio" → achado: "Estertor e sibilo — confiança 98%"
3. Clicar na evidência → trecho do ciclo respiratório
4. Explicar o pipeline de áudio (ICBHI → Random Forest sobre features acústicas)

**Fala sugerida:**

> "O pipeline de áudio tem várias camadas. A que está a ver agora é a classificação
> respiratória: o sistema analisou um ciclo de ausculta do dataset ICBHI 2017 e
> classificou como 'both' — estertor e sibilo simultâneos — com 98% de confiança. O
> classificador é uma Random Forest treinada sobre features acústicas extraídas com
> Librosa.
>
> O pipeline de áudio também tem transcrição com faster-whisper em português, extração
> de termos clínicos críticos e análise de fadiga vocal. Mas essas etapas dependem de
> um áudio de consulta com fala — e isso é o único dado que ainda não está
> automatizado. Fica documentado como gravação pendente."

### 4.2 Sinais vitais de UTI — SpO2 (9:30–10:30)

**Tela:** Painel "Sinais Vitais" do Paciente C.

**Ações:**
1. Mostrar o achado: "Saturação de oxigénio abaixo de 90% — hipoxemia"
2. Clicar na evidência → gráfico do SpO2 ao longo do tempo com a janela anômala
   destacada
3. Explicar que este é o BIDMC — registo real de UTI adulta, sem desfecho anotado,
   por isso a avaliação é contra critérios clínicos publicados

**Fala sugerida:**

> "Este paciente tem um registo de sinais vitais de UTI adulta — o dataset BIDMC, do
> PhysioNet. É um par diferente do CTG fetal: aqui estamos a ver frequência cardíaca e
> saturação de oxigénio de um paciente internado.
>
> O sistema detectou uma janela onde a SpO2 caiu abaixo de 90% — critério clínico de
> hipoxemia. O BIDMC não vem com desfecho anotado como o CTU-UHB, por isso a nossa
> referência de avaliação são critérios clínicos publicados, e isso está dito com
> transparência no relatório.
>
> Este segundo caso de sinais vitais fecha a cobertura de oxigenação do enunciado.
> Pressão arterial continua como trabalho futuro — a fonte está identificada, mas são
> 94 GB, inviável para o prazo de 7 dias."

### 4.3 Fusão (10:30–11:00)

**Tela:** Linha do tempo do Paciente C.

**Ações:**
1. Mostrar o risco combinado e o alerta (se houver)
2. Transitar para o bloco da nuvem

**Fala sugerida:**

> "Mais uma vez, dois eventos de modalidades diferentes a alimentar o mesmo indicador
> de risco. E isto traz-nos ao próximo ponto: onde é que a nuvem entra nisto tudo?"

---

## Bloco 5 — Nuvem: AWS Textract e Rekognition (11:00–12:30)

**Objetivo:** Demonstrar o modo `aws` com os dois serviços gerenciados, mostrar o log
de atividade com origem `[AWS]` e explicar o padrão adapter.

### 5.1 Demonstração do modo aws (11:00–12:00)

**Tela:** Terminal com a API a correr em modo `aws` + painel.

**Ações:**
1. Parar a API, mudar `ENV=aws`, subir de novo
2. Enviar o PDF de prescrição (ou um frame de vídeo) de novo
3. Mostrar o terminal com as linhas `[AWS]`:
   ```
   14:35:04 [prescrição][AWS] Textract analyze_document — 34 blocos extraídos em 1.8s — requestId=a1b2c3d4
   ```
4. Voltar ao painel e mostrar que o resultado é o mesmo — o adapter mudou, o
   comportamento não

**Fala sugerida:**

> "O sistema tem dois modos, escolhidos por uma variável de ambiente. No modo `local`,
> tudo roda na máquina: pdfplumber para PDF, YOLOv8 para imagem. No modo `aws`, o
> sistema chama dois serviços gerenciados: Textract para extrair texto e campos de PDF,
> e Rekognition para detetar objetos em imagens.
>
> O terminal mostra a origem de cada processamento: `[LOCAL]` quando resolvido na
> máquina, `[AWS]` quando houve chamada à nuvem — e a linha inclui o serviço chamado, a
> duração e o requestId da resposta. É uma evidência de que a chamada foi real, não um
> mock.
>
> Isto são os únicos dois serviços de nuvem no sistema — nada de S3, nada de filas,
> nada de funções serverless. O arquivo vai direto na chamada, o resultado volta, e o
> resto do processamento é local."

### 5.2 Padrão adapter e justificativa (12:00–12:30)

**Tela:** Voltar aos slides ou mostrar o código (opcional).

**Fala sugerida:**

> "O segredo para isto funcionar é um padrão adapter. Extração de texto é uma
> interface; há duas implementações atrás dela — pdfplumber para `local`, Textract para
> `aws`. O resto do código não sabe qual está a usar. Trocar de modo é trocar uma
> variável de ambiente.
>
> O enunciado original pedia Azure Cognitive Services. Nós usamos AWS porque é o
> ambiente de curso disponível, e o nosso adapter torna cada serviço substituível — se
> amanhã quisermos voltar para Azure, é só escrever um adapter novo. O comportamento do
> sistema não muda."

**Transição:** "Com o sistema a funcionar, deixa eu mostrar como ele é construído por
dentro."

---

## Bloco 6 — Arquitetura e decisões de projeto (12:30–14:00)

**Tela:** Diagrama de arquitetura (do README) ou slides com a estrutura de pastas.

### 6.1 As quatro camadas (12:30–13:15)

**Fala sugerida:**

> "A arquitetura tem quatro camadas. A primeira são as **análises independentes** —
> vídeo, áudio, vitais e prescrição. Cada uma é um pipeline isolado que recebe um
> ficheiro e produz um achado. Elas não se conhecem — não há `import video` dentro de
> `audio`.
>
> A segunda camada é o **contrato de evidência**. Toda anomalia gera um artefato visual
> e um JSON descritor. A evidência é o único ponto de contacto entre as análises e a
> fusão.
>
> A terceira é o **motor de fusão**. Ele lê as evidências, aplica pesos por modalidade
> e decaimento temporal, e produz o risk score. O classificador com histerese decide o
> nível. Quando o nível sobe, o alerta é gerado — e fica registado no banco local.
>
> A quarta é a **camada de apresentação**: uma API REST em FastAPI que o painel React
> consome por HTTP. O frontend não tem lógica de processamento — só apresenta o que a
> API devolve."

### 6.2 Decisões que vale a pena mencionar (13:15–14:00)

**Tela:** Manter o diagrama ou alternar para bullet points.

**Fala sugerida (escolher 3–4 pontos, não ler todos):**

> "Quatro decisões de projeto que vale a pena destacar:
>
> **Primeira — local-first.** O sistema roda inteiro em CPU, sem Docker, sem GPU. Só o
> treino do YOLOv8 é que usou uma GPU gratuita do Google Colab, uma única vez. O peso
> treinado está publicado no Hugging Face Hub.
>
> **Segunda — dado real, não sintético.** Cinco dos seis datasets usados são reais e
> públicos. O único dado sintético é a prescrição de demonstração, porque não existe
> alternativa aberta. E o ground truth dos sinais vitais é o pH real do cordão
> umbilical — não foi injetado por nós.
>
> **Terceira — evidência sempre reproduzível.** Nenhum alerta é gerado sem uma
> evidência que o justifique. O médico pode clicar e ver exatamente o que disparou o
> alerta.
>
> **Quarta — verificação independente.** Cada módulo do sistema foi verificado por uma
> segunda passagem que incluiu um sensor de discriminação — um programa que injeta
> defeitos de propósito e confirma que os testes os detetam. Hoje são 475 testes
> passando, zero falhas."

---

## Bloco 7 — Encerramento: resultados, limitações e conclusão (14:00–15:00)

**Tela:** Slide com tabela de resultados + limitações.

**Fala sugerida:**

> "Para fechar. O sistema cobre todos os requisitos obrigatórios do enunciado. Vídeo
> com duas raias — pose e objetos. Áudio com classificação respiratória, transcrição,
> termos e fadiga. Sinais vitais com dois casos — cardiotocografia fetal e UTI adulta,
> cobrindo frequência cardíaca e oxigenação. Prescrição com extração de PDF e regras de
> dose. Fusão multimodal com decaimento temporal e alerta explicável. Nuvem com dois
> serviços gerenciados, intercambiáveis por adapter.
>
> O que ficou para trabalho futuro está documentado com transparência: pressão arterial
> e disartria — ambos sem dataset aberto viável no prazo. Nenhuma lacuna foi mascarada
> como 'coberto'.
>
> O projeto está no GitHub, o peso do modelo está no Hugging Face, e qualquer pessoa
> consegue reproduzir tudo com quatro comandos: `make install`, `make data`, `make
> models-fetch` e `make seed-demo`."

**Tela final:** Link do repositório + QR code (opcional).

**Fala sugerida:**

> "Obrigada. O repositório está neste endereço, com o relatório técnico completo, as
> decisões de arquitetura, os relatórios de verificação e as instruções para rodar."

---

## Resumo: o que preparar antes de gravar

| # | Item | Estado |
|---|---|---|
| 1 | `make seed-demo` — ter os 3 pacientes criados e as análises concluídas | Rodar antes |
| 2 | `make serve-api` + `make serve-front` — ter o painel a funcionar | 2 terminais |
| 3 | Dados de demo — confirmar que os 6 datasets estão em `data/` | `make data` |
| 4 | Modelo — confirmar que `models/best.pt` existe | `make models-fetch` |
| 5 | Modo `aws` — se quiser demonstrar, ter credenciais do Learner Lab prontas | Opcional |
| 6 | Slides de apoio (título, arquitetura, resultados, limitações) | 4–5 slides |
| 7 | Ensaio de tempo — gravar um take de teste e medir | 1–2 takes |

---

## Dicas para a gravação

- **Mostra, não descrevas.** O espectador deve ver o sistema a funcionar mais tempo do
  que te ouve a explicar. Cada bloco de demonstração começa com uma ação visível.
- **O terminal é teu aliado.** As linhas `[LOCAL]`/`[AWS]` foram desenhadas para o vídeo
  — usa o terminal como 'narrador' do que o sistema está a fazer.
- **Linguagem clínica no painel, métricas no relatório.** O painel mostra "Queda
  detectada", não "score de movimento 0.31". Se alguém quiser os números, estão no
  relatório técnico.
- **15 minutos é o máximo, não a meta.** Se conseguires contar a história completa em
  12–13 minutos, melhor. O tempo extra é margem de segurança.
- **Grava em 1080p.** O painel tem texto pequeno nos painéis de evidência; quanto maior
  a resolução, mais legível.
