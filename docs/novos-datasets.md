# Novos datasets — resumo e uso no projeto

**Data:** 2026-07-24

Cada dataset cobre uma etapa específica do pipeline. Nenhum sozinho fecha o ciclo
completo (áudio em pt-BR + vocabulário clínico + patologia vocal), mas **juntos**
validam cada etapa em português com dados reais.

---

## Tabela consolidada

| # | Dataset | Tamanho | Fonte | Pipeline exercitado |
|---|---|---|---|---|
| 1 | **Laryngeal Voice Disorder** | ~250 MB | Kaggle | `acoustic_features.py` / `fatigue_score.py` |
| 2 | **Common Voice PT-BR** | ~200 MB | Hugging Face | `transcribe.py` (áudio pt-BR real) |
| 3 | **SemClinBr** | < 20 MB | Artigo / GitHub | `critical_terms.py` / `sentiment.py` |
| 4 | **UI-PRMD Skeleton** | < 50 MB | GitHub mirrors | `pose_detector.py` / `pose_features.py` |
| 5 | **KIMORE JSON** | ~300 MB | Google Drive / GitHub | `pose_detector.py` / `pose_features.py` |

**Total:** ~820 MB

---

## Detalhe de cada dataset

### 1. Laryngeal Voice Disorder — ~250 MB

| Item | Detalhe |
|---|---|
| **O que é** | Subconjunto curado do SVD alemão com gravações WAV de vozes saudáveis (30) e patológicas (30: disfonia, nódulos, paralisia vocal) |
| **Uso no projeto** | Roda `acoustic_features.py` (jitter, shimmer, HNR via Parselmouth) sobre os áudios e classifica saudável vs. patológico via `fatigue_score.py`. As features acústicas são independentes da língua — funciona em alemão, português, qualquer língua |
| **O que fecha** | Lacuna de **disartria/fadiga vocal com rótulo real** (enunciado Req.2: "alterações vocais indicativas de condições médicas") |
| **Baixar** | Kaggle (`sree14hari/svd-dataset` ou similar) |
| **Limitação** | Alemão, vogais sustentadas (não fala contínua). Só valida a camada acústica, não transcrição/termos |

### 2. Common Voice PT-BR — ~200 MB

| Item | Detalhe |
|---|---|
| **O que é** | Subconjunto de validação do Common Voice 11.0 em português. Fala real de pessoas lendo frases (domínio geral). 20 amostras bastam para validar o pipeline |
| **Uso no projeto** | Roda `transcribe.py` (faster-whisper pt-BR) sobre os áudios e verifica se o output é texto legível em português. Também alimenta `acoustic_features.py` para ter baseline de voz saudável em pt-BR |
| **O que fecha** | **Transcrição em português com áudio real** — antes só tinha o ICBHI (sem fala) e o faster-whisper nunca foi exercitado com pt-BR real |
| **Baixar** | Script pronto (ver seção abaixo). `load_dataset("mozilla-foundation/common_voice_11_0", "pt", split="validation[:20]")` |
| **Limitação** | Domínio geral (frases da Wikipedia). Não contém vocabulário clínico — "dor no peito", "falta de ar" etc. não aparecem. Os léxicos de termos/sentimento não vão casar |

### 3. SemClinBr — < 20 MB

| Item | Detalhe |
|---|---|
| **O que é** | 1.000 notas clínicas reais em português brasileiro, anotadas com 65.117 entidades (sintomas, diagnósticos, tratamentos, exames). Publicado no Journal of Biomedical Semantics (2022) |
| **Uso no projeto** | Roda `critical_terms.py` e `sentiment.py` sobre frases clínicas reais em pt-BR. Os léxicos ("dor no peito", "falta de ar", "tontura") vão casar com as notas, validando que a extração de termos e sentimento funciona com vocabulário clínico real |
| **O que fecha** | **Extração de termos críticos e sentimento em pt-BR com contexto clínico real** — antes os léxicos só eram testados com texto sintético |
| **Baixar** | Artigo: `jbiomedsem.biomedcentral.com/articles/10.1186/s13326-022-00269-1`. Dataset sob licença acadêmica |
| **Limitação** | É **texto puro**, não áudio. Não exerce o pipeline de transcrição (não passa pelo faster-whisper). Valida só a camada de NLP |

### 4. UI-PRMD Skeleton — < 50 MB

| Item | Detalhe |
|---|---|
| **O que é** | Posições 3D (mm) e ângulos articulares (graus) de 10 sujeitos executando 10 exercícios de fisioterapia, cada um com execução correta e incorreta. Formato CSV. Capturado com Vicon (gold standard) + Kinect |
| **Uso no projeto** | Converte os CSVs de posições 3D para o formato de keypoints do MediaPipe e roda `pose_features.py` (amplitude, velocidade, assimetria) para classificar execução correta vs. incorreta com threshold de desvio angular |
| **O que fecha** | **Fisioterapia — desvio angular em exercício** (enunciado Req.1: "análise postural / fisioterapia"). Antes só tinha URFD (queda/ADL genérico) |
| **Baixar** | Site oficial caiu (`webpages.uidaho.edu/ui-prmd` → 404). Mirrors via Google Drive nos repositórios STGCN-rehab do GitHub |
| **Limitação** | Só 10 sujeitos saudáveis (sem paciente real com patologia). Sem RGB — só esqueleto numérico |

### 5. KIMORE JSON — ~300 MB

| Item | Detalhe |
|---|---|
| **O que é** | Dados de esqueleto 3D (Kinect v2) de 78 sujeitos: 44 saudáveis + 34 com disfunção motora real (AVC, Parkinson, lombalgia). 5 exercícios de fisioterapia para lombar. Formato JSON. Publicado em IEEE TNSRE (2019) |
| **Uso no projeto** | Mesmo pipeline do UI-PRMD: keypoints → `pose_features.py` → classificação. A diferença é que aqui há **pacientes reais com patologia**, permitindo demonstrar que o sistema distingue movimento saudável de movimento patológico |
| **O que fecha** | **Fisioterapia com pacientes reais** — complementa o UI-PRMD (que só tem saudáveis executando errado de propósito). Juntos cobrem: desvio angular (UI-PRMD) + padrão patológico real (KIMORE) |
| **Baixar** | Google Drive (link no artigo da IEEE). Wrapper: `github.com/petteriTeikari/KiMoRe_wrapper` (conversão JSON → HDF5/MAT) |
| **Limitação** | Só esqueleto (sem RGB para demonstração visual). Requer baixar do Google Drive e extrair só os JSONs |

---

## Como os datasets se complementam

```
                         ┌─────────────────────────────────────┐
                         │         PIPELINE DE ÁUDIO           │
                         ├─────────────────────────────────────┤
Common Voice PT-BR ──────┤ áudio pt-BR → faster-whisper →     │ transcrição ✅
                         │                 transcript          │
SemClinBr (texto) ───────┤ texto clínico pt-BR → léxicos →    │ termos + sentimento ✅
                         │                 critical_terms.py   │
Laryngeal Voice ─────────┤ áudio patológico → Parselmouth →   │ fadiga vocal ✅
                         │                 fatigue_score.py    │
ICBHI (já existe) ───────┤ áudio respiratório → RF →          │ crackle/wheeze ✅
                         │                 icbhi_classifier.py │
                         └─────────────────────────────────────┘

                         ┌─────────────────────────────────────┐
                         │         PIPELINE DE VÍDEO           │
                         ├─────────────────────────────────────┤
UI-PRMD Skeleton ────────┤ CSV posições 3D → MediaPipe →      │ desvio angular ✅
                         │                 pose_features.py    │
KIMORE JSON ────────────┤ JSON esqueleto → MediaPipe →        │ padrão patológico ✅
                         │                 pose_features.py    │
URFD (já existe) ────────┤ PNG sequência → MediaPipe →        │ queda/ADL ✅
                         │                 pose_detector.py    │
Endoscapes (já existe) ──┤ JPG cirúrgico → YOLOv8 →          │ estruturas críticas ✅
                         │                 object_detector.py  │
                         └─────────────────────────────────────┘
```

---

## O que **ainda** falta após adicionar estes datasets

| Lacuna | Resolvida? |
|---|---|
| Transcrição de áudio em pt-BR | ✅ Common Voice — áudio real em português |
| Termos críticos / sentimento em pt-BR | 🟡 SemClinBr — texto clínico real, mas **sem áudio** (não exerce transcrição) |
| Fadiga vocal / disartria com rótulo | ✅ Laryngeal Voice — patologia vocal real |
| Fisioterapia — desvio angular | ✅ UI-PRMD — exercício correto vs. incorreto |
| Fisioterapia — paciente real | ✅ KIMORE — AVC, Parkinson, lombalgia |
| **Áudio de consulta completo** (fala pt-BR + vocabulário clínico + patologia num só fluxo) | ❌ Continua pendente. A gravação do grupo conforme `docs/roteiro-audio-consulta.md` é o único jeito |

---

## Script de download — Common Voice PT-BR

```python
import os
from datasets import load_dataset

def baixar_common_voice_ptbr():
    output_dir = "data/medical_consult_pt"
    os.makedirs(output_dir, exist_ok=True)

    print("Baixando amostra de áudio em PT-BR para teste de transcrição...")
    ds = load_dataset(
        "mozilla-foundation/common_voice_11_0",
        "pt",
        split="validation[:20]",
    )

    for i, item in enumerate(ds):
        audio_path = os.path.join(output_dir, f"consulta_ptbr_{i:03d}.wav")
        with open(audio_path, "wb") as f:
            f.write(item["audio"]["bytes"])

    print(f"Sucesso! {len(ds)} áudios baixados em {output_dir}/")

if __name__ == "__main__":
    baixar_common_voice_ptbr()
```

---

## Prioridade de adoção

| Prioridade | Dataset | Justificativa |
|---|---|---|
| 🔴 1 | **Common Voice PT-BR** | Único que exerce transcrição em português com áudio real. Download 100% programático |
| 🔴 2 | **Laryngeal Voice** | Fecha fadiga vocal/disartria com rótulo real. Pipeline já existe (`acoustic_features.py`) |
| 🟡 3 | **UI-PRMD** | Leve (< 50 MB), fecha fisioterapia. Mas precisa garimpar mirror (site oficial caiu) |
| 🟡 4 | **KIMORE** | Complementa UI-PRMD com pacientes reais. Mas ~300 MB e precisa extrair JSONs manualmente |
| ⚪ 5 | **SemClinBr** | Valida léxicos com texto clínico real. Mas é opcional — o léxico já foi validado com texto sintético durante F2 |
