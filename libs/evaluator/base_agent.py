import json
import logging
from dataclasses import dataclass, field
from typing import Any

import litellm
from litellm import acompletion

from .schemas import CriterionEvaluation, strict_schema
from .scoring import clamp_score, get_level_for_score

# Drop provider-unsupported params instead of erroring (e.g. reasoning models
# such as gpt-5.* that reject `temperature` / remap `max_tokens`).
litellm.drop_params = True


@dataclass(frozen=True)
class JudgeConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_secs: int = 180
    max_retries: int = 2
    seed: int | None = 7
    max_concurrency: int = 4
    max_input_tokens: int = 100_000

    @classmethod
    def from_env(cls) -> "JudgeConfig":
        import os

        seed_raw = os.getenv("EVALUATION_SEED", "7")
        return cls(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("EVALUATION_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("EVALUATION_MAX_TOKENS", "4096")),
            timeout_secs=int(os.getenv("EVALUATION_TIMEOUT_SECS", "180")),
            max_retries=int(os.getenv("EVALUATION_MAX_RETRIES", "2")),
            seed=int(seed_raw) if seed_raw.strip() else None,
            max_concurrency=int(os.getenv("EVALUATION_MAX_CONCURRENCY", "4")),
            max_input_tokens=int(os.getenv("EVALUATION_MAX_INPUT_TOKENS", "100000")),
        )


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0

    def add(self, other: "Usage | None") -> None:
        if other is None:
            return
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cost += other.cost

    @classmethod
    def from_response(cls, response: Any) -> "Usage | None":
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        try:
            cost = litellm.completion_cost(completion_response=response) or 0.0
        except Exception:
            cost = 0.0
        return cls(
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            cost=cost,
        )


@dataclass
class EvaluationResult:
    criterion: str
    weight: float
    score: float
    level: str
    justification: str
    evidence: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    raw_response: str | None = None
    error: str | None = None
    usage: Usage | None = None
    validation_flags: list[str] = field(default_factory=list)


EVALUATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_evaluation",
        "description": "Entrega el resultado de la evaluación para un criterio específico",
        "parameters": strict_schema(CriterionEvaluation),
        "strict": True,
    },
}

FORCE_EVALUATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {"name": "submit_evaluation"},
}


class CriterionAgent:
    def __init__(
        self,
        name: str,
        weight: float,
        system_prompt: str,
    ) -> None:
        self.name = name
        self.weight = weight
        self.system_prompt = system_prompt
        self.log = logging.getLogger(f"evaluator.{name}")

    async def evaluate(
        self,
        text: str,
        config: JudgeConfig,
    ) -> EvaluationResult:
        try:
            response = await acompletion(
                model=config.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                seed=config.seed,
                tools=[EVALUATION_TOOL],
                tool_choice=FORCE_EVALUATION_TOOL,
                timeout=config.timeout_secs,
                num_retries=config.max_retries,
            )

            choice = response.choices[0]
            assistant_msg = choice.message
            usage = Usage.from_response(response)

            if choice.finish_reason == "length":
                raise ValueError(
                    "respuesta truncada (max_tokens alcanzado); "
                    "aumente EVALUATION_MAX_TOKENS"
                )

            if assistant_msg.tool_calls:
                raw_args = assistant_msg.tool_calls[0].function.arguments
            elif assistant_msg.content:
                raw_args = assistant_msg.content
            else:
                raise ValueError("No tool calls and no content in response")

            evaluation = CriterionEvaluation.model_validate(
                self._extract_json(raw_args)
            )

            # Score is the rubric anchor; derive the level from it deterministically
            # so the displayed band can never contradict the number.
            score = clamp_score(evaluation.score)
            level = get_level_for_score(score)
            if level != evaluation.level:
                self.log.debug(
                    "level recomputed for '%s': model=%s -> score-band=%s",
                    self.name,
                    evaluation.level,
                    level,
                )

            return EvaluationResult(
                criterion=self.name,
                weight=self.weight,
                score=score,
                level=level,
                justification=evaluation.justification,
                evidence=evaluation.evidence,
                strengths=evaluation.strengths,
                weaknesses=evaluation.weaknesses,
                improvements=evaluation.improvements,
                raw_response=raw_args,
                usage=usage,
            )

        except Exception as e:
            self.log.error("Error evaluating criterion '%s': %s", self.name, e)
            return EvaluationResult(
                criterion=self.name,
                weight=self.weight,
                score=0.0,
                level="Error",
                justification="",
                error=str(e),
            )

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if 0 <= start < end:
                return json.loads(content[start:end])
            raise ValueError(f"No JSON found in content: {content[:200]}")
