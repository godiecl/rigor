"""Post-hoc failsafes for a single criterion verdict.

These run *after* the model responds and cost no extra API calls. They don't
change the score — they attach warning flags that mark a verdict as needing
human review. The headline check is evidence grounding: a judge that cites
quotes which don't appear in the document is hallucinating, the most damaging
failure mode for an LLM-as-judge.
"""

import re

from .base_agent import EvaluationResult
from .scoring import get_level_for_score

# Below this normalized-overlap ratio an evidence quote is treated as not found
# in the source (accounts for minor PDF-extraction whitespace/punctuation drift).
_EVIDENCE_MATCH_THRESHOLD = 0.85
_MIN_JUSTIFICATION_CHARS = 40


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace/punctuation for tolerant matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_grounded(quote: str, normalized_source: str) -> bool:
    norm_quote = _normalize(quote)
    if not norm_quote:
        return False
    if norm_quote in normalized_source:
        return True
    # Fall back to token-window overlap so a near-verbatim quote with a dropped
    # word or extraction artifact isn't flagged as fabricated.
    tokens = norm_quote.split()
    if len(tokens) < 4:
        return False
    source_tokens = set(normalized_source.split())
    hits = sum(1 for t in tokens if t in source_tokens)
    return (hits / len(tokens)) >= _EVIDENCE_MATCH_THRESHOLD


def validate_result(result: EvaluationResult, source_text: str) -> list[str]:
    """Return a list of warning messages; empty means the verdict looks sound."""
    if result.error:
        return []

    flags: list[str] = []
    normalized_source = _normalize(source_text)

    # 1. Evidence grounding — the core anti-hallucination check.
    ungrounded = [q for q in result.evidence if not _is_grounded(q, normalized_source)]
    if ungrounded:
        sample = ungrounded[0][:80]
        flags.append(
            f"posible cita fabricada: {len(ungrounded)}/{len(result.evidence)} "
            f'fragmentos de evidencia no se encontraron en el documento (ej.: "{sample}…")'
        )

    # 2. Score must sit in the band its level claims (defends against a model
    #    that returns an out-of-band level even after our recompute).
    if result.level != get_level_for_score(result.score):
        flags.append(
            f"nivel '{result.level}' no corresponde al puntaje {result.score:.1f}"
        )

    # 3. Structural coherence between the score and the qualitative fields.
    if result.score >= 6.0 and not result.strengths:
        flags.append("puntaje alto (≥6.0) sin fortalezas declaradas")
    if result.score < 4.0 and not (result.weaknesses or result.improvements):
        flags.append("puntaje bajo (<4.0) sin debilidades ni mejoras declaradas")
    if not result.evidence:
        flags.append("evaluación sin evidencia citada")
    if len(result.justification.strip()) < _MIN_JUSTIFICATION_CHARS:
        flags.append("justificación demasiado breve para respaldar el puntaje")

    return flags
