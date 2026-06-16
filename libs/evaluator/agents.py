from .base_agent import CriterionAgent
from .prompts import (
    CONCLUSIONES_PROMPT,
    CONTEXTUALIZACION_PROMPT,
    DESARROLLO_EVIDENCIAS_PROMPT,
    METODOLOGIA_PROMPT,
    PROBLEMA_OBJETIVOS_PROMPT,
    REDACION_FORMATO_PROMPT,
    RESULTADOS_PROMPT,
    USO_IA_PROMPT,
)

CRITERION_DEFINITIONS: list[tuple[str, float, str]] = [
    ("contextualizacion", 0.10, CONTEXTUALIZACION_PROMPT),
    ("problema_objetivos", 0.15, PROBLEMA_OBJETIVOS_PROMPT),
    ("metodologia", 0.15, METODOLOGIA_PROMPT),
    ("desarrollo_evidencias", 0.25, DESARROLLO_EVIDENCIAS_PROMPT),
    ("resultados", 0.15, RESULTADOS_PROMPT),
    ("conclusiones", 0.10, CONCLUSIONES_PROMPT),
    ("redaccion_formato", 0.05, REDACION_FORMATO_PROMPT),
    ("uso_etica_ia", 0.05, USO_IA_PROMPT),
]

def create_agents() -> list[CriterionAgent]:
    return [
        CriterionAgent(name=name, weight=weight, system_prompt=prompt)
        for name, weight, prompt in CRITERION_DEFINITIONS
    ]


def get_criterion_display_names() -> dict[str, str]:
    return {
        "contextualizacion": "Contextualización organización y práctica",
        "problema_objetivos": "Problema y objetivos",
        "metodologia": "Metodología aplicada",
        "desarrollo_evidencias": "Desarrollo y evidencias técnicas",
        "resultados": "Resultados obtenidos",
        "conclusiones": "Conclusiones y reflexión",
        "redaccion_formato": "Redacción, ortografía y formato",
        "uso_etica_ia": "Uso ético de IA",
    }
