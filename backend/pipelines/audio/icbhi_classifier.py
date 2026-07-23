"""Classificador respiratório leve: split sem vazamento de paciente, treino e predição.

Split feito por ``GroupShuffleSplit`` agrupado por ``patient_id`` — nunca por ciclo
solto — para não deixar o mesmo paciente aparecer em treino e teste, o que inflaria
precision/recall artificialmente.
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit

from pipelines.audio.icbhi_features import extract
from pipelines.audio.models import Prediction, RespiratoryCycle

IcbhiClassifier = RandomForestClassifier

N_ESTIMATORS = 200


def split_by_patient(
    cycles: list[RespiratoryCycle], test_size: float, seed: int
) -> tuple[list[RespiratoryCycle], list[RespiratoryCycle]]:
    """Divide os ciclos em treino/teste agrupando por ``patient_id`` (sem vazamento)."""
    groups = [c.patient_id for c in cycles]
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_idx, test_idx = next(splitter.split(cycles, groups=groups))
    treino = [cycles[i] for i in train_idx]
    teste = [cycles[i] for i in test_idx]
    return treino, teste


def train(cycles: list[RespiratoryCycle], seed: int) -> IcbhiClassifier:
    """Treina o RandomForest sobre os vetores de features dos ciclos fornecidos.

    ``class_weight="balanced"`` absorve o desbalanceamento natural das classes do
    ICBHI sem reamostragem manual.
    """
    x = np.array([extract(c) for c in cycles])
    y = [c.label for c in cycles]
    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS, class_weight="balanced", random_state=seed
    )
    model.fit(x, y)
    return model


def predict(model: IcbhiClassifier, cycle: RespiratoryCycle) -> Prediction:
    """Prediz a classe do ciclo e a confiança (probabilidade da classe vencedora)."""
    x = extract(cycle).reshape(1, -1)
    probs = model.predict_proba(x)[0]
    idx = int(np.argmax(probs))
    return Prediction(
        record_id=cycle.record_id,
        cycle_index=cycle.cycle_index,
        predicted_label=str(model.classes_[idx]),
        confidence=float(probs[idx]),
    )
