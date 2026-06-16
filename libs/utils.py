import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from logger import configure_logging


@dataclass(frozen=True)
class ConfiguredContext:
    root_path: Path
    output_path: Path
    input_path: Path
    scratch_path: Path


def configure_context() -> ConfiguredContext:
    configure_logging(logging.DEBUG)
    log = logging.getLogger(__name__)

    root_path = Path(__file__).resolve().parent.parent
    log.debug(f"📁 root_path -> {root_path}")

    output_path = root_path / "output"
    output_path.mkdir(parents=True, exist_ok=True)
    log.debug(f"📁 output_path -> {output_path}")

    input_path = root_path / "input"
    input_path.mkdir(parents=True, exist_ok=True)
    log.debug(f"📁 input_dir -> {input_path}")

    scratch_path = root_path / "scratch"
    scratch_path.mkdir(parents=True, exist_ok=True)
    log.debug(f"📁 scratch_dir -> {scratch_path}")

    before_env = set(os.environ.keys())
    if load_dotenv():
        log.info("✅ .env file loaded successfully.")
        after_env = set(os.environ.keys())
        file_env = after_env.difference(before_env)
        for var in file_env:
            log.debug(f"📋 {var} = {'*' * len(os.environ[var]) if os.environ[var] else '***'}")
    else:
        raise EnvironmentError("💀 .env file not found or could not be loaded.")

    return ConfiguredContext(
        root_path=root_path,
        output_path=output_path,
        input_path=input_path,
        scratch_path=scratch_path
    )
