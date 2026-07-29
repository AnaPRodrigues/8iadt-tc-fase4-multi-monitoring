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
    * **OpenPose** para análise postural.
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
