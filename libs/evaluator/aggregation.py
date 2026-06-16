from dataclasses import dataclass, field

from .base_agent import EvaluationResult
from .scoring import clamp_score, get_level_for_score

RELATED_CRITERION_PAIRS: list[tuple[str, str, float]] = [
    ("contextualizacion", "problema_objetivos", 2.0),
    ("problema_objetivos", "metodologia", 2.0),
    ("metodologia", "desarrollo_evidencias", 2.0),
    ("desarrollo_evidencias", "resultados", 2.5),
    ("resultados", "conclusiones", 2.0),
    ("redaccion_formato", "uso_etica_ia", 2.0),
]


@dataclass
class AggregatedResult:
    final_score: float
    final_level: str
    criterion_results: list[EvaluationResult]
    errors: list[str] = field(default_factory=list)
    is_partial: bool = False
    failed_criteria: list[str] = field(default_factory=list)
    evaluated_weight: float = 1.0


@dataclass
class ConsistencyWarning:
    criterion_a: str
    criterion_b: str
    score_a: float
    score_b: float
    max_diff: float
    actual_diff: float
    message: str


def aggregate_scores(results: list[EvaluationResult]) -> AggregatedResult:
    errors: list[str] = []
    failed_criteria: list[str] = []
    valid_results: list[EvaluationResult] = []
    total_weight = 0.0

    for r in results:
        if r.error:
            errors.append(f"{r.criterion}: {r.error}")
            failed_criteria.append(r.criterion)
        elif r.score < 1.0 or r.score > 7.0:
            errors.append(f"{r.criterion}: score {r.score} fuera de rango 1.0-7.0")
            failed_criteria.append(r.criterion)
        else:
            valid_results.append(r)
            total_weight += r.weight

    if total_weight == 0.0:
        return AggregatedResult(
            final_score=0.0,
            final_level="Error",
            criterion_results=results,
            errors=errors,
            is_partial=True,
            failed_criteria=failed_criteria,
            evaluated_weight=0.0,
        )

    if abs(total_weight - 1.0) > 0.001:
        errors.append(f"Pesos no suman 1.0 (suman {total_weight:.3f}). Normalizando.")

    # When some criteria fail, the final score is renormalized over the
    # surviving weight. That makes it *partial*: it cannot be compared 1:1 with a
    # complete evaluation, so we flag it explicitly rather than hide it behind a
    # clean-looking number.
    is_partial = bool(failed_criteria)
    if is_partial:
        covered = total_weight * 100
        errors.append(
            f"Evaluación PARCIAL: solo se evaluó {covered:.0f}% de la ponderación; "
            f"criterios sin nota: {', '.join(failed_criteria)}. "
            "El puntaje final está renormalizado sobre los criterios válidos."
        )

    weighted_sum = sum(r.score * r.weight for r in valid_results)
    final_score = clamp_score(weighted_sum / total_weight)

    return AggregatedResult(
        final_score=final_score,
        final_level=get_level_for_score(final_score),
        criterion_results=results,
        errors=errors,
        is_partial=is_partial,
        failed_criteria=failed_criteria,
        evaluated_weight=total_weight,
    )


def check_consistency(results: list[EvaluationResult]) -> list[ConsistencyWarning]:
    warnings: list[ConsistencyWarning] = []
    score_map = {r.criterion: r.score for r in results if not r.error}

    for criterion_a, criterion_b, max_diff in RELATED_CRITERION_PAIRS:
        if criterion_a in score_map and criterion_b in score_map:
            diff = abs(score_map[criterion_a] - score_map[criterion_b])
            if diff > max_diff:
                warnings.append(
                    ConsistencyWarning(
                        criterion_a=criterion_a,
                        criterion_b=criterion_b,
                        score_a=score_map[criterion_a],
                        score_b=score_map[criterion_b],
                        max_diff=max_diff,
                        actual_diff=diff,
                        message=(
                            f"Discrepancia entre '{criterion_a}' ({score_map[criterion_a]:.1f}) "
                            f"y '{criterion_b}' ({score_map[criterion_b]:.1f}): "
                            f"diferencia de {diff:.1f} puntos (máx. esperado: {max_diff:.1f})"
                        ),
                    )
                )

    return warnings
