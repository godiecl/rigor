import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import litellm

from benchmarking import benchmark
from extraction import extract_clean_text
from evaluator import (
    create_agents,
    aggregate_scores,
    check_consistency,
    validate_result,
    JudgeConfig,
    ReportData,
    Usage,
    generate_markdown_report,
    generate_json_report,
)
from utils import configure_context, ConfiguredContext

log = logging.getLogger(__name__)


async def run_evaluation(
    text: str,
    config: JudgeConfig,
) -> ReportData:
    agents = create_agents()

    input_tokens = litellm.token_counter(model=config.model, text=text)
    if input_tokens > config.max_input_tokens:
        log.warning(
            "input is %s tokens (limit %s); evaluation may overflow the model "
            "context window",
            f"{input_tokens:,}",
            f"{config.max_input_tokens:,}",
        )

    log.info(
        f"Evaluating with {len(agents)} agents (model: {config.model}, "
        f"input: {input_tokens:,} tokens, concurrency: {config.max_concurrency})"
    )

    # Bound concurrency so a batch of agents can't trip provider rate limits.
    semaphore = asyncio.Semaphore(config.max_concurrency)

    async def run_agent(agent):
        async with semaphore:
            return await agent.evaluate(text, config)

    results = await asyncio.gather(*(run_agent(a) for a in agents))

    # Failsafe: flag verdicts whose evidence isn't grounded in the document or
    # whose score/justification are structurally incoherent (no extra API cost).
    flagged = 0
    for r in results:
        r.validation_flags = validate_result(r, text)
        if r.validation_flags:
            flagged += 1
            for f in r.validation_flags:
                log.warning("validation [%s]: %s", r.criterion, f)
    if flagged:
        log.warning("%d/%d criterio(s) marcados para revisión humana", flagged, len(results))

    aggregated = aggregate_scores(results)
    log.info(f"Final score: {aggregated.final_score:.2f} — {aggregated.final_level}")

    consistency_warnings = check_consistency(results)
    if consistency_warnings:
        log.warning(f"{len(consistency_warnings)} consistency warning(s) found")
        for w in consistency_warnings:
            log.warning(f"  - {w.message}")

    total_usage = Usage()
    for r in results:
        total_usage.add(r.usage)

    estimated_cost = total_usage.cost or None

    usage = {
        "prompt_tokens": total_usage.prompt_tokens,
        "completion_tokens": total_usage.completion_tokens,
        "total_tokens": total_usage.total_tokens,
        "estimated_cost_usd": estimated_cost,
    }
    log.info(
        "tokens: %s prompt + %s completion = %s total%s",
        f"{total_usage.prompt_tokens:,}",
        f"{total_usage.completion_tokens:,}",
        f"{total_usage.total_tokens:,}",
        f" (~${estimated_cost:.4f})" if estimated_cost is not None else "",
    )

    return ReportData(
        document_name="",
        model=config.model,
        aggregated=aggregated,
        consistency_warnings=consistency_warnings,
        usage=usage,
    )


async def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    config: JudgeConfig,
) -> None:
    log.info(f"extracting text from {pdf_path.name}")
    with benchmark("PDF extraction", log):
        md_text, stats = extract_clean_text(pdf_path)
    log.info(
        "extracted %s pages, %s -> %s chars (%s header/footer lines removed)",
        stats.pages,
        f"{stats.raw_chars:,}",
        f"{stats.clean_chars:,}",
        stats.removed_header_footer_lines,
    )

    report_data = await run_evaluation(
        text=md_text,
        config=config,
    )
    report_data.document_name = pdf_path.stem

    md_report = generate_markdown_report(report_data)
    json_report = generate_json_report(report_data)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = output_dir / f"{timestamp}.{pdf_path.stem}_evaluation.md"
    md_path.write_text(md_report, encoding="utf-8")
    log.info(f"markdown report -> {md_path}")

    json_path = output_dir / f"{timestamp}.{pdf_path.stem}_evaluation.json"
    json_path.write_text(
        json.dumps(json_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(f"json report -> {json_path}")


async def process_pdfs(
    pdf_files: list[Path],
    output_dir: Path,
    config: JudgeConfig,
) -> None:
    for pdf in pdf_files:
        try:
            await process_pdf(
                pdf_path=pdf,
                output_dir=output_dir,
                config=config,
            )
        except Exception as e:
            log.error(f"{pdf.name}: {e}", exc_info=True)


def main(cc: ConfiguredContext) -> None:
    pdfs_path = cc.input_path / "pdfs"
    if not pdfs_path.exists():
        log.error(f"directory {pdfs_path} doesn't exist!")
        raise ValueError(f"directory {pdfs_path} doesn't exist!")

    pdf_files = sorted(pdfs_path.glob("*.pdf"))
    if not pdf_files:
        log.warning(f"No PDF files found in {pdfs_path}")
        return

    output_dir = cc.output_path / "evaluations"
    output_dir.mkdir(parents=True, exist_ok=True)

    # litellm reads OPENAI_API_KEY from the environment.
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    config = JudgeConfig.from_env()

    log.info(f"{len(pdf_files)} PDF(s) to evaluate")
    log.info(
        f"model: {config.model}, temperature: {config.temperature}, max_tokens: {config.max_tokens}"
    )

    asyncio.run(
        process_pdfs(
            pdf_files=pdf_files,
            output_dir=output_dir,
            config=config,
        )
    )


if __name__ == "__main__":
    ctx: ConfiguredContext = configure_context()

    with benchmark("main", log):
        log.info("🏎️ starting evaluation ..")
        main(cc=ctx)
        log.info("🏁 evaluation done.")
