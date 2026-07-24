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
- **Status**: superseded by AD-048

### AD-035
- **Decision**: Textract e Rekognition **não existem no LocalStack Community** (são Pro). Resolver com padrão **ADAPTER**: interfaces únicas `TextExtractor` e `ImageAnalyzer` em `backend/aws/adapters/`, cada uma com dois adaptadores — **cloud** (Textract / Rekognition reais) e **local** (OSS: Tesseract/pdfplumber para OCR de prescrição em F4; YOLOv8 local para labels de imagem em F1). O resto do pipeline depende só da interface, nunca do serviço concreto.
- **Reason**: Sem isso, o profile `local` (AD-034) não conseguiria exercitar F4/F1 offline. O adapter isola a dependência do serviço gerenciado num único ponto.
- **Trade-off**: Os resultados dos adaptadores local e cloud diferem (Tesseract ≠ Textract); o relatório precisa deixar claro qual ambiente gerou cada métrica.
- **Scope**: F4 (TextExtractor), F1 (ImageAnalyzer); `backend/aws/adapters/`.
- **Date**: 2026-07-21
- **Status**: active (reafirmada por AD-048 — o padrão adapter é mantido; só o motivo muda: já não é "contornar o LocalStack Community", passa a ser "trocar entre processamento 100% local e serviço gerenciado por `ENV`")

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
- **Status**: superseded by AD-048

### AD-038
- **Decision**: A fundação AWS (factory de cliente boto3 por `ENV`, adapters `TextExtractor`/`ImageAnalyzer`, IaC idempotente que provisiona os recursos nos dois ambientes) é uma **feature dedicada `aws-foundation`**, construída **antes** de F4/F1/F5, que passam a depender dela. Os **testes de integração usam LocalStack real** (Docker), conforme escolha do usuário — não moto. Docker é pré-requisito do Execute desta feature.
- **Reason**: A infra AWS é compartilhada por três features; isolá-la numa fatia fechada e verificável evita acoplá-la à lógica de prescrição (F4) e ter que extraí-la depois para F1/F5. LocalStack real dá fidelidade ao ambiente-alvo.
- **Trade-off**: Adiciona uma feature ao caminho antes de entregar valor de F4; e o Execute fica bloqueado por Docker (instalação de sistema, sudo).
- **Scope**: nova feature `aws-foundation`; pré-requisito de F4, F1, F5.
- **Date**: 2026-07-21
- **Status**: superseded by AD-048 (a fundação AWS deixa de depender de LocalStack/Docker; testes de integração de nuvem passam a usar o cliente boto3 substituído por dublê, AD-048 ponto 6)

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

### AD-042
- **Decision**: Pasta de topo `training/` (irmã de `backend/`/`frontend/`) contém o notebook Colab que roda o fine-tuning **real** (épocas completas) do YOLOv8 de F1 na GPU gratuita do Colab, **reusando** — nunca reimplementando — `backend/pipelines/video/object_finetune.py`/`object_loader.py`/`object_detector.py`/`object_evaluate.py` (código já testado e fechado por Verifier, F1 não é modificada). `training/prepare_dataset_subset.py` reusa `object_loader.load_annotated_frames` para preparar localmente só o subconjunto anotado do Endoscapes (1933 imagens/~207MB, medido nesta sessão — não os 36694 jpgs brutos/~6GB) antes do upload ao Drive. O notebook treina sobre `train/` (comportamento de F1 não alterado: `finetune()` usa o próprio treino como validação interna) e depois avalia o `best.pt` contra o split `test/` oficial do Endoscapes — nunca visto no treino — via os módulos de avaliação já existentes de F1, produzindo a métrica honesta reportada. Treino em GPU (Colab) não fere a AD-012: só esta etapa offline de treino usa GPU; a inferência do sistema continua CPU-only.
- **Reason**: O fine-tuning de F1 foi validado com treino curto/smoke em CPU (`epochs=1`); produzir pesos com precisão real em CPU é inviável no prazo (AD-012); GPU gratuita do Colab resolve sem violar a decisão de CPU-only em produção. F1 não tem split de validação separado (usa `val: images/train`) — como não pode ser modificada, a avaliação honesta contra `test/` é feita como um passo pós-treino independente, não dentro de `finetune()`.
- **Trade-off**: Dependência de ambiente externo não versionado (Colab); mitigado versionando o notebook + seed fixa + exportação de `results.csv`/`metrics_test.json` junto com o peso. A validação interna do treino (`finetune()`) continua metodologicamente fraca (val=train) — aceito porque não se pode tocar F1; a métrica que importa vem da avaliação pós-treino contra `test/`.
- **Scope**: F1 (video-analysis), etapa de treino apenas — não afeta o código de inferência já fechado. Nova pasta de topo `training/`.
- **Date**: 2026-07-22
- **Status**: active

### AD-043
- **Decision**: Pesos treinados (`best.pt` do YOLOv8, e qualquer artefato de modelo persistido no futuro) **não entram no Git** — vivem em `models/` (gitignored, exceto `models/README.md` versionado), publicados como asset de um GitHub Release. `models/README.md` documenta proveniência (notebook, hiperparâmetros, seed, data, métricas contra o split de teste) e é preenchido depois de cada treino real. `make models-fetch` baixa o Release configurado (`MODEL_RELEASE_URL` no `Makefile`, ainda vazio — nenhum Release publicado até esta sessão) para `models/best.pt`, mesmo padrão de `make data` (F0) para datasets.
- **Reason**: Pesos de modelo são binários grandes que não pertencem ao histórico do Git; o avaliador precisa poder rodar a demo sem retreinar, baixando um artefato versionado por Release em vez de reconstruir do zero.
- **Trade-off**: `make models-fetch` só funciona depois que o primeiro Release for publicado manualmente (passo fora do Git); até lá, quem quiser os pesos precisa rodar `training/` ou usar o smoke test já existente de F1.
- **Scope**: F1 (pesos YOLOv8); estrutura do repositório (`models/`, `.gitignore`, `Makefile`).
- **Date**: 2026-07-22
- **Status**: superseded by AD-047

### AD-044
- **Decision**: F5 inclui a camada de API fina exigida pela AD-029 (não fica para depois): `backend/app/` expõe FastAPI com, no mínimo, `/patients/{id}/timeline`, `/analyze`, `/alerts`, `/evidence/{id}`; `frontend/` usa **Streamlit** (framework antes "a definir" no `frontend/README.md`) como cliente fino que só consome essa API — sem lógica de processamento no frontend, sem acesso direto de `frontend/` a `backend/fusion/`.
- **Reason**: F5 P3 (dashboard) não é entregável sem uma camada de apresentação; a AD-029 já fixou "app separado que apenas consome a API" e o contrato REST mínimo — resolver "qual framework" com Streamlit fecha essa lacuna concretamente em vez de adiar de novo.
- **Trade-off**: Aumenta o escopo de F5 (motor de fusão + API + dashboard, não só fusão/alerta); aceito porque sem a API não há como demonstrar P3 dentro da arquitetura já decidida.
- **Scope**: F5 (fusion-and-alerting); `backend/app/`, `frontend/`. Concretiza a AD-029/030.
- **Date**: 2026-07-22
- **Status**: superseded by AD-050 (a parte da API fina em `backend/app/` continua válida; a escolha de Streamlit para `frontend/` foi substituída por React + Vite)

### AD-045
- **Decision**: Refina a AD-024. (a) **Timeline cross-modal do paciente-demo é curada manualmente, evento a evento** — o config do paciente-demo não só linka um registro por modalidade, mas declara explicitamente um subconjunto pequeno de eventos reais já detectados por F1–F4 (via `evidence_id`/`source_record_id`) e o instante de cada um na linha do tempo da demo. Isso decorre diretamente do already-active "associação... nunca inferida algoritmicamente" da AD-024 — investigação nesta sessão confirmou que os metadados de evidência reais de F1–F4 não compartilham um formato de tempo comparável entre si (F3 tem `start_s` real; F1-pose só índice de frame; F1-objeto/Endoscapes e F2 não expõem tempo nenhum; F4 tem timestamp real embutido no `evidence_id`), então não há como derivar uma linha do tempo única sem uma decisão de curadoria explícita. (b) **O paciente-demo usa só a raia pose/queda de F1** (URFD), não a raia objeto/estrutura crítica (Endoscapes) — a raia cirúrgica não compõe uma história narrativa coerente com queda/vitais/prescrição de um mesmo paciente-demo, mas continua demonstrável isoladamente fora do paciente-demo.
- **Reason**: (a) Evita fabricar uma normalização de tempo cross-modal que os dados reais não sustentam — mais honesto que inventar uma conversão frame→segundo ou assumir uma sincronia que as fontes não têm. (b) A AD-024 original citava "1 vídeo" de F1 antes de F1 ganhar duas raias (AD-039); com duas raias sem relação narrativa entre si, incluir a cirúrgica no paciente-demo forçaria uma composição ainda menos coerente que o já aceito "didática, não clínica".
- **Trade-off**: (a) A "reordenação cronológica" (FUSION-02) é testável com os eventos curados entregues fora de ordem, não com uma derivação automática de tempo real — comportamento do motor de fusão continua validável, só a fonte do timestamp é curada, não computada. (b) F1 fica sub-representada no paciente-demo (só 1 de 2 raias); a raia objeto/cirúrgica permanece coberta pelos próprios testes/relatório de F1, só não entra na fusão.
- **Scope**: F5 (fusion-and-alerting). Refina AD-024 (não a supersede — a associação manual/curada continua o princípio, só fica mais explícita no nível de evento).
- **Date**: 2026-07-22
- **Status**: active

### AD-046
- **Decision**: Duas mudanças transversais de higiene do repositório, pedidas explicitamente pelo usuário: (a) `training/` passa a ser um mundo **totalmente desacoplado** do resto do projeto — nenhum arquivo em `training/` importa `backend/`/`frontend/`, e nenhum arquivo em `backend/`/`frontend/` importa `training/`; o único ponto de contato é o arquivo de peso treinado (`models/best.pt`). Isso exigiu extrair a lógica de treino do YOLOv8 (antes em `backend/pipelines/video/object_finetune.py`) para um módulo novo e autocontido, `training/finetune.py` (só `ultralytics` + stdlib), com conversão COCO→YOLO própria e splits de treino/validação/teste reais (o código antigo do backend só usava `val=train`). O backend deixou de ter qualquer capacidade de treino — só inferência. (b) Todo vocabulário interno do método de trabalho (F0-F5, AD-NNN, IDs de requisito por feature, IDs de tarefa T1-T13, "Verifier", "user story", "SPEC_DEVIATION", labels de story P1/P2/P3, referências a `design.md`/`spec.md`/`validation.md`) foi removido de tudo fora de `.specs/` — ~110 arquivos de código (docstrings/comentários, preservando 100% do raciocínio técnico real, só removendo a citação de rastreabilidade), mais `Makefile`/`docker-compose.yml`/`.env.example`/`download_datasets.sh`/READMEs. `README.md` da raiz foi criado (não existia); `data/README.md` e `backend/README.md` foram reescritos por estarem desatualizados (faltavam 2 dos 5 datasets reais; citavam uma migração de código já concluída há várias sessões como se estivesse pendente).
- **Reason**: (a) Separar treino (GPU, esporádico, roda no Colab) de inferência (CPU, contínua, roda em produção) evita que o ambiente de produção carregue dependências/capacidades que nunca usa, e torna explícito que o sistema em operação nunca treina nada sozinho. (b) O vocabulário de rastreabilidade do método spec-driven (F1, AD-027, VITALS-06 etc.) é opaco para qualquer leitor externo ao processo — um professor avaliando o código não tem como saber o que "VIDEO-08" significa, e a citação raramente adicionava informação que a explicação técnica ao lado já não continha.
- **Trade-off**: (a) Pequena duplicação deliberada entre `training/finetune.py` (treino real) e um helper de smoke-train dentro de `backend/tests/conftest.py` (só para os testes de inferência terem pesos reais e rápidos) — única forma de manter as duas regras (backend não treina; `training/` não é importado por ninguém) sem quebrar os testes de inferência não-mockados. (b) Comentários/docstrings ficam menos rastreáveis a uma decisão específica de `STATE.md` a partir do código-fonte; a rastreabilidade completa permanece em `.specs/` e no histórico do git.
- **Scope**: Estrutura do repositório inteira — `backend/`, `frontend/`, `training/`, `models/`, `data/`, raiz. Não altera nenhum comportamento/lógica testável (suíte idêntica antes/depois: 382 passando, 36 skipped, 0 falhas).
- **Date**: 2026-07-22
- **Status**: active

### AD-047
- **Decision**: O peso treinado (`best.pt`) passa a ser publicado como arquivo de um repositório de modelo público no Hugging Face Hub (`AnaPRodrigues/endoscapes-surgical-detector`), em vez de asset de um GitHub Release (AD-043 superseded). `make models-fetch` baixa via `curl -L` direto da URL de download do Hugging Face (`https://huggingface.co/AnaPRodrigues/endoscapes-surgical-detector/resolve/main/best.pt`) — repo público, sem token necessário. O `Makefile` passa a ter o repo/arquivo do Hugging Face como padrão fixo (`MODEL_HF_REPO`/`MODEL_HF_FILE`), em vez da variável `MODEL_RELEASE_URL` vazia a preencher manualmente a cada Release. `models/README.md` continua documentando proveniência do jeito já definido em AD-043 (notebook, hiperparâmetros, seed, data, métricas) — só a seção "Versão publicada" passa a apontar para o Hugging Face.
- **Reason**: Pedido explícito do usuário — Hugging Face Hub em vez de GitHub Release como destino de publicação. É o registro padrão da comunidade para pesos de modelo (versionamento próprio para binários grandes, metadata/model card dedicados) e não exige nenhuma dependência nova no caminho de download (`curl` continua funcionando via URL `resolve`, mesmo padrão de hoje).
- **Trade-off**: Perde a amarração natural do peso a uma tag/commit do próprio repositório de código (GitHub Release liga o artefato a um commit/tag do Git do projeto); o Hugging Face versiona por commit no repo do modelo, independente do Git do projeto — proveniência continua garantida por `models/README.md`, não pela plataforma de hospedagem. Como nenhum Release chegou a ser publicado sob AD-043 (`MODEL_RELEASE_URL` nunca foi preenchida), não há artefato já publicado para migrar — troca limpa, sem custo de migração.
- **Scope**: F1 (pesos YOLOv8); estrutura do repositório (`models/README.md`, `Makefile`, `training/README.md`, notebook de treino).
- **Date**: 2026-07-23
- **Status**: active

### AD-048
- **Decision**: Reformulação de infraestrutura pedida pelo usuário — remoção completa do LocalStack e da arquitetura serverless/gerenciada. O sistema passa a ter dois modos por `ENV`: `local` (padrão, **nenhuma** chamada de nuvem, **zero** boto3 em runtime — extração de PDF por pdfplumber/Tesseract, rótulos de imagem por YOLOv8 local) e `aws` (chama **exatamente dois** serviços gerenciados síncronos com bytes embutidos: Textract `analyze_document` para prescrições e Rekognition `detect_labels` para quadros de vídeo; o resultado volta ao processamento local). Removidos: S3, SNS, DynamoDB, SQS, Lambda, Step Functions e todo IaC/handler associado (`aws/provision.py`, `pipelines/*/handler.py`, `pipelines/*/infra.py`, `pipelines/prescription/history.py`, `docker-compose.yml`). O factory `aws/clients.py` só existe para o modo `aws` e só cria clientes de Textract/Rekognition. Lógica útil que vivia na nuvem foi trazida ao processo local: a decisão de alerta (transição de nível que cruza o limiar) já era pura na API e permanece; o histórico de prescrições (para a regra de variação abrupta) deixa de vir do DynamoDB e passa a ser injetado por parâmetro (`previous_record`), a ser ligado ao banco local no bloco seguinte. Alertas deixam de ser enviados por SNS — passam a ser registrados no banco local e exibidos na interface (destino muda, comportamento de geração automática ao cruzar o limiar não muda).
- **Reason**: Pedido explícito do usuário. Elimina a dependência de Docker/LocalStack para desenvolver, testar e demonstrar; reduz a superfície de nuvem a dois serviços com valor claro (OCR gerenciado e visão gerenciada), mantendo o resto 100% local e CPU-only. As APIs síncronas com bytes dispensam bucket intermediário — o arquivo local vai direto na chamada.
- **Trade-off**: Perde-se a demonstração de uma arquitetura serverless orientada a eventos (S3→Lambda→SNS/DynamoDB) que existia antes; em troca, o sistema fica reproduzível por qualquer pessoa sem conta AWS nem Docker, e o caminho de nuvem fica trivial de auditar (dois serviços, chamadas síncronas). Supersede a parte de fundação de nuvem que dependia de LocalStack/serverless (AD-001/004/024/034/043-related infra); o padrão de adapter por `ENV` é mantido.
- **Scope**: `backend/aws/`, `backend/pipelines/*/` (remoção de handlers/infra), `backend/app/`, `Makefile`, `.env.example`, `docker-compose.yml`, documentação. Reformulação em 6 blocos (este é o bloco 1); blocos seguintes: banco SQLite local, frontend React, log de atividade, pipeline de oxigenação (BIDMC), dados de demonstração.
- **Date**: 2026-07-24
- **Status**: active

### AD-049
- **Decision**: Bloco 2 da reformulação — banco local de pacientes (SQLite em `data/app.db`, gitignored) e nova superfície de API por paciente real, substituindo a abordagem antiga de "paciente-demo" curado por YAML. Quatro tabelas: `pacientes`, `uploads` (modalidade video|audio|documento|sinais_vitais, situação recebido|processando|concluido|erro), `analises` (resultado JSON + pontuação), `alertas` (nível + motivo clínico + referências de evidência). Arquivos enviados vivem em `data/uploads/<paciente>/<modalidade>/`; o banco guarda só o caminho. Novos módulos em `backend/app/`: `db.py` (esquema idempotente), `repositorio.py` (CRUD), `armazenamento.py` (arquivos), `analise.py` (despacho por modalidade — **compõe** as funções públicas de cada pipeline sobre um único arquivo, sem reescrever detecção), `servico.py` (orquestra análise + monta a linha do tempo de risco a partir do banco reusando o motor de fusão existente `risk_engine`/`hysteresis`, e registra alerta ao cruzar o limiar). Endpoints: CRUD de pacientes, upload multipart + listagem, disparo/consulta de análise, timeline consolidada, alertas por paciente + lista geral, evidência por id. `python-multipart` adicionado às dependências. Campo morto `sns_topic` removido de `PatientDemoConfig`.
- **Reason**: O sistema passa a operar sobre pacientes reais persistidos, não uma composição curada em YAML. A linha do tempo e os alertas passam a ser derivados das análises reais de cada paciente. O despacho por composição honra "reaproveitar os pipelines sem reescrevê-los".
- **Trade-off**: Para reusar os pipelines (orientados a dataset) sobre um único arquivo, os uploads têm o **formato dos datasets de origem** (sequência de quadros URFD para vídeo, gravação+anotação ICBHI para áudio, registro wfdb para vitais, PDF para documento) — documentado como restrição da demonstração. A posição de cada evento na linha do tempo vem de `instante_s` (curado pela carga de demonstração do bloco 6) ou do intervalo real desde o início do monitoramento. Os módulos de fusão da abordagem antiga (`loader.py` de config curada, `alert.py`, `transitions.py` e a YAML `configs/demo.yaml`) ficaram **órfãos em produção** (ainda testados, verdes) — remoção adiada para decisão do usuário, não feita neste bloco para não desestabilizá-lo.
- **Scope**: `backend/app/` (novos módulos + rotas reescritas), `backend/pipelines/fusion/config.py` (limpeza de `sns_topic`), `pyproject.toml`, `.gitignore` (já cobria `data/*`), documentação. Bloco 2 de 6.
- **Date**: 2026-07-24
- **Status**: active

### AD-050
- **Decision**: Bloco 3 — o painel Streamlit (`frontend/app.py`) foi substituído por uma aplicação de página única em `frontend/`: **React + Vite + react-router + Recharts**, JavaScript, chamadas por `fetch`, dependências enxutas (sem SSR, sem biblioteca de componentes pesada). Só consome a API por HTTP; nenhuma lógica de processamento no frontend. Três telas: Pacientes (lista com indicador de risco colorido + cadastro/remoção), Detalhe do paciente (cabeçalho com nível em destaque, área de envio por modalidade com situação, quatro painéis por modalidade com o último achado em **linguagem clínica**, linha do tempo de risco com eixo em tempo legível + linhas de atenção/alerta + marcadores por evento, painel de alertas do paciente, drill-down de evidência por evento) e Alertas (lista geral com filtro por paciente e por nível). Nenhum identificador técnico ou número com muitas casas aparece na tela (pontuações em %). O Vite faz proxy das rotas de API para o backend em desenvolvimento. `streamlit` removido das dependências Python; `make serve-front` agora roda o Vite; novo alvo `make frontend-install`. `frontend/README.md` reescrito com passo a passo.
- **Reason**: Pedido explícito do usuário — interface web em JavaScript no lugar do Streamlit, mais adequada para apresentação e para as telas por paciente introduzidas no bloco 2.
- **Trade-off**: Introduz uma toolchain Node/npm ao projeto (antes 100% Python); em troca, uma UI mais controlável e apresentável. Verificação: `npm run build` compila sem erros (842 módulos) e um smoke test ponta a ponta confirmou o Vite servindo o painel e fazendo proxy correto para a API real (paciente criado e listado via proxy). Inspeção visual detalhada no navegador continua sendo um passo humano recomendado antes de gravar o vídeo.
- **Scope**: `frontend/` inteiro (novo app React; `app.py` Streamlit removido), `Makefile` (serve-front + frontend-install), `pyproject.toml` (remove streamlit), `.gitignore` (já cobria node_modules/dist), documentação. Bloco 3 de 6.
- **Date**: 2026-07-24
- **Status**: active

### AD-051
- **Decision**: Bloco 4 — registro de atividade legível no terminal, pensado para o vídeo de demonstração. Novo módulo `common/atividade.py` com funções de log nas fronteiras do fluxo: arquivo recebido, análise iniciada/concluída (com duração), origem do processamento, cálculo de risco e decisão de alerta. Cada linha traz o contexto entre colchetes e, nas etapas de processamento, a **origem explícita**: `[LOCAL]` (modelo/biblioteca na máquina) ou `[AWS]` (serviço gerenciado). As chamadas de nuvem registram serviço + operação + duração + `requestId` da resposta (evidência de que a chamada foi real). Mensagens incluem paciente e modalidade. Formato de log mudado para `HH:MM:SS <mensagem>` (`common/logging.py`); o access log do uvicorn foi rebaixado para WARNING (`app/main.py`) para não afogar o log de aplicação. Ligações: `routes.enviar_arquivo` (recebido), `servico.analisar_upload` (iniciada/concluída/falhou), `servico._reavaliar_alertas` (risco/alerta), despachos de `analise.py` (`[LOCAL]` por modalidade), adapters `pdfplumber` (`[LOCAL]`) e `Textract`/`Rekognition` (`[AWS]` com duração+requestId).
- **Reason**: Pedido explícito do usuário — o terminal precisa mostrar o que o sistema faz, com a origem (local vs. nuvem) marcada, para exibição em vídeo. Clareza importa mais que volume.
- **Trade-off**: O formato de log ficou mais enxuto (sem nível/nome do logger na saída de terminal) — decisão consciente pela legibilidade da demonstração; a captura de log dos testes (`caplog`) usa formatter próprio do pytest e não é afetada. Verificação: log capturado ao vivo confirmou todos os formatos batendo com o exemplo do enunciado (`[paciente:...]`, `[prescrição][LOCAL]`, `[prescrição][AWS] Textract analyze_document ... requestId=...`, `[risco] pontuação X -> Y — nível NIVEL`, `[alerta] registrado ...`); zero linhas de acesso HTTP afogando o log.
- **Scope**: `common/atividade.py` (novo), `common/logging.py` (formato), `app/main.py` (access log), `app/routes.py`/`app/servico.py`/`app/analise.py` (ligações), `aws/adapters/cloud.py` e `pipelines/prescription/adapters.py` (origem). Bloco 4 de 6.
- **Date**: 2026-07-24
- **Status**: active

### AD-052
- **Decision**: Bloco 5 — segundo caso de sinais vitais (internação adulta, BIDMC), fechando a cobertura de **oxigenação (SpO2)** e frequência cardíaca (HR) de adulto, antes um gap real. Novo `pipelines/vitals/bidmc.py`: lê os registros numéricos do BIDMC (os com sufixo `n`, ex.: `bidmc01n`, a 1 Hz, que não constam da listagem principal), expõe HR e SpO2, e **reaproveita os detectores existentes** (escore móvel + floresta de isolamento) e a extração de features por janela — não reimplementa detecção. Como o BIDMC não vem com desfecho anotado, a avaliação usa **critérios clínicos publicados** como referência (num único lugar, `CriteriosClinicos`): SpO2 sustentada < 90% = hipoxemia; HR fora de 60–100 bpm = bradicardia/taquicardia. Gera evidência no mesmo contrato (gráfico da janela anômala destacada) e reporta métricas (precision/recall/f1) contra os critérios. Varredura utilitária `varrer()` + `python -m pipelines.vitals.bidmc` (alvo `make bidmc-scan`) lista quais dos 53 registros têm eventos (para escolher casos de demo; seleciona, não altera sinais). O despacho de análise (`app/analise._analisar_sinais_vitais`) passa a rotear pelos canais do registro: FHR → cardiotocografia (CTU-UHB); HR/SpO2 → internação (BIDMC).
- **Reason**: Pedido explícito do usuário (bloco 5) e fechamento do gap de SpO2. Reusar os detectores mantém a coerência com o caso CTG e evita reimplementar lógica de detecção.
- **Trade-off**: As features por janela foram calibradas para cardiotocografia (baseline/variabilidade/decelerações em bpm); aplicadas ao HR são clinicamente análogas, e ao SpO2 servem como descritores estatísticos genéricos para a floresta de isolamento (a referência de avaliação do SpO2 é o critério clínico de hipoxemia, não a feature CTG). 1 dos 53 registros (`bidmc19n`) é pulado por ter o cabeçalho do canal SpO2 corrompido — tratamento gracioso, não bug. Verificação: 8 testes de BIDMC (unit dos critérios/métricas + integração com dados reais) + teste de roteamento do despacho, todos verdes; `make bidmc-scan` lista 13 registros com evento.
- **Scope**: `pipelines/vitals/bidmc.py` (novo), `app/analise.py` (roteamento CTG vs internação), `Makefile` (`bidmc-scan`), documentação. Bloco 5 de 6.
- **Date**: 2026-07-24
- **Status**: active

### AD-053
- **Decision**: Bloco 6 (último da reformulação) — dados de demonstração e teste, em 3 partes. (a) **Script de carga** `backend/scripts/seed_demo_patients.py` (`make seed-demo`): cria 3 pacientes reais no banco local, cada um vinculado a arquivos reais de 2 modalidades — Paciente A: queda (URFD `fall-01`) + cardiotocografia (CTU-UHB `1001`, pH 7.14); Paciente B: estrutura crítica cirúrgica (Endoscapes, quadro `168_24925.jpg` do split `test/`) + prescrição sintética com dose fora da faixa (digoxina 1,5 mg; faixa real [0,125; 0,5] mg); Paciente C: dificuldade respiratória (ICBHI) + internação/hipoxemia (BIDMC `bidmc32n`). Idempotente (paciente com o mesmo nome é reaproveitado). Precisou de 2 adições de suporte, pequenas e aditivas: `armazenamento.copiar_diretorio` (copia uma sequência de quadros — formato multi-arquivo que o endpoint HTTP de upload único não cobre) e o parâmetro opcional `instante_s` em `servico.analisar_upload` (fixa a posição do evento na linha do tempo — o próprio `_instante_s` já citava esse uso previsto desde o Bloco 2, sem existir ainda). (b) **Gerador de prescrições sintéticas**: já existia (`pipelines/prescription/generator.py`, construído durante F4) — só reaproveitado pelo script de carga, nenhum código novo. (c) **Áudio de consulta**: sem substituto automático (precisa de fala humana real em português) — só um roteiro de gravação (`docs/roteiro-audio-consulta.md`), sem dado de demo; painel do paciente-demo de áudio usa só ICBHI.
- **Reason**: Fecha o Bloco 6 pedido pelo usuário — qualquer pessoa que clonar o projeto e rodar `make seed-demo` já tem pacientes reais com achados em todas as modalidades para explorar no painel, sem precisar cadastrar nada na mão. O gerador de prescrições já existente evita retrabalho; o roteiro de áudio documenta o único item que exige uma ação humana fora do meu alcance.
- **Trade-off**: A raia cirúrgica de vídeo (Endoscapes) nunca tinha sido ligada a nenhum código de produção antes deste bloco — `app/analise._analisar_video` passa a rotear por formato do envio (diretório → pose/queda; arquivo único → estrutura crítica, via o adaptador `ImageAnalyzer` local/aws já existente em `pipelines/video/adapters.py` mas nunca chamado). Isso torna `pipelines/video/cli.py` (driver em lote só da raia pose) parcialmente desatualizado no comentário de escopo — corrigido nesta sessão junto com a limpeza de jargão que o arquivo ainda carregava (F1/F5/AD-045b citados fora de `.specs/`, resquício de código escrito depois da varredura da AD-046). Nenhum evento novo tem `instante_s` "real" no sentido de F1-F4 (AD-045a) — os valores usados na carga (0s/300s/600s) são curados pelo próprio script, mesmo princípio já aceito para o paciente-demo antigo.
- **Scope**: `backend/scripts/seed_demo_patients.py` (novo), `backend/app/armazenamento.py` (`copiar_diretorio`), `backend/app/servico.py` (`instante_s`), `backend/app/analise.py` (raia objeto cirúrgica), `docs/roteiro-audio-consulta.md` (novo), `docs/relatorio-tecnico.md` (sincronizado com o fluxo real), `Makefile` (`seed-demo`), `README.md`/`backend/README.md`. Fecha a reformulação de 6 blocos (AD-048 a AD-053).
- **Date**: 2026-07-24
- **Status**: active

## Rastreabilidade de Requisitos Obrigatórios

Mapeamento dos requisitos do enunciado (`docs/8IADT-Fase-4-Tech-challenge.md`) às features.

| Requisito do enunciado | Feature / cobertura | Status |
| --- | --- | --- |
| Req.1 — Vídeo: análise postural (OpenPose/pose) | F1 raia pose: URFD + MediaPipe Pose (AD-039) — **FECHADO, Verifier PASS** | ✅ Coberto |
| Req.1 — Vídeo: detecção de objeto/área crítica (YOLOv8) | F1 raia objeto: Endoscapes/Cholec80 + YOLOv8/Rekognition (AD-033/035) — **FECHADO, Verifier PASS** | ✅ Coberto |
| Req.1 — Vídeo: relatórios automáticos de desvios | F1 (saída: JSON de eventos + frames anotados + relatório) — **FECHADO, Verifier PASS** | ✅ Coberto |
| Req.2 — Áudio: alterações vocais (cansaço, dif. respiratória) | F2: ICBHI (crackle/wheeze) + jitter/shimmer/HNR (AD-020) — **FECHADO, Verifier PASS** | ✅ Coberto |
| Req.2 — Áudio: transcrição (Azure STT → faster-whisper) | F2 (AD-003) — **FECHADO, Verifier PASS** | ✅ Substituído |
| Req.2 — Áudio: termos críticos + sentimento (Text Analytics → local) | F2 (AD-003) — **FECHADO, Verifier PASS** | ✅ Substituído |
| Req.2 — Áudio: disartria | Trabalho futuro (sem dataset aberto rotulado, AD-020) | ⚠️ Deferido |
| Req.3 — Vitais: batimentos (HR) | F3 caso CTG: FHR do CTU-UHB **e** caso internação: HR do BIDMC (`pipelines/vitals/bidmc.py`, AD-052) | ✅ Coberto |
| Req.3 — Vitais: oxigenação (SpO2) | **Coberto na reformulação (bloco 5, AD-052)**: `pipelines/vitals/bidmc.py` lê os registros numéricos do BIDMC (HR/SpO2 a 1 Hz) e detecta hipoxemia (SpO2 sustentada < 90%) reusando os detectores existentes, com referência clínica publicada. O gap real que eu havia flagrado antes está fechado. | ✅ Coberto |
| Req.3 — Vitais: pressão arterial (PA) | Trabalho futuro — fonte aberta identificada: VitalDB (AD-041) | ⚠️ Deferido |
| Req.3 — Prescrições: evolução | F4: Textract/adapter + regras — **FECHADO, Verifier PASS** (AD-022/035) | ✅ Coberto |
| Req.3 — Padrões de movimentação do paciente | F1 raia pose: URFD fall/ADL (AD-039) — **FECHADO, Verifier PASS** | ✅ Coberto |
| Req.3 — Alertas automáticos à equipe | F5: Lambda → SNS (AD-004/024) — **FECHADO, Verifier PASS** | ✅ Coberto |
| Objetivo — Fusão multimodal | F5: late fusion + risk score (AD-024) — **FECHADO, Verifier PASS** | ✅ Coberto |
| Objetivo — Nuvem gerenciada (Azure → AWS) | AWS Learner Lab + LocalStack (AD-001/034); **explicar a troca no relatório/vídeo** | ✅ Substituído |
| Objetivo — Tempo real | Near-real-time por micro-batch (AD-011) | ✅ Substituído |
| Entregável — Relatório técnico | Pendente (escrever ao final) | ⏳ Pendente |
| Entregável — Vídeo demo ≤15 min | Pendente (gravar ao final) | ⏳ Pendente |

Lacunas obrigatórias remanescentes: **nenhuma bloqueadora**. Sinais vitais: `batimentos` (HR — FHR do CTU-UHB e HR do BIDMC) e `oxigenação` (SpO2 do BIDMC, AD-052) cobertos; `pressão arterial` deferida com justificativa (sem dataset aberto em waveform sem credenciamento). `disartria` (áudio) deferida (sem dataset aberto rotulado). Entregáveis (relatório + vídeo) pendentes por natureza (fase final).

## Handoff

### Estado atual — Reformulação pós-MVP (AD-048 a AD-053) — **FECHADA nesta sessão (2026-07-24)**

O MVP original (F0-F5, spec-driven, ver histórico abaixo) foi fechado com Streamlit + LocalStack + arquitetura serverless (S3/Lambda/SNS/DynamoDB). O usuário pediu uma reformulação em **6 blocos**, executados em ordem, cada um parando para aprovação antes do próximo (ver pedido original do usuário para o texto completo de cada bloco). Regras transversais: vocabulário interno do método (F0-F5, AD-NNN, nomes de fase) só dentro de `.specs/`; texto voltado ao usuário em linguagem de domínio, compreensível sem contexto do projeto; `training/` e os pesos treinados não são tocados; suíte verde ao final de cada bloco. **Todos os 6 blocos estão commitados.**

- **Bloco 1 — remove LocalStack/serverless, nuvem = só Textract+Rekognition síncronos** (AD-048). **Commitado** (`e02949b`). Verificado nesta sessão: `docker-compose.yml` não existe mais; `backend/aws/clients.py` só cria cliente para `textract`/`rekognition`, recusa qualquer outro serviço; modo `local` (padrão) não chama nenhum SDK de nuvem.
- **Bloco 2 — banco local de pacientes (SQLite) + endpoints por paciente** (AD-049). **Commitado** (`959c717`). `backend/app/{db,repositorio,armazenamento,analise,servico}.py` + rotas novas.
- **Bloco 3 — frontend React + Vite substituindo o Streamlit** (AD-050). **Commitado** (`a0f403d`). Verificado nesta sessão: `frontend/package.json` confirma `react`/`react-router-dom`/`recharts`/`vite`; sem `streamlit` no projeto.
- **Bloco 4 — registro de atividade legível no terminal, com origem `[LOCAL]`/`[AWS]`** (AD-051). **Commitado** (`243a109`). `backend/common/atividade.py` confirmado presente.
- **Bloco 5 — segundo caso de sinais vitais (BIDMC: HR + SpO2 de internação adulta)** (AD-052). **Commitado** (`1402885` + fix de doc `b731a59`). Estava com código pronto mas não commitado no início desta sessão (retomando de uma pausa anterior) — verificado e commitado: `backend/pipelines/vitals/bidmc.py` (novo) + roteamento em `backend/app/analise.py` (CTG vs. internação pelos canais do registro) + 8 testes novos + `make bidmc-scan`.
- **Bloco 6 — dados de demonstração e teste** (AD-053). **Commitado** (`e45b116` raia objeto, `dc0a3e8` script de carga, `5c6bd2f` docs). (a) `app/analise._analisar_video` agora roteia por formato do envio: diretório → pose/queda (já existia); arquivo único → estrutura crítica cirúrgica, via o adaptador `ImageAnalyzer` (`pipelines/video/adapters.py`) que existia desde antes desta sessão mas nunca tinha sido chamado por nenhum código de produção — confirmado com o peso real publicado (`models/best.pt`) contra um quadro do split `test/` do Endoscapes (`168_24925.jpg`), detecta `cystic_artery`/`cystic_duct`/`cystic_plate` de verdade. (b) `backend/scripts/seed_demo_patients.py` (`make seed-demo`, idempotente) cria 3 pacientes reais com dados reais de 5 datasets + 1 prescrição sintética — rodado de verdade nesta sessão, ponta a ponta, com risco calculado e evidência gravada para as 6 análises. (c) `docs/roteiro-audio-consulta.md` (checklist de gravação, sem dado de demo). (d) `docs/relatorio-tecnico.md` sincronizado (§4 e §8 ainda descreviam o "paciente-demo" único curado por YAML, obsoleto desde o Bloco 2).
- **Higiene de rastreabilidade feita nesta sessão**: AD-034/037/038 (perfil LocalStack, estrutura `docker-compose`, `aws-foundation` com testes de integração via LocalStack) marcadas `superseded by AD-048`; AD-035 (padrão adapter) mantida `active`, mas anotada como reafirmada por AD-048 com motivo atualizado; AD-044 (Streamlit como frontend de F5) marcada `superseded by AD-050`. Nenhuma dessas ADs tinha sido atualizada quando os blocos 1/3 foram commitados — a tabela de decisões estava desalinhada do código real até esta sessão.
- **Gate final da reformulação**: `make test` (`pytest backend/tests`) **478 testes** (incluindo os novos do Bloco 6), sem falhas, alguns skips pré-existentes documentados (evidência de demo ausente em cenários específicos, sem relação com este bloco); `ruff check backend` limpo.
- **Achado não corrigido (decisão do usuário pendente)**: `backend/pipelines/fusion/` (módulo de F5, construído *depois* da varredura de jargão da AD-046) ainda tem bastante vocabulário interno fora de `.specs/` — códigos `FUSION-NN`, `F1`/`F5`, `AD-045a` em docstrings/comentários de `hysteresis.py`, `models.py`, `loader.py`, `risk_engine.py`, `configs/demo.yaml`. Viola a regra transversal desta reformulação ("rótulos internos só em `.specs/`"), mas é dívida pré-existente à reformulação, não algo introduzido pelos blocos 1-6 — corrigi só o um arquivo que toquei de passagem nesta sessão (`pipelines/video/cli.py`, que citava F1/F5/AD-045b). Uma varredura completa de `fusion/` (nos mesmos moldes da AD-046, ~poucos arquivos desta vez) fica para quando o usuário priorizar — não é bloqueador do MVP nem desta reformulação.
- **Next step**: reformulação encerrada; próximos passos ficam a critério do usuário — candidatos: varredura de jargão em `fusion/` (achado acima), inspeção visual do painel React num navegador (nunca feita por um humano), relatório técnico e vídeo de demonstração (entregáveis finais, ainda pendentes por natureza).
- **Branch**: `feat/f3-vitals-anomaly`; `main` só tem o commit inicial — estratégia de merge/rename para `main` continua em aberto (ver "Aberto" no histórico abaixo).
- **Ambiente**: ativar `.venv` (`source .venv/bin/activate`) antes de `pytest`/`ruff`/`python`; `PYTHONPATH=backend` necessário fora do pytest. Sem Docker/LocalStack nesta reformulação — não é mais pré-requisito.

### Histórico — MVP original (F0-F5, spec-driven), antes da reformulação

As entradas abaixo descrevem o estado em 2026-07-22/23, **antes** dos blocos 1-6 acima. Streamlit, LocalStack, S3/SNS/DynamoDB/Lambda e o "paciente-demo" curado por YAML citados aqui foram removidos ou substituídos pela reformulação — não presumir que ainda existem no código. Mantido só para rastreabilidade histórica das decisões de F1-F5.

- **PAUSA a pedido do usuário (2026-07-22, fim de sessão)** — usuário vai desligar a máquina, retoma amanhã. Nada em andamento, working tree limpa, tudo commitado (último commit `a0842b6`). Antes de retomar: reler este Handoff inteiro (não presumir contexto).
- **Feature**: **F1 (video-analysis) — FECHADA** (Verifier PASS; nota: `object_finetune.py` foi removida de `backend/pipelines/video/` na emenda AD-046 — treino não é mais responsabilidade do backend, ver abaixo; nenhum outro arquivo de F1 mudou). **F2 (audio-analysis) — FECHADA** (Verifier PASS na iteração 2). **F5 (fusion-and-alerting) — FECHADA** (Verifier PASS após fix de 2 gaps, ver bullet dedicado abaixo). Emendas transversais concluídas: camada de treino desacoplada (`training/`, AD-042/043), limpeza de jargão interno fora de `.specs/` (AD-046), publicação do peso treinado no Hugging Face Hub (AD-047, ver bullet dedicado abaixo). Único item não iniciado do escopo original: **`frontend/`** já existe como parte de F5 (`frontend/app.py`, Streamlit, AD-044) — falta só a inspeção visual humana num navegador (ver bullet de F5).
- **Verificação de F2 (Verifier independente, 2026-07-22, 2 iterações)**: `.specs/features/audio-analysis/validation.md`. Iteração 1: **FAIL**, 4 gaps (1 blocker — `backend/tests/audio/test_config.py` colidia de nome-base com `backend/tests/common/test_config.py` e quebrava `make test` do repo inteiro; 2 major — mutante sobrevivente `class_weight="balanced"` sem teste, evidência de fadiga vocal P3 AC3 sem teste + inalcançável com 1 único áudio; 1 minor — tolerância a áudio de consulta corrompido sem teste). 4 fixes aplicados (commits `2ccce34`, `d8dc8ef`, `657511f`, `e8a1189|; Fix 3 seguiu decisão do usuário: documentar a limitação de baseline com 1 áudio em `design.md` § Risks & Concerns, em vez de redesenhar). Iteração 2: **PASS** — 14/14 requisitos `Verified`, gate `make test && make lint` limpo (**384 passando, 0 falhas, 36 skipped**), 3/3 mutações novas mortas, zero regressão. F2 está fechada; nenhum resíduo aceito pendente.
- **Resumo de implementação de F2** (13 tarefas, 2 lotes via sub-agentes, todas commitadas): Lote 1 (T1–T7): T1 `models.py` (`365a9a1`), T2 `config.py` (`f0c07c4`), T3 `icbhi_loader.py` (`2099f11`), T4 `icbhi_features.py` (`a7e02d8`), T5 `icbhi_classifier.py` (`37354e1`), T6 `icbhi_evaluate.py` (`071d105`), T7 `icbhi_evidence.py` (`6504290`). Lote 2 (T8–T13): T8 `transcribe.py` (`afaa8fd`), T9 `critical_terms.py` (`ef4e887`), T10 `sentiment.py` (`eaf5616`), T11 `acoustic_features.py` (`bb30a4d`), T12 `fatigue_score.py` (`ddd190e`), T13 `cli.py` (`2aafbfe`). Depois: 4 commits de fix (ver acima) + 2 commits de docs do Verifier (`f579f3d` iteração 1, `43ef7c3` iteração 2).
- **Decisões de F2 registradas (não re-derivar)**: classificador ICBHI é `RandomForestClassifier(class_weight="balanced")`, 4 classes (`normal/crackle/wheeze/both` — SPEC_DEVIATION, ICBHI real tem ciclos com crackle+wheeze simultâneos, 506/6898 medidos); split treino/teste por `GroupShuffleSplit` agrupado por `patient_id`; subconjunto curado = `icbhi_max_patients` default 40; **sem persistência de modelo — `icbhi_classifier.train()` treina do zero a cada execução do CLI, nenhum artefato salvo em disco** (AD-008, confirmado no código real em `backend/pipelines/audio/icbhi_classifier.py`, sem `joblib.dump`/`load` em nenhum lugar de F2); `common/config.py` **não é reusado** por F2 (específico de vitals apesar do nome); `temperature=0.0` fixo no faster-whisper por determinismo; léxico de sentimento é lista embutida curada pelo agente; score de fadiga (P3) usa z-score contra o baseline dos áudios de consulta da mesma execução — com 1 único áudio o baseline é degenerado (desvio-padrão zero) e o score fica sempre `0.0`, documentado como limitação aceita, não redesenhado.
- **Gap aceito em F2 (não redescobrir)**: `transcribe.py` — o caminho positivo de transcrição (fala real → transcript correto, `reliable=True`) não tem teste de integração com áudio real, porque não existe ainda áudio de consulta gravado pelo grupo (roteiro exato ainda não definido, "confirmed: n" na spec). A lógica de `reliable` tem cobertura unit completa com `model` fake; o caminho negativo (`reliable=False`) é provado com áudio real do ICBHI (sem fala) através do CLI completo. Verificado 2x (iterações 1 e 2) como gap aceito, não uma falha nova.
- **Emenda `training/` — FECHADA** (AD-042/AD-043, commits `a7c5784` inicial + follow-up de desacoplamento total). Usuário vai rodar o Colab manualmente — nenhuma ação pendente aqui.
- **Documentação sincronizada**: `video-analysis/spec.md` e `prescription-analysis/spec.md` tinham a tabela de rastreabilidade como "Pending" apesar de fechadas — sincronizado a partir de cada `validation.md` real (commit `214e5d0`). Nenhuma mudança de código.
- **F5 (fusion-and-alerting) — Design APROVADO e commitado** (`6b918e7`). Duas decisões de escopo confirmadas pelo usuário, **AD-044** e **AD-045**: (a) F5 inclui a API fina (`backend/app/`, FastAPI) + Streamlit como frontend (fecha o "a definir" antigo); (b) a linha do tempo cross-modal do paciente-demo é curada manualmente evento a evento (formatos de tempo reais de F1-F4 são incompatíveis entre si); (c) paciente-demo usa só a raia pose/queda de F1 (URFD), não a raia objeto/Endoscapes. `pyproject.toml` ganhou `fastapi`/`uvicorn`/`httpx`/`requests`/`streamlit`, todos confirmados instaláveis.
- **Decisões de Design de F5 registradas (não re-derivar)**: `pipelines/fusion/loader.py` lê sidecars JSON reais de `output/<feature>/<run_id>/` (nunca inventa dado); decaimento exponencial `2**(-Δt/half_life_s)`, default 600s; histerese com classe stateful (`HysteresisClassifier`) que só muda de nível ao cruzar limiar±histerese a partir do nível atual; severidade por evento é **curada** (default 1.0, overridable), não computada — não há escala comum entre os 4 detectores; dedupe de alerta reusa a MESMA tabela DynamoDB genérica de F4 com prefixo `ALERT#`; nova função aditiva `ensure_subscription` em `aws/provision.py` para inscrever e-mails no tópico SNS (confirmação de inscrição é manual, passo operacional documentado, não bug); Streamlit só fala HTTP com `backend/app/`, nunca importa `backend/fusion/` direto. F5 ganha uma tarefa nova, `backend/pipelines/video/cli.py` (**arquivo novo, aditivo** — só orquestra os módulos já verificados da raia pose de F1, nenhum modificado), porque F1 nunca ganhou um driver ponta a ponta gravando evidência real em `output/video/<run_id>/`.
- **Emenda AD-046 (desacoplar `training/` + remover jargão) — FECHADA nesta sessão.** (a) `object_finetune.py` removida de `backend/pipelines/video/` (produção não treina mais nada); lógica de treino recriada do zero em `training/finetune.py`, autocontido, com splits treino/val/teste reais (o código antigo só usava `val=train`) — testado rodando de verdade contra dados reais, pegou e corrigiu 2 bugs reais (chave `train:` obrigatória no YAML do ultralytics mesmo para só validar; `model.val()` também polui a raiz do repo sem `project=`/`name=` explícitos). `training/prepare_dataset_subset.py` e o notebook pararam de importar qualquer coisa do backend. `backend/tests/conftest.py` ganhou um helper de smoke-train autocontido (duplicação deliberada e mínima, documentada) para a fixture `finetuned_weights` continuar dando pesos reais aos testes de inferência sem violar o desacoplamento em nenhuma direção. (b) ~110 arquivos de código (docstrings/comentários) + `Makefile`/`docker-compose.yml`/`.env.example`/`download_datasets.sh`/READMEs tiveram o vocabulário de rastreabilidade (F0-F5, AD-NNN, IDs de requisito, T1-T13, "Verifier", P1/P2/P3 como label de story, refs a `design.md`/`spec.md`) removido, preservando 100% do raciocínio técnico. `README.md` da raiz criado (não existia); `data/README.md` e `backend/README.md` reescritos (estavam desatualizados). Verificação final: `make test` **382 passando, 36 skipped, 0 falhas** (idêntico ao baseline antes da emenda), `make lint` limpo, grep de jargão fora de `.specs/`/`.claude/`/`.cursor/`/`.windsurf/` retorna vazio (só falsos-positivos de "F1" como F1-score).
- **In-progress**: nenhum — todas as mudanças desta sessão estão commitadas. `git status` confirmado limpo ao final.
- **Next step (retomar amanhã)**: Perguntar ao usuário se quer começar pela fase **Tasks** de F5 (14 requisitos + `pipelines/video/cli.py` + API/dashboard — bem maior que F1/F2, avaliar quantos batches de sub-agente) ou se já rodou o notebook de treino no Colab (produziria o primeiro `best.pt` real + Release — ação do usuário, fora do meu alcance, ver `training/README.md`; não bloqueia F5, cuja config de paciente-demo usa só a raia pose de F1, AD-045b). Execute de F5 vai precisar rodar `pipelines/video/cli.py` (novo, ainda não criado) + `make demo` (F3) + o `cli.py` de F2 antes de escrever a config curada do paciente-demo, para ela referenciar `evidence_id`s reais, não fixtures.
- **F5 (fusion-and-alerting) — FECHADA nesta sessão (2026-07-23), Verifier PASS.** `tasks.md` criado (18 tarefas, 6 fases) e executado via 3 lotes de sub-agentes em background, sequenciais: Lote 1 (T1-T8, fundação+motor de fusão, commits `9dd7d1d`..`b44e52b`), Lote 2 (T9-T15, alerta SNS+API, commits `57e122c`..`7019f91`), Lote 3 (T16-T18, dashboard+config curada, commits `22a5808`..`cf613d0`). Decisão de curadoria confirmada com o usuário durante o Lote 3: caso de vitais do paciente-demo é CTU-UHB (FHR), não BIDMC — BIDMC exigiria implementar um segundo caso inteiro de F3 (loader/features/detectores próprios, nenhum existe hoje, ver correção na tabela de rastreabilidade acima), fora de escopo de F5; desencaixe narrativo (monitoramento fetal ao lado de queda de paciente adulto) aceito conscientemente, documentado em `pipelines/fusion/configs/demo.yaml`, consistente com AD-024. O Lote 3 não tinha acesso à ferramenta de sub-agente para despachar um Verifier realmente separado — rodou o "Standalone fallback" documentado em `references/sub-agents.md` (validação fresh-eyes pelo próprio agente que implementou T18; distinção registrada explicitamente em `validation.md`, não apresentada como equivalente). **Verifier, 1ª passada: FAIL** — sensor de discriminação (4 mutações) achou 2 mutantes sobreviventes (gaps de cobertura de teste em código de produção já correto, não bugs ao vivo): (1) `pipelines/fusion/hysteresis.py:41` — nenhum teste fixava a fronteira exata verde→vermelho (`threshold_vermelho + hysteresis = 0.75`); (2) `backend/app/routes.py:132` (`_is_confirmed`) — nenhum teste de integração real contra LocalStack cobria o caminho de leitura do DynamoDB. Candidatos a lição registrados: `L-036`/`L-037` em `.specs/LESSONS.md`. **Fix aplicado e re-verificado no mesmo dia (orquestrador, não um sub-agente novo, mesma ressalva de transparência)**: 2 testes novos adicionados (`backend/tests/fusion/test_hysteresis.py`, `backend/tests/integration/test_fusion_handler.py`), confirmados matando as mutações originais reaplicando-as manualmente e observando a falha antes de reverter (`git checkout --`, árvore confirmada limpa) — não assumido, checado de verdade. Commit `6466e46`. Gate final pós-fix: `make test` **489 passando, 0 falhas**, `make lint` limpo. `validation.md`/`tasks.md`/`spec.md` atualizados para refletir PASS (commit `e90330d`). **Único item ainda aberto (não bloqueador)**: inspeção visual real do dashboard Streamlit (T16/T17) num navegador nunca foi feita por um humano em nenhuma sessão — só smoke check de processo + `streamlit.testing.v1.AppTest` headless (0 exceções); fazer antes de gravar o vídeo de demonstração.
- **`best.pt` publicado — FECHADO nesta sessão (2026-07-23).** Os 4 passos pendentes anteriores foram todos concluídos pelo usuário e verificados: (1) `training/train_yolo_endoscapes.ipynb` rodado no Colab até o fim (100 épocas, não 50 — usuário ajustou `EPOCHS` antes de rodar), saída completa arquivada em `training/endoscapes_training_output/` (não commitada, `.gitignore` já cobre `training/`); (2) repositório público `AnaPRodrigues/endoscapes-surgical-detector` criado no Hugging Face — confirmado via `WebFetch` (`tree/main` lista `best.pt`, 22,5 MB); (3) `best.pt` da variante vencedora (`yolov8s`, mAP50-95 0.3837 vs 0.3622 do `yolov8n` — venceu nas 4 métricas) publicado lá — md5 de `models/best.pt` bate exatamente com `training/endoscapes_training_output/runs/finetune_yolov8s/weights/best.pt`; (4) `models/README.md` preenchido com data, hiperparâmetros, variante vencedora e a comparação completa das duas variantes. `make models-fetch` deve funcionar agora (não re-testado nesta sessão — o arquivo já está em `models/best.pt` localmente, então ninguém precisou rodar o fetch ainda).
- **Blockers**: none. Rede disponível; Docker funciona direto. LocalStack parado (F2/`training/` não precisam — 100% local/Colab, sem AWS).
- **Residual aceito em aws-foundation**: 2 mutantes sobreviventes (dívida de teste, não bugs) — teste de variável ausente em `main()` passa por acidente (comportamento de produção correto, só o teste não discrimina o mecanismo); paginação de `ensure_topic` nunca forçada por teste (risco latente que cresce com o nº de tópicos no Learner Lab ao longo do tempo — não bloqueador agora). 3 follow-ups de baixa prioridade registrados em `validation.md`, não agendados.
- **Ambiente**: grupo `docker` do usuário exige `sg docker -c '...'` até um logout/login completo aplicar a mudança de verdade (não foi mais necessário nesta sessão). Ativar `.venv` (`source .venv/bin/activate`) antes de `pytest`/`ruff`/`python`; `PYTHONPATH=backend` necessário fora do pytest.
- **Residual aceito na emenda F0**: 3 mutantes sobreviventes (não bloqueadores) — dupla chamada do BIDMC não verificável pelo harness de stub (limitação de teste, não do código); URFD sem teste de zip corrompido (paridade com lacuna já aceita no núcleo para ICBHI); overlap teórico de glob no BIDMC (`*.hea` vs `*n.hea`), não alcançável no fluxo sequencial atual.
- **Fontes verificadas (não re-checar)**: URFD zips em `https://fenix.ur.edu.pl/~mkepski/ds/data/{fall,adl}-NN-cam0-rgb.zip` (fall 01–30, adl 01–40) — HTTP 206, `application/zip`, magic `PK`. BIDMC via `wfdb.dl_database('bidmc', ...)` — 53 registros contíguos `bidmc01`..`bidmc53` confirmados via `get_record_list`; numerics = mesmo nome + sufixo `n`, fora do `RECORDS`. Endoscapes: `train/`(1212 img/5566 anot.)/`val/`(409/1733)/`test/`(312/1485) — 1933 imagens totais anotadas, batendo com AD-033; `train/` bruto tem 36694 jpgs (só os anotados importam para treino).
- **Residual aceito em F0 (núcleo)**: 4 mutantes sobreviventes pré-existentes (dívida de teste P2, não bugs) — ver validation.md.
- **Uncommitted files**: `training/` inteiro (novo, não commitado ainda), `.specs/STATE.md` (esta edição). Nada em `backend/` tocado.
- **Branch**: `feat/f3-vitals-anomaly` (contém F3 + reestruturação + F0 completa + aws-foundation + F4 completa + F1 completa (Verifier PASS) + F2 completa (Verifier PASS) + emenda `training/` em andamento; `main` só tem o commit inicial — estratégia de merge/rename a decidir).
- **Aberto (decisões futuras)**: estratégia de branch/merge para `main`; DATA-12 (checksum) diferido P3; fix opcional de VIDEO-10 (observabilidade CloudWatch, Minor, não agendado); roteiro exato das gravações de áudio de consulta para F2 P2/P3 (grupo define); onde treinar o classificador de áudio de F2 (pergunta pendente ao usuário, ver Next step); **gap real descoberto nesta sessão**: SpO2/oxigenação (Req.3) não tem pipeline nenhum apesar de AD-040/F0 já terem escolhido e baixado o BIDMC — implementar `pipelines/vitals/` para HR/SpO2 do BIDMC é trabalho futuro, não bloqueador (ver tabela de rastreabilidade); inspeção visual humana do dashboard Streamlit de F5 num navegador (ver bullet de F5); relatório técnico e vídeo de demonstração (≤15 min) — os 2 entregáveis finais, ainda não iniciados.

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
