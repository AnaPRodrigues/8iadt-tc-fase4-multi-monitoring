"""Tratamento de perda de sinal antes da detecção.

Perda de sinal é endêmica em cardiotocografia: o transdutor se desloca e o FHR é
gravado como zero. Se esses zeros chegarem aos detectores como valores reais, viram
outliers espúrios e produzem falsos positivos em massa — o risco registrado no design.

SPEC_DEVIATION: o design assinava ``interpolate_gaps(signal, mask, max_gap_s) -> ndarray``.
Faltava ``fs`` (sem ele não dá para converter segundos em amostras) e o retorno precisa
incluir a máscara atualizada — gaps longos continuam inválidos, e sem isso o chamador não
teria como saber quais amostras ainda não são confiáveis.
"""

import numpy as np


def mark_signal_loss(signal: np.ndarray) -> np.ndarray:
    """Marca amostras inválidas: ``True`` onde há dropout.

    Considera zero e NaN como perda. **Aplicável ao FHR**, onde zero só pode ser
    dropout do transdutor. Não aplique cegamente ao UC: ausência de contração é
    legitimamente zero e seria descartada como se fosse falha de sinal.
    """
    signal = np.asarray(signal, dtype=float)
    return (signal == 0.0) | np.isnan(signal)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Intervalos ``[início, fim)`` contíguos de ``True`` na máscara."""
    runs: list[tuple[int, int]] = []
    inicio: int | None = None
    for i, invalido in enumerate(mask):
        if invalido and inicio is None:
            inicio = i
        elif not invalido and inicio is not None:
            runs.append((inicio, i))
            inicio = None
    if inicio is not None:
        runs.append((inicio, len(mask)))
    return runs


def interpolate_gaps(
    signal: np.ndarray, mask: np.ndarray, max_gap_s: float, fs: float
) -> tuple[np.ndarray, np.ndarray]:
    """Interpola linearmente os gaps curtos; devolve ``(sinal, máscara atualizada)``.

    Um gap só é preenchido quando (a) sua duração não passa de ``max_gap_s`` e
    (b) existem amostras válidas dos dois lados. Gaps nas bordas não têm âncora e
    permanecem inválidos: extrapolar ali seria fabricar dado, não recuperá-lo.
    """
    saida = np.array(signal, dtype=float, copy=True)
    nova_mask = np.array(mask, dtype=bool, copy=True)
    if saida.size == 0:
        return saida, nova_mask

    max_amostras = int(max_gap_s * fs)

    for inicio, fim in _runs(nova_mask):
        na_borda = inicio == 0 or fim == len(saida)
        if na_borda or (fim - inicio) > max_amostras:
            continue

        esquerda, direita = inicio - 1, fim
        passo = (saida[direita] - saida[esquerda]) / (direita - esquerda)
        for i in range(inicio, fim):
            saida[i] = saida[esquerda] + passo * (i - esquerda)
        nova_mask[inicio:fim] = False

    return saida, nova_mask
