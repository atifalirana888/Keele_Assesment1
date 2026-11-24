"""Shared command-line options and demo database bootstrap.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
The student must review, understand and acknowledge this use in their submission.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
import shutil

from .service import FinanceService

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
NORMAL_PATH = DATA_DIR / "pennypilot.json"
DEMO_SEED = DATA_DIR / "sample_data.json"
DEMO_WORKSPACE = DATA_DIR / "demo_workspace.json"


def add_data_arguments(parser: ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--demo", action="store_true", help="Use a separate seeded demo workspace")
    group.add_argument("--data", type=Path, metavar="PATH", help="Use an alternative JSON data file")


def open_service(args: Namespace) -> FinanceService:
    if args.demo:
        if not DEMO_WORKSPACE.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DEMO_SEED, DEMO_WORKSPACE)
        path = DEMO_WORKSPACE
    else:
        path = args.data if args.data is not None else NORMAL_PATH
    return FinanceService(path)
