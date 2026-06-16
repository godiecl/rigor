from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .aggregation import AggregatedResult, ConsistencyWarning
from .agents import get_criterion_display_names


@dataclass
class ReportData:
    document_name: str
    model: str
    aggregated: AggregatedResult
    consistency_warnings: list[ConsistencyWarning]
    usage: dict[str, Any] | None = None
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


def _level_emoji(level: str) -> str:
    return {
        "Excelente": "🟢",
        "Bueno": "🔵",
        "Suficiente": "🟡",
        "Insuficiente": "🔴",
        "Error": "⚫",
    }.get(level, "⚪")


def _format_score(score: float) -> str:
    return f"{score:.2f}"


def generate_markdown_report(data: ReportData) -> str:
    names = get_criterion_display_names()
    lines: list[str] = []
    agg = data.aggregated
    emoji = _level_emoji(agg.final_level)

    lines.append(f"# Evaluación: {data.document_name}")
    lines.append("")
    lines.append(
        f"**Puntaje Final:** {_format_score(agg.final_score)} / 7.0 — {emoji} **{agg.final_level}**"
    )
    lines.append("")
    lines.append(f"**Modelo:** {data.model}")
    lines.append(f"**Generado:** {data.generated_at}")
    lines.append("")

    if agg.is_partial:
        lines.append(
            f"> ⚠️ **Evaluación parcial.** Solo se evaluó "
            f"{agg.evaluated_weight:.0%} de la ponderación total. "
            f"Criterios sin nota: {', '.join(agg.failed_criteria) or '—'}. "
            "El puntaje final está renormalizado y no es directamente comparable "
            "con una evaluación completa."
        )
        lines.append("")

    flagged = [r for r in agg.criterion_results if r.validation_flags]
    if flagged:
        lines.append(
            f"> 🚩 **{len(flagged)} criterio(s) marcados para revisión humana** "
            "por alertas de validación automática (ver detalle por criterio)."
        )
        lines.append("")

    if agg.errors:
        lines.append("## ⚠️ Errores")
        for err in agg.errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.append("## Desglose por Criterio")
    lines.append("")
    lines.append("| Criterio | Peso | Score | Nivel |")
    lines.append("|----------|------|-------|-------|")

    for r in agg.criterion_results:
        display = names.get(r.criterion, r.criterion)
        level_emoji = _level_emoji(r.level if not r.error else "Error")
        if r.error:
            lines.append(f"| {display} | {r.weight:.0%} | — | ⚫ Error: {r.error} |")
        else:
            lines.append(
                f"| {display} | {r.weight:.0%} | {_format_score(r.score)} | {level_emoji} {r.level} |"
            )
    lines.append(
        f"| **Total ponderado** | **100%** | **{_format_score(agg.final_score)}** | **{emoji} {agg.final_level}** |"
    )
    lines.append("")

    lines.append("## Análisis Detallado")
    lines.append("")

    for i, r in enumerate(agg.criterion_results):
        display = names.get(r.criterion, r.criterion)
        level_emoji = _level_emoji(r.level if not r.error else "Error")
        lines.append(f"### {i + 1}. {display} ({r.weight:.0%})")
        lines.append("")

        if r.error:
            lines.append(f"**Error:** {r.error}")
            lines.append("")
            continue

        lines.append(f"**Score:** {_format_score(r.score)} — {level_emoji} {r.level}")
        lines.append("")
        lines.append(f"**Justificación:** {r.justification}")
        lines.append("")

        if r.evidence:
            lines.append("**Evidencia citada:**")
            pages = r.evidence_pages or [None] * len(r.evidence)
            for ev, page in zip(r.evidence, pages):
                cite = f"📄 p. {page}" if page else "📄 página no localizada"
                lines.append(f"- _{ev}_ ({cite})")
            lines.append("")

        if r.strengths:
            lines.append("**Fortalezas:**")
            for s in r.strengths:
                lines.append(f"- ✅ {s}")
            lines.append("")

        if r.weaknesses:
            lines.append("**Debilidades:**")
            for w in r.weaknesses:
                lines.append(f"- ❌ {w}")
            lines.append("")

        if r.improvements:
            lines.append("**Recomendaciones de mejora:**")
            for imp in r.improvements:
                lines.append(f"- 💡 {imp}")
            lines.append("")

        if r.validation_flags:
            lines.append("**🚩 Alertas de validación (revisión humana sugerida):**")
            for flag in r.validation_flags:
                lines.append(f"- {flag}")
            lines.append("")

    if data.consistency_warnings:
        lines.append("## ⚠️ Advertencias de Consistencia")
        lines.append("")
        for w in data.consistency_warnings:
            lines.append(f"- {w.message}")
        lines.append("")

    if data.usage:
        lines.append("## Uso de Tokens")
        lines.append("")
        lines.append(f"- **Prompt tokens:** {data.usage.get('prompt_tokens', 'N/A')}")
        lines.append(
            f"- **Completion tokens:** {data.usage.get('completion_tokens', 'N/A')}"
        )
        lines.append(f"- **Total tokens:** {data.usage.get('total_tokens', 'N/A')}")
        cost = data.usage.get("estimated_cost_usd")
        if cost is not None:
            lines.append(f"- **Costo estimado:** ${cost:.4f} USD")
        lines.append("")

    return "\n".join(lines)


def generate_json_report(data: ReportData) -> dict[str, Any]:
    names = get_criterion_display_names()

    return {
        "document": data.document_name,
        "model": data.model,
        "generated_at": data.generated_at,
        "final_score": round(data.aggregated.final_score, 2),
        "final_level": data.aggregated.final_level,
        "is_partial": data.aggregated.is_partial,
        "evaluated_weight": round(data.aggregated.evaluated_weight, 4),
        "failed_criteria": data.aggregated.failed_criteria,
        "needs_review": any(
            r.validation_flags for r in data.aggregated.criterion_results
        ),
        "criterions": [
            {
                "id": r.criterion,
                "name": names.get(r.criterion, r.criterion),
                "weight": r.weight,
                "score": r.score if not r.error else None,
                "level": r.level if not r.error else None,
                "justification": r.justification,
                "evidence": [
                    {"quote": quote, "page": page}
                    for quote, page in zip(
                        r.evidence,
                        r.evidence_pages or [None] * len(r.evidence),
                    )
                ],
                "strengths": r.strengths,
                "weaknesses": r.weaknesses,
                "improvements": r.improvements,
                "validation_flags": r.validation_flags,
                "error": r.error,
            }
            for r in data.aggregated.criterion_results
        ],
        "consistency_warnings": [
            {
                "criterion_a": w.criterion_a,
                "criterion_b": w.criterion_b,
                "score_a": w.score_a,
                "score_b": w.score_b,
                "max_expected_diff": w.max_diff,
                "actual_diff": round(w.actual_diff, 2),
                "message": w.message,
            }
            for w in data.consistency_warnings
        ],
        "usage": data.usage,
    }
