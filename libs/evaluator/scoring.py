"""Shared scoring helpers (level bands, clamping).

Kept in its own module so both ``base_agent`` and ``aggregation`` can use it
without a circular import.
"""

SCORE_MIN: float = 1.0
SCORE_MAX: float = 7.0

# Lower-bound ladder. Ordered high -> low. A continuous score always falls in
# exactly one band (no dead-zones between e.g. 5.99 and 6.0).
LEVEL_BANDS: list[tuple[float, str]] = [
    (6.0, "Excelente"),
    (5.0, "Bueno"),
    (4.0, "Suficiente"),
    (SCORE_MIN, "Insuficiente"),
]

VALID_LEVELS: tuple[str, ...] = ("Excelente", "Bueno", "Suficiente", "Insuficiente")


def get_level_for_score(score: float) -> str:
    for low, level in LEVEL_BANDS:
        if score >= low:
            return level
    return "Insuficiente"


def clamp_score(score: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, score))
