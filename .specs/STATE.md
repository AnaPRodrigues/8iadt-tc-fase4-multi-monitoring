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
- **Status**: superseded by AD-033

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
- **Status**: superseded by AD-033

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
- **Status**: superseded by AD-029

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

### AD-029
- **Decision**: Monorepo com separação front/back. `backend/` = Python (FastAPI expondo REST; pipelines F1–F4; motor de fusão/score em `backend/fusion/`; integração AWS via boto3 e handlers de Lambda em `backend/aws/`; scripts de dados). `frontend/` = app separado que apenas **consome a API** (dashboard de timeline do paciente, replay do cenário de demo, visualização de evidências), sem nenhuma lógica de processamento. Contrato: API REST versionada com, no mínimo, `/patients/{id}/timeline`, `/analyze`, `/alerts`, `/evidence/{id}`.
- **Reason**: Separa apresentação de processamento; permite demonstrar o fluxo multimodal por uma API real (mais defensável no relatório/vídeo que um script monolítico) e um dashboard desacoplado. Substitui a estrutura `src/core` + módulo por feature da AD-025, que não previa front/back nem API.
- **Trade-off**: Mais superfície (API + contrato + app de frontend) para manter num prazo de 7 dias; exige disciplina de contrato entre as duas metades.
- **Scope**: Todas as features (F1–F5) e a estrutura do repositório. **Supersede AD-025.**
- **Date**: 2026-07-20
- **Status**: active

### AD-030
- **Decision**: Estrutura do repositório: `backend/app/` (FastAPI: rotas, schemas, main), `backend/pipelines/{video,audio,vitals,prescription}/`, `backend/fusion/`, `backend/aws/`, `backend/scripts/` (inclui `download_datasets`), `backend/tests/`, `frontend/`, `data/` (gitignored, populado por F0), `infra/` (CloudFormation ou boto3 idempotente). Código compartilhado entre pipelines (formato de evidência, métricas, config, logging — o antigo `src/core/`) passa a viver em `backend/common/`. Adiciona-se `.gitignore` (com `data/`, venvs, artefatos), `data/README.md` e um `Makefile` de raiz com alvos `data`, `demo`, `test`, `lint`.
- **Reason**: Concretiza a AD-029 em uma árvore de diretórios explícita; `backend/common/` é proposto como lar do código transversal por não ser específico do FastAPI (é usado também pelos pipelines e handlers de Lambda) — **item a confirmar com o usuário na revisão do esqueleto**.
- **Trade-off**: `backend/common/` é um nome escolhido pelo agente, não presente no brief; se o grupo preferir outro (`backend/app/core/`, `backend/shared/`), ajusta-se antes da migração.
- **Scope**: Estrutura do repositório; todas as features.
- **Date**: 2026-07-20
- **Status**: active

### AD-031
- **Decision**: Aquisição de dados por script idempotente (feature F0), nada de download manual. `backend/scripts/download_datasets` baixa só as fontes sem barreira: CTU-UHB via `wfdb.dl_database('ctu-uhb-ctgdb', ...)`; ICBHI 2017 via `wget --continue` do zip oficial (URL como variável no topo, **a confirmar com o usuário**) + `unzip`; Cholec80-CVS via `git clone` do repositório aberto no GitHub (**nome do repo a confirmar**), buscando via Git LFS só os poucos vídeos da demo. Requisitos: idempotência ("já existe? pula"), retomada de download, checagem de espaço, URLs/paths como variáveis no topo. `data/` no `.gitignore`; versiona-se só o script + `data/README.md`. `make data` reproduz tudo.
- **Reason**: Reprodutibilidade é critério de aceite global; o professor/avaliador precisa recriar os dados com um comando. Datasets grandes não entram no Git.
- **Trade-off**: Depende de URLs/repos externos estáveis; duas fontes (ICBHI, Cholec80) têm identificador ainda não confirmado.
- **Scope**: F0 (data-acquisition); pré-requisito de F1, F2, F3.
- **Date**: 2026-07-20
- **Status**: active

### AD-032
- **Decision**: A F3 (vitals-anomaly), já implementada e testada em `src/core/` + `src/vitals/` na branch `feat/f3-vitals-anomaly` (165 testes), é **migrada** para a nova estrutura: `src/core/` → `backend/common/` e `src/vitals/` → `backend/pipelines/vitals/`, com os testes correspondentes movidos para `backend/tests/`, preservando o histórico git (`git mv`) e mantendo os 165 testes verdes. Os caminhos citados na AD-026 (`src/core/evidence.py`) e na AD-028 (`src/vitals/mitbih.py`) atualizam-se para os novos locais. A migração é a **primeira etapa de execução após aprovação** — nenhum código é movido antes disso.
- **Reason**: O usuário escolheu preservar e migrar em vez de recomeçar; descartar uma feature pronta e verificada seria retrabalho dentro do prazo de 27/07.
- **Trade-off**: Commits antigos referenciam AD-025 (agora superseded) e caminhos `src/…` que deixam de existir; a rastreabilidade fica no histórico git e nesta AD.
- **Scope**: F3 (vitals-anomaly); estrutura do repositório.
- **Date**: 2026-07-20
- **Status**: active

### AD-033
- **Decision**: A âncora de vídeo/frames da F1 passa a ser o **Endoscapes2023** (CAMMA), não o Cholec80-CVS. Motivo factual verificado: o Cholec80-CVS aberto (figshare 22183885) é só um `.xlsx` de 24 KB de anotações CVS — os vídeos brutos do Cholec80 exigem formulário CAMMA (barreira que AD-016/AD-017 evitam). O Endoscapes2023 é baixável por URL direta sem formulário (`https://s3.unistra.fr/camma_public/datasets/endoscapes/endoscapes.zip`, ~6 GB, licença aberta) e contém frames cirúrgicos reais anotados: **Endoscapes-BBox201** (1933 frames, bounding boxes COCO de 5 estruturas anatômicas + 1 classe de instrumento) e **Endoscapes-CVS201** (11090 frames com rótulo de CVS). A F1 é **reescopada**: de "detecção de desvio na sequência de fases de vídeo" para **detecção de objetos/instrumentos/anatomia (YOLOv8) sobre os frames anotados com bbox COCO do Endoscapes-BBox201 + avaliação de CVS**. Rekognition sobre keyframes na nuvem permanece. O repo `github.com/ManuelRios18/CHOLEC80-CVS-PUBLIC` (COLENET) é código baseline, não fonte de dado — pode ser citado no relatório.
- **Reason**: YOLOv8 precisa de frames/vídeo reais; o único caminho aberto sem credenciamento com rótulo real de detecção é o Endoscapes-BBox201 (bounding boxes COCO encaixam direto no YOLOv8 e dão precision/recall honesto). Mantém o caso cirúrgico e o tema de segurança (CVS).
- **Trade-off**: Endoscapes são frames amostrados em intervalos, não vídeo contínuo — perde-se o ângulo "sequência temporal de fases". Download de ~6 GB exige a checagem de espaço já prevista em F0 (DATA-08).
- **Scope**: F1 (video-analysis) e F0/DATA-03. **Supersede a parte Cholec80-CVS das AD-016, AD-019 e AD-023** (AD-016 permanece válida para CTU-UHB, ICBHI e MIT-BIH).
- **Date**: 2026-07-20
- **Status**: active (reafirmada por AD-036 — Endoscapes segue como âncora de F1)

### AD-034
- **Decision**: Todo acesso a serviços AWS passa por **dois profiles selecionados pela variável `ENV`** (`local` | `cloud`). `local` → **LocalStack** (endpoint `http://localhost:4566`, credenciais dummy `test/test`), para dev e testes 100% offline sem gastar budget nem lidar com credenciais rotativas do lab; `cloud` → AWS real do Learner Lab (credenciais temporárias, sem `endpoint_url`). Implementação obrigatória: um **factory único de cliente boto3** (`backend/aws/clients.py`) que injeta `endpoint_url` só quando `ENV=local`. **NUNCA** instanciar `boto3.client(...)` direto nos pipelines — sempre via o factory. Config por `.env.local`/`.env.cloud` (+ `.env.example`); `docker-compose.yml` sobe o LocalStack; a IaC de `infra/` provisiona os MESMOS recursos nos dois ambientes (só muda o endpoint).
- **Reason**: Permite desenvolver e testar todo o fluxo event-driven (S3/Lambda/SNS/DynamoDB) sem sessão AWS ativa, sem gastar o budget do Learner Lab e sem depender das credenciais que rotacionam por sessão. Um factory único garante que trocar de ambiente seja só mudar `ENV`.
- **Trade-off**: Exige rodar LocalStack (Docker) localmente e manter a IaC agnóstica de endpoint; LocalStack Community não cobre todos os serviços (ver AD-035).
- **Scope**: Todas as features com AWS (F1, F4, F5); `backend/aws/`, `infra/`, `docker-compose.yml`.
- **Date**: 2026-07-21
- **Status**: active

### AD-035
- **Decision**: Textract e Rekognition **não existem no LocalStack Community** (são Pro). Resolver com padrão **ADAPTER**: interfaces únicas `TextExtractor` e `ImageAnalyzer` em `backend/aws/adapters/`, cada uma com dois adaptadores — **cloud** (Textract / Rekognition reais) e **local** (OSS: Tesseract/pdfplumber para OCR de prescrição em F4; YOLOv8 local para labels de imagem em F1). O resto do pipeline depende só da interface, nunca do serviço concreto.
- **Reason**: Sem isso, o profile `local` (AD-034) não conseguiria exercitar F4/F1 offline. O adapter isola a dependência do serviço gerenciado num único ponto.
- **Trade-off**: Os resultados dos adaptadores local e cloud diferem (Tesseract ≠ Textract); o relatório precisa deixar claro qual ambiente gerou cada métrica.
- **Scope**: F4 (TextExtractor), F1 (ImageAnalyzer); `backend/aws/adapters/`.
- **Date**: 2026-07-21
- **Status**: active

### AD-036
- **Decision**: F1 usa **apenas datasets abertos** já discutidos (e eventualmente outros abertos encontrados no futuro) — **sem nenhuma gravação de vídeo pelo próprio grupo**. A âncora de vídeo/frames **permanece o Endoscapes2023** (AD-033, já baixado em `data/endoscapes/`): YOLOv8 sobre os frames anotados (bbox COCO) + `ImageAnalyzer` na nuvem para keyframes (AD-035). O **MediaPipe Pose** fica **condicionado** a encontrar um dataset **aberto** de vídeo de corpo inteiro (nenhum identificado até agora); sem essa fonte, o ângulo postura/queda **não entra no caminho crítico**. O **Cholec80-CVS** (anotações XLSX, sem vídeo) segue como enriquecimento opcional.
- **Reason**: O usuário optou por não gravar vídeo próprio e usar só dados abertos. Entre os datasets discutidos, o único com frames reais e acesso aberto é o Endoscapes2023 — por isso ele volta a ser a âncora, e o Endoscapes baixado deixa de estar órfão.
- **Trade-off**: Sem fonte aberta de vídeo de corpo inteiro, o MediaPipe Pose (AD-006) fica sem uso imediato e o caso "fisioterapia/queda" do enunciado vira contingente a um dataset futuro. F1 no caminho crítico é detecção sobre frames cirúrgicos (Endoscapes), não análise postural.
- **Scope**: F1 (video-analysis). **Reafirma a AD-033** (não a supersede); torna a aplicação de MediaPipe (AD-006) condicional a uma fonte aberta futura.
- **Date**: 2026-07-21
- **Status**: superseded by AD-039

### AD-037
- **Decision**: A estrutura de `backend/aws/` é: `clients.py` (factory de cliente boto3 por `ENV`, AD-034), `adapters/` (`TextExtractor`/`ImageAnalyzer` cloud+local, AD-035), `lambdas/` (handlers de Lambda). Acrescenta-se `docker-compose.yml` (sobe LocalStack), `.env.local`/`.env.cloud`/`.env.example`, e alvos no `Makefile`: `localstack-up`/`localstack-down` (docker-compose) e `infra-local`/`infra-cloud` (mesma IaC nos dois ambientes, só muda o endpoint). `.env.local` e `.env.cloud` entram no `.gitignore`; só `.env.example` é versionado. Refina a AD-030.
- **Reason**: Concretiza AD-034/AD-035 em arquivos e comandos; mantém segredos/endpoints fora do Git e o mesmo IaC recriável nos dois ambientes.
- **Trade-off**: Mais superfície de configuração (dois `.env`, docker-compose, quatro alvos novos de Make).
- **Scope**: `backend/aws/`, `infra/`, raiz do repo. Refina AD-030.
- **Date**: 2026-07-21
- **Status**: active

### AD-038
- **Decision**: A fundação AWS (factory de cliente boto3 por `ENV`, adapters `TextExtractor`/`ImageAnalyzer`, IaC idempotente que provisiona os recursos nos dois ambientes) é uma **feature dedicada `aws-foundation`**, construída **antes** de F4/F1/F5, que passam a depender dela. Os **testes de integração usam LocalStack real** (Docker), conforme escolha do usuário — não moto. Docker é pré-requisito do Execute desta feature.
- **Reason**: A infra AWS é compartilhada por três features; isolá-la numa fatia fechada e verificável evita acoplá-la à lógica de prescrição (F4) e ter que extraí-la depois para F1/F5. LocalStack real dá fidelidade ao ambiente-alvo.
- **Trade-off**: Adiciona uma feature ao caminho antes de entregar valor de F4; e o Execute fica bloqueado por Docker (instalação de sistema, sudo).
- **Scope**: nova feature `aws-foundation`; pré-requisito de F4, F1, F5.
- **Date**: 2026-07-21
- **Status**: active

### AD-039
- **Decision**: A raia de **pose/movimento** de F1 usa o **UR Fall Detection Dataset (URFD)** — dado real aberto, sem credenciamento e sem gravação do grupo. Fonte: `https://fenix.ur.edu.pl/~mkepski/ds/uf.html`; zips por sequência em `https://fenix.ur.edu.pl/~mkepski/ds/data/<seq>-cam0-rgb.zip` (verificado: HTTP 206, `application/zip`, magic `PK`). Conteúdo: 70 sequências (30 quedas + 40 ADL), RGB corpo inteiro 640×480 em PNG + acelerômetro. **MediaPipe Pose** extrai keypoints por frame → assimetria, amplitude, velocidade, detecção de queda (variação brusca do centro de massa); classificação **queda vs ADL** com métricas precision/recall contra o rótulo real. Isso **fecha o Requisito 1 (análise postural)** e o **Requisito 3 (padrões de movimentação do paciente)**. F1 passa a ter **duas raias**: pose (URFD + MediaPipe) e objeto/área crítica (Endoscapes/Cholec80 + YOLOv8/`ImageAnalyzer`). **Supersede a AD-036** (MediaPipe deixa de ser condicional — URFD é a fonte).
- **Reason**: URFD é a fonte aberta que faltava para habilitar MediaPipe sem gravação do grupo e com rótulo real (fall/ADL), cobrindo dois requisitos obrigatórios que estavam sem fonte.
- **Trade-off**: URFD são sequências de PNG por câmera (não vídeo contínuo nem clínico) e ~70 zips a baixar; o cenário é queda/ADL genérico, não fisioterapia clínica — mas atende "análise postural" e "padrões de movimentação". AD-006 (MediaPipe) volta a ser incondicional.
- **Scope**: F1 (video-analysis), raia pose; F0 (nova fonte). Supersede AD-036; reafirma AD-033 para a raia objeto.
- **Date**: 2026-07-21
- **Status**: active

### AD-040
- **Decision**: F3 ganha um **segundo caso de sinais vitais** com o **BIDMC PPG and Respiration Dataset** — aberto, sem credenciamento (subconjunto liberado do MIMIC-II matched, SEM a barreira do MIMIC). Fonte: `https://physionet.org/content/bidmc/1.0.0/` (verificado: página HTTP 200); baixável via `wfdb.dl_database('bidmc', 'data/bidmc')`. Conteúdo: 53 gravações de 8 min de UTI adulto; numéricos a 1 Hz — **HR, PULSE, RESP, SpO2** — + ECG e PPG a 125 Hz. Cobre **"batimentos" (HR)** e **"oxigenação" (SpO2)** com sinal real de internação. CTU-UHB permanece como caso materno-fetal (FHR + contração). **Pressão arterial (PA)** fica documentada como **trabalho futuro** (PA em waveform aberto praticamente só no MIMIC credenciado). **MIT-BIH (AD-028) permanece descopado** — BIDMC já entrega HR derivado de ECG, tornando-o redundante.
- **Reason**: Fecha o gap parcial de sinais vitais (o enunciado exemplifica batimento/PA/SpO2; F3 só tinha FHR fetal). BIDMC dá HR e SpO2 reais de internação sem credenciamento.
- **Trade-off**: PA continua descoberta (aceito como trabalho futuro); F3 passa a lidar com dois formatos/domínios de série (CTG materno-fetal e UTI adulto).
- **Scope**: F3 (vitals-anomaly), segundo caso; F0 (nova fonte). Complementa AD-021; mantém AD-028 (MIT-BIH descopado).
- **Date**: 2026-07-21
- **Status**: active

### AD-041
- **Decision**: A **pressão arterial (PA)** permanece **fora do caminho crítico** — documentada como desenvolvimento futuro no relatório técnico, não bloqueadora (é exemplo do enunciado, não item-lista obrigatório estrito; nenhum requisito obrigatório depende dela). Fonte identificada para fechá-la quando houver tempo: **VitalDB** (`vitaldb.net`; também no PhysioNet, DOI `10.13026/czw8-9p62`) — aberto após cadastro + data usage agreement, **sem credenciamento CITI**. Contém pressão arterial invasiva (ABP) real + ECG, PPG, SpO2 de ~6.388 casos cirúrgicos/anestésicos; biblioteca Python própria (`vitaldb`) + API. **Condição de execução**: só entra depois do MVP fechado (F1, F2, F4, F5, aws-foundation e frontend construídos, vídeo/relatório encaminhados) — enriquecimento, não bloqueador. **Não adicionar ao F0 (`download_datasets`) agora**; se/quando priorizado, acrescentar `fetch_vitaldb` usando a lib `vitaldb` (confirmar o loader exato na doc antes de implementar — formato próprio `.vital`, não reaproveita os loaders `wfdb` de F3, terceiro domínio de série vital além do materno-fetal/CTU-UHB e UTI/BIDMC).
- **Reason**: Fecha a lacuna de "fonte aberta identificada" para PA sem comprometer o prazo — formaliza o caminho de fechamento sem puxá-lo para o caminho crítico.
- **Trade-off**: PA segue sem implementação nesta entrega; VitalDB é código novo (formato `.vital` próprio), não um ajuste incremental de F3.
- **Scope**: F3 (vitals-anomaly), trabalho futuro; não altera F0/F1/F2/F4/F5 nem o caminho crítico. Refina a nota de AD-040 sobre PA.
- **Date**: 2026-07-21
- **Status**: active

## Rastreabilidade de Requisitos Obrigatórios

Mapeamento dos requisitos do enunciado (`docs/8IADT-Fase-4-Tech-challenge.md`) às features.

| Requisito do enunciado | Feature / cobertura | Status |
| --- | --- | --- |
| Req.1 — Vídeo: análise postural (OpenPose/pose) | F1 raia pose: URFD + MediaPipe Pose (AD-039) | ✅ Coberto |
| Req.1 — Vídeo: detecção de objeto/área crítica (YOLOv8) | F1 raia objeto: Endoscapes/Cholec80 + YOLOv8/Rekognition (AD-033/035) | ✅ Coberto |
| Req.1 — Vídeo: relatórios automáticos de desvios | F1 (saída: JSON de eventos + frames anotados + relatório) | ✅ Planejado |
| Req.2 — Áudio: alterações vocais (cansaço, dif. respiratória) | F2: ICBHI (crackle/wheeze) + jitter/shimmer/HNR (AD-020) | ✅ Planejado |
| Req.2 — Áudio: transcrição (Azure STT → faster-whisper) | F2 (AD-003) | ✅ Substituído |
| Req.2 — Áudio: termos críticos + sentimento (Text Analytics → local) | F2 (AD-003) | ✅ Substituído |
| Req.2 — Áudio: disartria | Trabalho futuro (sem dataset aberto rotulado, AD-020) | ⚠️ Deferido |
| Req.3 — Vitais: batimentos (HR) | F3 caso UTI: BIDMC (AD-040) + FHR do CTU-UHB | ✅ Coberto |
| Req.3 — Vitais: oxigenação (SpO2) | F3 caso UTI: BIDMC (AD-040) | ✅ Coberto |
| Req.3 — Vitais: pressão arterial (PA) | Trabalho futuro — fonte aberta identificada: VitalDB (AD-041) | ⚠️ Deferido |
| Req.3 — Prescrições: evolução | F4: Textract/adapter + regras — **FECHADO, Verifier PASS** (AD-022/035) | ✅ Coberto |
| Req.3 — Padrões de movimentação do paciente | F1 raia pose: URFD fall/ADL (AD-039) | ✅ Coberto |
| Req.3 — Alertas automáticos à equipe | F5: Lambda → SNS (AD-004/024) | ✅ Planejado |
| Objetivo — Fusão multimodal | F5: late fusion + risk score (AD-024) | ✅ Planejado |
| Objetivo — Nuvem gerenciada (Azure → AWS) | AWS Learner Lab + LocalStack (AD-001/034); **explicar a troca no relatório/vídeo** | ✅ Substituído |
| Objetivo — Tempo real | Near-real-time por micro-batch (AD-011) | ✅ Substituído |
| Entregável — Relatório técnico | Pendente (escrever ao final) | ⏳ Pendente |
| Entregável — Vídeo demo ≤15 min | Pendente (gravar ao final) | ⏳ Pendente |

Lacunas obrigatórias remanescentes: **nenhuma** (PA e disartria são deferidas com justificativa, não requisitos-lista obrigatórios estritos). Entregáveis (relatório + vídeo) pendentes por natureza (fase final).

## Handoff

- **Feature**: **F1 (video-analysis) EM ANDAMENTO** — Batch 1 (T1-T7) do `tasks.md` **concluído** nesta sessão. Batch 2 (T8-T13) é o próximo passo, ainda não iniciado.
- **Phase / Task**: Batch 1 **completo** (T1 a T7, todas commitadas, gate verde + ruff limpo em cada uma). Próxima tarefa é **T8** (`object_detector.py`), início do Batch 2.
- **Completed (Batch 1, T1-T7)**:
  - T1 `pose_loader.py` + `models.py` (`Sequence`/`PoseFrame`/`MovementWindow`/`SequenceVerdict`) — commit `c49be7f`.
  - T2 `pose.py` (`ensure_pose_model`/`create_landmarker`/`extract_keypoints`, Task API real + download real do modelo) — commit `de572fe`.
  - T3 `pose_features.py` (`windowed_features`: centro de massa via landmarks 23/24, amplitude/velocidade/assimetria) — commit `7c72a56`.
  - T4 `pose_detector.py` (`classify_sequence` + `draw_keypoints`/`save_fall_evidence`) — commit `5f30611`.
  - T5 `pose_evaluate.py` (`evaluate`, reaproveita `common.metrics.binary_metrics`) — commit `43be52f`.
  - T6 `object_loader.py` + `models.py` ganhou `BoundingBox`/`AnnotatedFrame` (`load_annotated_frames` contra o COCO real do Endoscapes) — commit `c4eeed9`.
  - T7 `object_finetune.py` (`ensure_base_weights`/`finetune`: converte COCO→YOLO via `ultralytics.data.converter.convert_coco` isolando o JSON num diretório próprio — o diretório real do Endoscapes tem 3 JSONs de anotação, glob pegaria os 3 — e roda fine-tuning real do YOLOv8n com `project=`/`name=` explícitos e peso base em cache absoluto dentro de `output_dir`, nunca o cwd) — commit `0a09db4`. Teste extra que compara `os.listdir(repo_root)` antes/depois confirma, na própria suíte, que nada polui a raiz do repo (não só inspeção manual).
  - Testes: 277 passando (`pytest -q -m "not integration"`), 0 falhas; `ruff check backend/` limpo em cada commit.
- **In-progress**: nada em código não commitado. Working tree limpa.
- **Next step**: iniciar o **Batch 2 (T8-T13)** seguindo `tasks.md` a partir de T8 (`object_detector.py` — `YoloDetector.detect` com os pesos fine-tuned de T7 + evidência de estrutura crítica via `common.evidence`). Depende de T6+T7 (ambas prontas). Depois de T8: T9 (`object_evaluate.py`), T10 (`adapters.py`/`YoloImageAnalyzer`), e o restante do Batch 2 (T11-T13, incluindo o relatório consolidado das duas raias). Ao final do Batch 2, rodar o **Verifier independente** de F1 (author ≠ verifier, nunca rodado ainda para esta feature).
- **Blockers**: none. Rede disponível e testada (download real do modelo MediaPipe, do peso base YOLOv8n e leitura do dataset Endoscapes já confirmados nesta sessão).
- **Residual aceito em aws-foundation**: 2 mutantes sobreviventes (dívida de teste, não bugs) — teste de variável ausente em `main()` passa por acidente (comportamento de produção correto, só o teste não discrimina o mecanismo); paginação de `ensure_topic` nunca forçada por teste (risco latente que cresce com o nº de tópicos no Learner Lab ao longo do tempo — não bloqueador agora). 3 follow-ups de baixa prioridade registrados em `validation.md`, não agendados.
- **Ambiente**: grupo `docker` do usuário exige `sg docker -c '...'` até um logout/login completo aplicar a mudança de verdade. Ativar `.venv` (`source .venv/bin/activate`) antes de `pytest`/`ruff`/`python`; `PYTHONPATH=backend` necessário fora do pytest.
- **Residual aceito na emenda F0**: 3 mutantes sobreviventes (não bloqueadores) — dupla chamada do BIDMC não verificável pelo harness de stub (limitação de teste, não do código); URFD sem teste de zip corrompido (paridade com lacuna já aceita no núcleo para ICBHI); overlap teórico de glob no BIDMC (`*.hea` vs `*n.hea`), não alcançável no fluxo sequencial atual.
- **Fontes verificadas (não re-checar)**: URFD zips em `https://fenix.ur.edu.pl/~mkepski/ds/data/{fall,adl}-NN-cam0-rgb.zip` (fall 01–30, adl 01–40) — HTTP 206, `application/zip`, magic `PK`. BIDMC via `wfdb.dl_database('bidmc', ...)` — 53 registros contíguos `bidmc01`..`bidmc53` confirmados via `get_record_list`; numerics = mesmo nome + sufixo `n`, fora do `RECORDS`.
- **Residual aceito em F0 (núcleo)**: 4 mutantes sobreviventes pré-existentes (dívida de teste P2, não bugs) — ver validation.md.
- **Uncommitted files**: nenhum (tudo commitado, working tree limpa) — parada segura confirmada via `git status` antes de encerrar.
- **Branch**: `feat/f3-vitals-anomaly` (contém F3 + reestruturação + F0 completa + aws-foundation + F4 completa + F1 Batch 1 completo T1-T7; `main` só tem o commit inicial — estratégia de merge/rename a decidir).
- **Aberto (decisões futuras)**: estratégia de branch/merge para `main`; framework do `frontend/`; DATA-12 (checksum) diferido P3; Batch 2 de F1 (T8-T13) e Verifier de F1 ainda não rodados.

### Achados verificados durante o Execute (não presumir de novo)

- `wfdb.rdrecord()` expõe `p_signal`, `sig_name`, `fs`, `comments`, `sig_len`, `record_name` (wfdb 4.3.1).
- **O wfdb remove o `#` das linhas de comentário**: o campo do `.hea` chega como `'pH           7.26'`. Presumir o `#` faria a regex nunca casar e descartaria 100% dos registros silenciosamente.
- CTU-UHB: 552 registros, 4 Hz uniforme, sinais `FHR` e `UC`; desfechos `pH`, `BDecf`, `BE`, `pCO2`, `Apgar1`, `Apgar5` no header.
- `pythonpath` do pytest não vale para `python -m`: o alvo `demo` do Makefile usa `PYTHONPATH=backend` (após a migração).
- ICBHI: a URL `bhichallenge.med.auth.gr` tem cert SSL autoassinado E retorna HTTP 403 no site inteiro — usar Harvard Dataverse (DOI 10.7910/DVN/HT6PKI, datafile 7127117, ~1.9 GB). Cholec80-CVS aberto (figshare 22183885) é só um xlsx de anotações; vídeo exige CAMMA → âncora de vídeo é o Endoscapes2023 (`s3.unistra.fr/camma_public/datasets/endoscapes/endoscapes.zip`, ~6 GB, aberto).
- F0 é testado com pytest dando `source` no script shell e dublando `curl`/`wget`/`python` no PATH; harness (`run`/`stubbin`) fica em `backend/tests/conftest.py` (um só conftest, para não colidir com `from conftest import`).
- **MediaPipe 0.10.35 não tem mais `mp.solutions.pose`** — só a Task API (`mediapipe.tasks.python.vision.PoseLandmarker` + `mediapipe.tasks.python.BaseOptions`). Modelo `.task` baixado sob demanda de `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task` (~5.7MB, testado real nesta sessão, idempotente via `ensure_pose_model`).
- URFD real: `data/urfd/<fall-NN|adl-NN>/<mesmo-nome>-cam0-rgb/<mesmo-nome>-cam0-rgb-NNN.png` (numeração zero-padded — não expõe o bug alfabético-vs-numérico sozinha; testado explicitamente com nomes sem padding em teste sintético). `fall-01` tem 160 frames.
- Endoscapes real (`data/endoscapes/endoscapes/train/annotation_coco.json`): 1212 imagens no COCO, 5566 anotações, 6 categorias (`cystic_plate`, `calot_triangle`, `cystic_artery`, `cystic_duct`, `gallbladder`, `tool`), `bbox` no formato COCO `[x, y, width, height]`. 26 imagens do JSON não têm nenhuma anotação (frame legitimamente sem estrutura). Diretório `train/` tem 36694 `.jpg` no total (COCO só referencia o subconjunto anotado/keyframes).
- Modelo de dataclasses da F1 fica centralizado em `pipelines/video/models.py` (T1 criou `Sequence`/`PoseFrame`/`MovementWindow`/`SequenceVerdict`; T6 estendeu com `BoundingBox`/`AnnotatedFrame` — `Detection` fica para T8/Batch 2, quando `object_detector.py` for implementado).
