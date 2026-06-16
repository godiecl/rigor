"""Pydantic models that define the structured output of the judge.

The models are the single source of truth: the function-calling JSON schema is
*generated* from them (so tool definition and runtime validation never drift),
and the model's tool-call arguments are validated back into typed objects via
``model_validate``.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from .scoring import SCORE_MAX, SCORE_MIN

# Keys pydantic emits that OpenAI strict structured-output / function calling
# rejects (numeric bounds, titles, defaults). We validate those at runtime with
# pydantic instead of relying on the provider to enforce them.
_STRICT_UNSUPPORTED_KEYS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "title",
    "default",
    "format",
)


class CriterionEvaluation(BaseModel):
    """One specialist judge's verdict for a single rubric criterion."""

    score: float = Field(
        ge=SCORE_MIN,
        le=SCORE_MAX,
        description="Puntaje de 1.0 a 7.0 en pasos de 0.5 (1.0, 1.5, …, 7.0) según la rúbrica",
    )
    level: Literal["Excelente", "Bueno", "Suficiente", "Insuficiente"] = Field(
        description="Nivel cualitativo correspondiente al puntaje"
    )
    justification: str = Field(description="Justificación detallada del puntaje asignado")
    evidence: list[str] = Field(
        description="Fragmentos textuales citados del documento que respaldan la evaluación"
    )
    strengths: list[str] = Field(
        description="Fortalezas identificadas en el criterio evaluado"
    )
    weaknesses: list[str] = Field(
        description="Debilidades o áreas de mejora identificadas"
    )
    improvements: list[str] = Field(
        description="Recomendaciones específicas de mejora"
    )


def _strip_for_strict(node: Any) -> Any:
    """Recursively make a pydantic JSON schema OpenAI-strict compatible.

    - drops keywords strict mode rejects (numeric bounds, title, default, ...)
    - forces ``additionalProperties: false`` on every object
    - marks every property ``required`` (strict mode requires this)
    """
    if isinstance(node, dict):
        cleaned = {
            k: _strip_for_strict(v)
            for k, v in node.items()
            if k not in _STRICT_UNSUPPORTED_KEYS
        }
        if cleaned.get("type") == "object" and "properties" in cleaned:
            cleaned["additionalProperties"] = False
            cleaned["required"] = list(cleaned["properties"].keys())
        return cleaned
    if isinstance(node, list):
        return [_strip_for_strict(item) for item in node]
    return node


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Build an OpenAI-strict JSON schema dict from a pydantic model."""
    return _strip_for_strict(model.model_json_schema())
