"""mizan/cli/main.py — top-level `mizan` console-script entrypoint.

Implements PHASE_2_SPEC.md §4.4.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from mizan.cli import ingest as ingest_cli
from mizan.cli import normalize as normalize_cli
from mizan.config.boot_check import FiqhRegisterError, InvariantViolationError, check_all


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level `mizan` parser.

    Registers one subparser per verb; Phase 2 registered `ingest`
    (`mizan.cli.ingest.add_subparser`), Phase 3 adds `normalize`
    (`mizan.cli.normalize.add_subparser`). Later phases each add one line here for their verb — this
    file is the one place later phases touch in `mizan/cli/`, per PHASE_2_SPEC.md §1's
    additive-extension note.
    """
    parser = argparse.ArgumentParser(
        prog="mizan", description="Mizan halal-constrained research sandbox."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_cli.add_subparser(subparsers)
    normalize_cli.add_subparser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entrypoint (`mizan`, registered in `pyproject.toml`).

    Per `PHASE_1_SPEC.md` §4.1's own stated requirement for every later phase's CLI entrypoint:
    calls `mizan.config.boot_check.check_all()` FIRST, before dispatching to any subcommand, and
    exits 1 immediately (printing to stderr, in exactly the same format `mizan-boot-check` uses) if
    it raises — no subcommand ever runs against an unverified foundation.
    """
    try:
        check_all()
    except InvariantViolationError as exc:
        print(f"BOOT FAILED — permissibility invariant violated: {exc}", file=sys.stderr)
        return 1
    except FiqhRegisterError as exc:
        print(f"BOOT FAILED — fiqh register is structurally broken: {exc}", file=sys.stderr)
        return 1

    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
