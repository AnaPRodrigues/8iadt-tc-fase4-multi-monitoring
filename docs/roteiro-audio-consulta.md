# Roteiro de gravação — áudio de consulta

As análises de **transcrição**, **termos clínicos críticos**, **sentimento** e
**sinais de fadiga vocal** (`pipelines/audio/transcribe.py`,
`critical_terms.py`, `sentiment.py`, `fatigue_score.py`) precisam de uma
gravação real de fala em português — é o único dado do projeto sem substituto
automático (todo o resto vem de datasets abertos ou é gerado
sinteticamente). Este roteiro é só para orientar a gravação; nenhum código
depende deste arquivo.

## O que gravar

**Grave pelo menos 2 áudios curtos** (não 1). O score de fadiga vocal compara
cada gravação com as demais da mesma execução — com um único áudio essa
comparação degenera e o score fica sempre zero (ver
`.specs/features/audio-analysis/design.md` § Risks & Concerns).

- **Formato**: WAV ou MP3, fala em português, uma pessoa falando (não precisa
  ser diálogo).
- **Duração sugerida**: 30–60 segundos cada.
- **Conteúdo**: uma fala simulando um paciente relatando sintomas numa consulta
  — não precisa ser um roteiro decorado, só cobrir os pontos abaixo.

## Pontos a cobrir na fala

Inclua, em algum momento da gravação, pelo menos um dos termos clínicos
críticos já configurados (`pipelines/audio/critical_terms.py`), para que a
busca de termos tenha algo real para encontrar:

- "dor no peito"
- "falta de ar"
- "tontura"

Exemplo de fala (adapte livremente, não precisa ser literal):

> "Bom dia, doutora. Eu queria falar sobre uns sintomas que apareceram essa
> semana. Tive um pouco de falta de ar quando subi a escada de casa, e ontem
> senti uma tontura ao levantar da cama. Não senti dor no peito, mas fiquei
> preocupado. Também notei que ando mais cansado que o normal."

## Variação entre as gravações (opcional, mas recomendada)

Para que o painel mostre a variação de sentimento/fadiga entre gravações, vale
gravar a segunda com um tom diferente da primeira — por exemplo, uma mais
calma e outra mais ofegante/preocupada. Isso não é obrigatório: mesmo duas
gravações parecidas já resolvem o problema do baseline degenerado.

## Depois de gravar

Não há um alvo de `Makefile` para isso — os arquivos entram no sistema pelo
envio de arquivo do paciente (modalidade "áudio"), do mesmo jeito que qualquer
outro envio. Quando os áudios existirem, quem for demonstrar a fatiga vocal
(P3 de F2) decide se cria um paciente de demonstração dedicado ou reaproveita
um dos criados por `make seed-demo` (ver seção 4 de
`docs/relatorio-tecnico.md`).
