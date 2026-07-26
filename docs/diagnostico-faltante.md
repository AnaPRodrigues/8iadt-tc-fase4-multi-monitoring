# Diagnóstico — o que falta para o Tech Challenge (Fase 4)

**Data:** 2026-07-24
**Branch:** `feat/f3-vitals-anomaly`
**Testes:** 475 passando, 3 skipped, zero falhas

---

## Estado geral

O projeto está **maduro e quase completo**. A reformulação de 6 blocos (AD-048 a
AD-053) está fechada, o frontend React compila sem erros e os 3 pacientes de
demonstração (`make seed-demo`) cobrem 5 dos 6 datasets reais.

---

## Lacunas reais

### 🟡 Não bloqueador — documentado como trabalho futuro

| Lacuna | Detalhe | Requisito |
|---|---|---|
| **Pressão arterial** | VitalDB (94 GB) inviável no prazo. AD-041. | Req.3 (exemplo) |
| **Disartria** | Coberta parcialmente pelo Laryngeal Voice Disorder. Sem dataset de disartria específica em pt-BR. | Req.2 |

### Estratégia para o áudio de consulta (sem gravação)

O grupo **não quer gravar**. Solução em duas camadas:

| Camada | Dataset | O que valida |
|---|---|---|
| **Voz humana real em pt-BR** | Common Voice PT-BR (~200 MB) | Transcrição (faster-whisper) com fala real |
| **Pipeline completo ponta a ponta** | TTS sintético (edge-tts, pt-BR) | Áudio → transcrição → termos → sentimento → fadiga num fluxo único |

A validação com voz humana real fica no Common Voice; o fluxo completo de
"consulta" é demonstrado com áudio sintetizado a partir de frases clínicas.
Ambos são 100% programáticos — zero gravação.

---

## Novos datasets (todos leves, todos programáticos)

| # | Dataset | Tam. | Fonte | Pipeline |
|---|---|---|---|---|
| 1 | **Common Voice PT-BR** | ~200 MB | Hugging Face | `transcribe.py` — áudio pt-BR real |
| 2 | **Laryngeal Voice Disorder** | ~250 MB | Kaggle | `acoustic_features.py` / `fatigue_score.py` |
| 3 | **UI-PRMD Skeleton** | < 50 MB | GitHub mirrors | `pose_features.py` — fisioterapia |
| 4 | **KIMORE JSON** | ~300 MB | Google Drive | `pose_features.py` — paciente real |
| 5 | **SemClinBr** | < 20 MB | Artigo / GitHub | `critical_terms.py` / `sentiment.py` |
| 6 | **TTS — consulta sintética** | 0 MB (gerado) | edge-tts | Pipeline completo de áudio (ponta a ponta) |

**Total:** ~820 MB de downloads + TTS gerado sob demanda.

Detalhes de cada dataset em [`docs/novos-datasets.md`](novos-datasets.md).

---

## Entregáveis obrigatórios

| Entregável | Estado | O que falta |
|---|---|---|
| **Código-fonte completo** | ✅ Versionado | Merge para `main` |
| **Relatório técnico** | 🟡 Rascunho pronto | Revisão final humana |
| **Vídeo de demonstração ≤ 15 min** | ⏳ Pendente | Depende de: datasets baixados, TTS integrado, inspeção visual do painel |

---

## Itens de verificação

### 1. Baixar os novos datasets

```bash
# Common Voice PT-BR — script pronto (ver docs/novos-datasets.md)
python scripts/baixar_common_voice_ptbr.py

# Demais: download manual do Kaggle / Google Drive / GitHub
```

### 2. Integrar TTS de consulta sintética

Usar `edge-tts` (gratuito, sem API key, voz pt-BR feminina/masculina) para gerar
≥ 2 áudios de consulta a partir de frases com vocabulário clínico:

```
"Bom dia doutora. Tive falta de ar subindo a escada e uma tontura ao levantar.
Não senti dor no peito, mas estou preocupada."
```

O áudio gerado passa pelo pipeline completo: faster-whisper → critical_terms →
sentiment → fatigue_score. A origem sintética fica documentada no relatório.

### 3. Inspeção visual do painel React

```bash
make serve-api      # Terminal 1 — http://localhost:8000
make serve-front    # Terminal 2 — http://localhost:5173
```

Verificar as 3 telas com `make seed-demo`.

### 4. Merge para `main`

```bash
git checkout main && git merge feat/f3-vitals-anomaly
```

### 5. Testar `make models-fetch`

```bash
rm models/best.pt && make models-fetch
```

---

## Ordem recomendada

1. **Baixar Common Voice PT-BR + Laryngeal Voice** (script + Kaggle)
2. **Integrar TTS edge-tts** — gerar áudios de consulta sintéticos e rodar pipeline
3. **Baixar UI-PRMD + KIMORE** se quiser o ângulo fisioterapia
4. **Inspecionar painel visualmente** no navegador
5. **Rever relatório técnico** — incluir novos datasets e estratégia TTS
6. **Gravar vídeo de demonstração** (≤ 15 min)
7. **Merge para `main`**

---

## Referências

| Documento | Conteúdo |
|---|---|
| [`docs/8IADT-Fase-4-Tech-challenge.md`](8IADT-Fase-4-Tech-challenge.md) | Enunciado original |
| [`docs/relatorio-tecnico.md`](relatorio-tecnico.md) | Relatório técnico |
| [`docs/novos-datasets.md`](novos-datasets.md) | Detalhe dos datasets e script Common Voice |
| [`.specs/STATE.md`](../.specs/STATE.md) | Decisões de arquitetura (AD-001 a AD-053) |
| [`README.md`](../README.md) | Visão geral e comandos |
