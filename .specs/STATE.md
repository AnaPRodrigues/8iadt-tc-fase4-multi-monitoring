# STATE

## Decisions

### AD-001
- **Decision**: Usar AWS Academy (Learner Lab) no lugar de Azure para todos os serviços gerenciados de nuvem.
- **Reason**: Aprovado pelo professor; Azure Cognitive Services do enunciado original não está disponível no ambiente do grupo.
- **Trade-off**: Perde-se o catálogo de serviços cognitivos do Azure (Speech to Text, Text Analytics); precisa substituir por equivalentes locais/AWS.
- **Scope**: Todas as features (F1–F5).
- **Date**: 2026-07-20
- **Status**: active

### AD-002
- **Decision**: Lista fechada de serviços AWS permitidos no Learner Lab: S3, Lambda, SNS, SQS, DynamoDB, EventBridge, Step Functions, CloudWatch, Rekognition, Textract, SageMaker (limitado), API Gateway, Secrets Manager. Transcribe e Comprehend NÃO estão disponíveis.
- **Reason**: Restrição da conta AWS Academy — usar serviço fora da lista pode desativar a conta.
- **Trade-off**: Nenhuma transcrição/NLP gerenciada na nuvem; tudo precisa de alternativa local.
- **Scope**: Todas as features (F1–F5), especialmente F1 (Rekognition), F2 (sem Transcribe/Comprehend), F4 (Textract).
- **Date**: 2026-07-20
- **Status**: active

### AD-003
- **Decision**: Transcrição de áudio local com faster-whisper (CPU, pt-BR), substituindo Transcribe. Sentimento e termos críticos também processados localmente (léxico pt-BR / modelo leve em CPU).
- **Reason**: Transcribe indisponível no Learner Lab (AD-002); precisa de alternativa CPU-only.
- **Trade-off**: Sem elasticidade gerenciada da nuvem; qualidade depende do modelo local escolhido.
- **Scope**: F2 (audio-analysis).
- **Date**: 2026-07-20
- **Status**: active

### AD-004
- **Decision**: Papel da nuvem = serviços gerenciados de IA disponíveis + eventos + alerta: Textract para prescrições em PDF; Rekognition para keyframes de vídeo; S3 + Lambda (LabRole) + SNS para o fluxo event-driven de alerta; Step Functions (opcional) para orquestração visual do alerta.
- **Reason**: Mantém a exigência de "integração com serviços gerenciados em nuvem" do enunciado, respeitando a lista fechada (AD-002).
- **Trade-off**: Cloud é um complemento (evidência + alerta), não o motor de processamento pesado.
- **Scope**: F1, F4, F5.
- **Date**: 2026-07-20
- **Status**: active

### AD-005
- **Decision**: Local-first para modelos pesados — YOLOv8, MediaPipe, faster-whisper, librosa e detecção de anomalias rodam no notebook (CPU). Único compute na nuvem é Lambda.
- **Reason**: Evita custo/complexidade de infra de GPU/compute gerenciado no Learner Lab; simplifica reprodutibilidade.
- **Trade-off**: Processamento limitado à capacidade CPU do notebook do grupo.
- **Scope**: Todas as features (F1–F5).
- **Date**: 2026-07-20
- **Status**: active

### AD-006
- **Decision**: MediaPipe Pose no lugar de OpenPose para análise postural.
- **Reason**: Enunciado permite "modelos como OpenPose"; MediaPipe é mais leve para CPU e mais simples de integrar.
- **Trade-off**: Menor precisão que OpenPose em cenários complexos multi-pessoa, aceitável para o escopo da demo.
- **Scope**: F1 (video-analysis).
- **Date**: 2026-07-20
- **Status**: active

### AD-007
- **Decision**: Restrições operacionais do Learner Lab: região us-east-1; usar sempre a role `LabRole` existente (IAM restrito, não é possível criar roles); nunca deixar EC2/RDS/SageMaker rodando entre sessões; máx. 10 execuções concorrentes de Lambda; limite de 1000 detecções do Rekognition é suficiente para a demo.
- **Reason**: Estourar o budget ou violar restrições da conta acadêmica desativa a conta e apaga os recursos.
- **Trade-off**: Nenhuma automação de infraestrutura de longa duração; tudo deve ser recriável por script a cada sessão.
- **Scope**: Todas as features com componente AWS (F1, F4, F5); IaC do projeto.
- **Date**: 2026-07-20
- **Status**: active

### AD-008
- **Decision**: Estratégia "demo-first" — o roteiro do vídeo de 15 min define o escopo do projeto; cada cena do roteiro é um critério de aceite; nada fora do roteiro/relatório entra no escopo.
- **Reason**: Prazo curto (7 dias) e entregável final é o vídeo de demonstração + relatório técnico.
- **Trade-off**: Funcionalidades "legais de ter" mas fora do roteiro são explicitamente descartadas.
- **Scope**: Todas as features (F1–F5); critério de priorização geral do projeto.
- **Date**: 2026-07-20
- **Status**: active

### AD-009
- **Decision**: Usar apenas dados sintéticos e datasets públicos anonimizados — nenhum dado real de paciente. Sinais vitais via simulador sintético com anomalias injetadas (ground truth conhecido) + datasets PhysioNet.
- **Reason**: Projeto acadêmico, sem aprovação ética/LGPD para dados reais de pacientes.
- **Trade-off**: Resultados são demonstrativos, não validados clinicamente.
- **Scope**: F3 (vitals-anomaly), F4 (prescription-analysis, dados sintéticos), F1/F2 (vídeos/áudios gravados pelo próprio grupo).
- **Date**: 2026-07-20
- **Status**: superseded by AD-015

### AD-010
- **Decision**: Tematização em saúde materno-fetal (opcional-forte) usando a base CTU-UHB de cardiotocografia (PhysioNet) como um dos casos de sinais vitais.
- **Reason**: Conecta o projeto a uma linha de pesquisa em IA multimodal para saúde da mulher, além do simulador genérico.
- **Trade-off**: Complexidade adicional de parsing/format específico do CTU-UHB; tratado como caso de estudo extra, não substitui o simulador sintético principal.
- **Scope**: F3 (vitals-anomaly).
- **Date**: 2026-07-20
- **Status**: superseded by AD-016

### AD-011
- **Decision**: "Tempo real" implementado como near-real-time via micro-batch (janelas de segundos); simulador faz streaming local. Kinesis não é usado.
- **Reason**: Kinesis adiciona custo/complexidade desnecessários para o escopo da demo; micro-batch é suficiente para o comportamento esperado.
- **Trade-off**: Não há streaming verdadeiro de baixa latência; aceitável dado o objetivo de "identificação precoce", não de tempo real crítico.
- **Scope**: F3 (vitals-anomaly), F5 (fusion-and-alerting).
- **Date**: 2026-07-20
- **Status**: active

### AD-012
- **Decision**: Todo processamento roda em CPU (notebook Linux) — sem dependência de GPU.
- **Reason**: Ambiente do grupo não possui GPU disponível.
- **Trade-off**: Modelos/parâmetros escolhidos (YOLOv8, MediaPipe, faster-whisper) devem ser as variantes leves/CPU-friendly.
- **Scope**: Todas as features (F1–F5).
- **Date**: 2026-07-20
- **Status**: active

### AD-013
- **Decision**: CI via GitHub Actions restrito a lint e testes unitários; nenhum deploy automatizado para AWS.
- **Reason**: Credenciais do AWS Academy rotacionam por sessão, tornando deploy automatizado inviável/inseguro.
- **Trade-off**: Deploy dos recursos AWS é sempre manual/script local (boto3/CloudFormation) executado pelo usuário.
- **Scope**: Todas as features com componente AWS (F1, F4, F5); pipeline de CI do projeto.
- **Date**: 2026-07-20
- **Status**: active

### AD-014
- **Decision**: Infraestrutura AWS (bucket S3, tópico SNS, Lambdas, regras de evento) provisionada via CloudFormation simples ou script boto3 idempotente, recriável em qualquer sessão do lab.
- **Reason**: Recursos do Learner Lab não persistem de forma confiável entre sessões / credenciais rotacionam; precisa reprovisionar rapidamente.
- **Trade-off**: Sem configuração manual "na mão" no console — tudo deve estar versionado como código.
- **Scope**: F1, F4, F5; IaC do projeto.
- **Date**: 2026-07-20
- **Status**: active

### AD-015
- **Decision**: Priorizar datasets clínicos reais que já carregam rótulo/desfecho real; dado sintético fica restrito a (a) composição de timeline de demo concatenando registros reais (não fabricação) e (b) prescrições longitudinais em F4 (único ponto sem dataset aberto viável). Nenhum dado real identificável de paciente.
- **Reason**: Rótulo real (ex.: pH do cordão no CTU-UHB) produz métricas de precision/recall honestas, mais defensáveis no relatório técnico do que anomalia injetada artificialmente.
- **Trade-off**: Menos controle sobre a taxa/tipo de anomalia apresentada na demo; depende da distribuição real dos datasets escolhidos.
- **Scope**: Todas as features (F1–F5). Supersede AD-009.
- **Date**: 2026-07-20
- **Status**: active

### AD-016
- **Decision**: Datasets-âncora por feature, todos abertos e baixáveis sem credenciamento: CTU-UHB Intrapartum CTG (PhysioNet/Open Data Commons) para F3; ICBHI 2017 Respiratory Sound (bhichallenge.med.auth.gr) para F2; Cholec80-CVS / Endoscapes-CVS (GitHub, open) para F1; MIT-BIH Arrhythmia (PhysioNet, open) como segundo caso opcional de F3.
- **Reason**: Elimina o gargalo de credenciamento (CITI/DUA) do caminho crítico de 7 dias; todos disponíveis para download imediato.
- **Trade-off**: Escopo do projeto fica atrelado ao conteúdo/rótulos desses datasets específicos, não a dados customizados.
- **Scope**: F1, F2, F3. Supersede AD-010 (CTU-UHB deixa de ser "caso opcional" e passa a âncora primária de F3).
- **Date**: 2026-07-20
- **Status**: active

### AD-017
- **Decision**: Evitar datasets com credenciamento (MIMIC-III, MIMIC-IV, MIMIC-IV waveform, MIMIC-IV-Ext-BHC) — não entram no caminho crítico. Cholec80 original (formulário CAMMA) é substituído por Cholec80-CVS (open) a menos que o registro libere a tempo.
- **Reason**: Processo de CITI + DUA leva dias/semanas, com risco real de não liberar até o prazo de 27/07/2026.
- **Trade-off**: Abre mão de datasets potencialmente mais ricos (ex. MIMIC-IV) em favor de disponibilidade garantida.
- **Scope**: F1 (vídeo), F3/F4 (caso MIMIC fosse usado como alternativa futura).
- **Date**: 2026-07-20
- **Status**: active

### AD-018
- **Decision**: Descartar catálogos comerciais (Shaip) e datasets fora do escopo multimodal de monitoramento (1000 Genomes, CheXpert, HAM10000, SEER); SHands e MedMosaic descartados por acesso incerto.
- **Reason**: Não atendem ao domínio do desafio (monitoramento multimodal hospitalar) ou têm barreira de acesso não avaliável a tempo.
- **Trade-off**: Nenhum — eram candidatos de baixa aderência ao escopo.
- **Scope**: Triagem geral de datasets do projeto.
- **Date**: 2026-07-20
- **Status**: active

### AD-019
- **Decision**: F1 usa Cholec80-CVS (vídeo cirúrgico laparoscópico real, anotado) como entrada primária, com YOLOv8 para detecção de instrumentos/eventos fora da sequência de fases anotada. MediaPipe Pose NÃO se aplica a vídeo endoscópico; se o grupo quiser o ângulo postural/fisioterapia, grava um clipe próprio de corpo inteiro (atuação, não dado de paciente) — único vídeo "gravado pelo grupo" aceitável.
- **Reason**: Vídeo laparoscópico é endoscópico (sem corpo inteiro visível), incompatível com estimativa de pose; Cholec80-CVS dá anomalia real (desvio de fase) em vez de heurística sobre atuação.
- **Trade-off**: Abre mão do caso "queda/assimetria" via pose sobre dado real; se incluído, vem de um clipe encenado à parte.
- **Scope**: F1 (video-analysis).
- **Date**: 2026-07-20
- **Status**: active

### AD-020
- **Decision**: F2 usa ICBHI 2017 (sons respiratórios reais, anotados) como entrada primária para classificação de crackle/wheeze com rótulo real. Disartria real (datasets TORGO/UA-Speech) fica fora do caminho crítico; "fadiga/qualidade vocal" é coberta via features acústicas (jitter, shimmer, HNR) sobre áudio de consulta gravado pelo grupo (atuação, não paciente). Transcrição + termos críticos via faster-whisper sobre esse mesmo áudio.
- **Reason**: ICBHI dá métricas honestas de precision/recall com rótulo de especialista; disartria real exigiria dataset extra fora do prazo.
- **Trade-off**: Disartria vira "trabalho futuro" documentado no relatório, não uma capacidade demonstrada com dado rotulado real.
- **Scope**: F2 (audio-analysis).
- **Date**: 2026-07-20
- **Status**: active

### AD-021
- **Decision**: F3 usa CTU-UHB como âncora primária, com ground truth REAL via pH do cordão umbilical (pH < 7.05 ≈ acidose/sofrimento fetal) — sem injeção de anomalia. MIT-BIH Arrhythmia é caso secundário opcional. A timeline de demo é montada por um **compositor** que concatena registros reais (ex.: CTG normal → CTG patológico) para simular deterioração; o dado permanece 100% real, apenas a ordenação/composição é montada.
- **Reason**: Rótulo clínico real (pH) é mais defensível no relatório técnico do que anomalia sintética injetada; concatenar registros reais permite contar uma história de "deterioração" sem fabricar dado.
- **Trade-off**: Sem controle fino sobre o timing exato da anomalia (vem do registro real escolhido, não de um parâmetro ajustável); precisa normalizar taxa de amostragem entre registros concatenados.
- **Scope**: F3 (vitals-anomaly). Substitui a abordagem "simulador sintético" registrada em AD-009 (superseded).
- **Date**: 2026-07-20
- **Status**: active

### AD-022
- **Decision**: F4 é o único módulo do projeto com dado sintético assumido e justificado — prescrições longitudinais reais e abertas com anomalias rotuladas não existem sem credenciamento (MIMIC-IV). Bulas/dosagens reais são usadas como referência de faixa terapêutica (a regra clínica é real; o documento é sintético). Se alguém do grupo conseguir credenciamento MIMIC-IV a tempo, pode substituir pela tabela `prescriptions` real, mas isso não é caminho crítico.
- **Reason**: Não há alternativa aberta viável para este domínio dentro do prazo; ainda assim é valioso ter um PDF controlado para demonstrar o Textract de forma reprodutível.
- **Trade-off**: Resultados de F4 são demonstrativos, não validados contra caso real.
- **Scope**: F4 (prescription-analysis).
- **Date**: 2026-07-20
- **Status**: active

### AD-023
- **Decision**: F1 restrito à opção (a) de AD-019 — pipeline apenas sobre Cholec80-CVS (YOLOv8 local + Rekognition na nuvem). Sem MediaPipe Pose, sem clipe de corpo inteiro gravado pelo grupo.
- **Reason**: Mantém 100% dado real/aberto e reduz escopo de gravação própria do grupo; grupo optou pela alternativa recomendada no brief.
- **Trade-off**: Abre mão do ângulo "fisioterapia/queda" via pose estimation mencionado no enunciado original; coberto apenas pela análise cirúrgica (instrumentos/fases).
- **Scope**: F1 (video-analysis).
- **Date**: 2026-07-20
- **Status**: active

### AD-024
- **Decision**: A fusão (F5) usa um "paciente-demo" sintético que agrupa manualmente um registro real de cada modalidade (1 vídeo Cholec80-CVS de F1, 1 áudio ICBHI/gravado de F2, 1 registro CTU-UHB de F3, 1 histórico de prescrição de F4). A associação é curada, documentada no relatório técnico como composição didática — não representa um paciente real cruzando domínios.
- **Reason**: Os datasets reais usados em F1-F4 não compartilham identidade de paciente entre si (AD-016); é necessário um construto para viabilizar a "timeline unificada do paciente" e o risk score combinado pedidos pelo desafio.
- **Trade-off**: A fusão demonstra o mecanismo de combinação de sinais multimodais, mas não uma correlação clínica real entre os quatro sinais do mesmo indivíduo.
- **Scope**: F5 (fusion-and-alerting); consome saídas de F1, F2, F3, F4.
- **Date**: 2026-07-20
- **Status**: active

### AD-025
- **Decision**: Monorepo Python com pacote compartilhado `src/core/` (evidência, métricas, config, logging, cliente AWS) e um módulo por feature (`src/vitals/`, `src/audio/`, `src/video/`, `src/prescription/`, `src/fusion/`), mais `tests/`, `infra/` (CloudFormation/boto3) e um `Makefile` com alvo `demo`. `core/aws.py` é criado em F4 (F3 é 100% local), não em F3.
- **Reason**: Evita duplicar formato de evidência e relatório de métricas cinco vezes, e garante que F5 (fusão) consuma um formato único em vez de quatro formatos divergentes; Python é imposto por todas as bibliotecas já decididas (wfdb, scikit-learn, YOLOv8, librosa, faster-whisper, streamlit, boto3).
- **Trade-off**: Exige disciplina de organização desde a primeira feature e cria acoplamento entre features via `core/`; mudanças em `core/` afetam todas.
- **Scope**: Todas as features (F1–F5).
- **Date**: 2026-07-20
- **Status**: active

### AD-026
- **Decision**: Formato único de evidência para todo o projeto, definido em `src/core/evidence.py`: cada anomalia produz metadados estruturados + um artefato visual, gravados sob `output/[feature]/[run_id]/`. Toda feature (gráfico de janela em F3, espectrograma em F2, frame anotado em F1, PDF anotado em F4) usa esse mesmo contrato.
- **Reason**: Critério de aceite global exige que toda anomalia gere evidência reproduzível; um contrato único permite que o dashboard de F5 faça drill-down de qualquer modalidade sem tratar cada uma como caso especial.
- **Trade-off**: O contrato precisa ser genérico o bastante para quatro tipos de artefato bem diferentes, o que pode torná-lo menos expressivo para cada caso individual.
- **Scope**: Todas as features (F1–F5).
- **Date**: 2026-07-20
- **Status**: active

### AD-027
- **Decision**: Em F3, a regra de agregação janela → registro é "fração de janelas anômalas > τ" (default τ=0.15), com τ e limiares de detector calibrados em conjunto de desenvolvimento separado do conjunto de avaliação. Janelas marcadas `insufficient_data` são excluídas do denominador, nunca contadas como normais.
- **Reason**: O rótulo (pH) é por registro e os detectores operam por janela; a regra de agregação determina inteiramente as métricas. A alternativa "qualquer janela anômala ⇒ registro patológico" não discrimina (recall ≈ 1.0, precision ≈ prevalência) em séries de ~21.600 amostras.
- **Trade-off**: Introduz um hiperparâmetro adicional (τ) que precisa ser calibrado e justificado no relatório.
- **Scope**: F3 (vitals-anomaly); o padrão de calibração dev/avaliação separada aplica-se também a F1 e F2, que reportam métricas contra rótulo real.
- **Date**: 2026-07-20
- **Status**: active

### AD-028
- **Decision**: VITALS-11 AC2 ("o MIT-BIH produz anomalias e evidências no mesmo formato do CTU-UHB") sai do escopo de F3. O módulo `src/vitals/mitbih.py` permanece como **leitor de dados**: carrega ECG e anotações de arritmia e expõe o rótulo real, mas não é integrado ao pipeline de detecção nem gera evidência no formato AD-026.
- **Reason**: A verificação independente constatou que o AC não foi entregue — o módulo estava desconectado do pipeline. Integrá-lo de verdade exigiria repensar janelamento e features para ECG a 360 Hz com anotação por batimento, um domínio bem diferente de CTG a 4 Hz; é trabalho real, não ajuste, e o brief marca P3 como explicitamente opcional com prazo em 27/07/2026.
- **Trade-off**: F3 entrega um único caso de série vital integrado (CTU-UHB). O MIT-BIH fica disponível como leitor para uso no relatório ou trabalho futuro, sem sustentar a alegação de "segundo caso detectado e evidenciado".
- **Scope**: F3 (vitals-anomaly), user story P3. Rebaixa VITALS-11 AC2; AC1 e AC3 permanecem válidos.
- **Date**: 2026-07-20
- **Status**: active

## Handoff

- **Feature**: F3 vitals-anomaly (`.specs/features/vitals-anomaly/`)
- **Phase / Task**: Execute COMPLETO — 18/18 tarefas implementadas, testadas e commitadas na branch `feat/f3-vitals-anomaly`. Verificação independente (Verifier) em andamento.
- **Completed**: AD-001 a AD-027; specs das 5 features confirmadas; design e tasks de F3 aprovados; T1–T18 commitados individualmente (um commit atômico por tarefa). Suíte: 135 testes passando (129 unitários + 6 de integração), lint limpo.
- **In-progress**: Verifier independente re-derivando cobertura dos ACs e rodando sensor de mutação; escreverá `.specs/features/vitals-anomaly/validation.md`
- **Next step**: ler o veredito do Verifier; se FAIL, rotear lacunas como tarefas de correção (loop limitado a 3 iterações). Se PASS, F3 está encerrada e a próxima feature do plano de 7 dias é F4 (prescription-analysis), que precisa de Design + Tasks antes de Execute.
- **Blockers**: none. Ambiente resolvido — `.venv` na raiz com pytest, ruff, numpy, scikit-learn, wfdb 4.3.1, matplotlib e pyyaml. `make demo` exige o CTU-UHB baixado em `data/ctu-uhb-ctgdb/` (ainda não baixado); sem ele o comando falha com mensagem acionável, e os testes rodam com fixtures WFDB sintéticas.
- **Uncommitted files**: `.specs/` (design, tasks e STATE atualizados durante o Execute)
- **Branch**: `feat/f3-vitals-anomaly` (partiu de `main`; `main` tem apenas o commit inicial de planejamento)

### Achados verificados durante o Execute (não presumir de novo)

- `wfdb.rdrecord()` expõe `p_signal`, `sig_name`, `fs`, `comments`, `sig_len`, `record_name` (wfdb 4.3.1).
- **O wfdb remove o `#` das linhas de comentário**: o campo do `.hea` chega como `'pH           7.26'`. Presumir o `#` faria a regex nunca casar e descartaria 100% dos registros silenciosamente.
- CTU-UHB: 552 registros, 4 Hz uniforme, sinais `FHR` e `UC`; desfechos `pH`, `BDecf`, `BE`, `pCO2`, `Apgar1`, `Apgar5` no header.
- `pythonpath` do pytest não vale para `python -m`: o alvo `demo` do Makefile precisa de `PYTHONPATH=src`.
