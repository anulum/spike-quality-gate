# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — preflight orchestration
"""Aggregate the complete source-selected scaffold chain without successful skips."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from preflight_checks import CHECKS, CheckResult, run_check


@dataclass(frozen=True)
class PreflightReport:
    """Retain every required check, including checks not executed.

    Parameters
    ----------
    checks : tuple of CheckResult
        Source-ordered actual or not_run outcomes.
    """

    checks: tuple[CheckResult, ...]

    @property
    def exit_code(self) -> int:
        """Refuse unavailable, invalid, failed and unexecuted required checks."""
        return max((x.exit_code for x in self.checks), default=4)

    def as_dict(self) -> dict[str, object]:
        """Return the infrastructure scope with no domain or hosted acceptance."""
        return {
            "gate": "preflight",
            "scope": "local_scaffold",
            "status": {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[self.exit_code],
            "checks": [x.as_dict() for x in self.checks],
        }


def run_preflight(root: Path, *, only: tuple[str, ...] | None = None) -> PreflightReport:
    """Run the actual selected chain, retaining omitted or failed-check successors.

    Parameters
    ----------
    root : pathlib.Path
        Actual selected checkout.
    only : tuple of str or None
        Optional named checks for focused diagnosis. Other required checks stay
        not_run and the overall preflight cannot pass. None selects all checks.

    Returns
    -------
    PreflightReport
        Every required result, with 4>3>2>0 precedence. The first actual failure
        prevents subsequent launches, with their unexecuted states retained.

    Notes
    -----
    The full default includes the entire infrastructure test suite and network
    vulnerability lookups. Use it in CI or an explicitly reserved pre-push
    environment. A focused invocation cannot clear complete scaffold acceptance.
    """
    names = {x.name for x in CHECKS}
    if only is not None and (not only or len(set(only)) != len(only) or set(only) - names):
        return PreflightReport(
            (CheckResult("invocation", "invalid", 4, "invalid_check_selection"),)
        )
    results: list[CheckResult] = []
    stopped = False
    for check in CHECKS:
        if stopped or (only is not None and check.name not in only):
            results.append(CheckResult(check.name, "not_run", 2, "required_check_not_run"))
            continue
        result = run_check(root, check.name)
        results.append(result)
        stopped = result.exit_code != 0
    return PreflightReport(tuple(results))


class _Arguments(argparse.Namespace):
    root: str
    profile: str
    only: list[str] | None
    json: bool


def main(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    """Execute the real preflight CLI with controlled diagnostics.

    Parameters
    ----------
    argv : list of str or None
        Explicit arguments, or actual process arguments.
    output : text stream or None
        Report destination; defaults to standard output.

    Returns
    -------
    int
        Complete pass 0, refusal/not_run 2, unavailable 3 or invalid 4.
        Help is informational and launches no checks.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", choices=("local-scaffold",), default="local-scaffold")
    parser.add_argument("--only", action="append")
    parser.add_argument("--json", action="store_true")
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        report = PreflightReport((CheckResult("invocation", "invalid", 4, "invalid_arguments"),))
        json_output = True
    else:
        json_output = args.json
        report = (
            PreflightReport((CheckResult("invocation", "invalid", 4, "unknown_arguments"),))
            if unknown
            else run_preflight(
                Path(args.root), only=None if args.only is None else tuple(args.only)
            )
        )
    document = report.as_dict()
    text = (
        json.dumps(document, sort_keys=True, indent=2) + "\n"
        if json_output
        else "preflight: "
        + str(document["status"])
        + "\n"
        + "".join(f"{x.name}: {x.status} ({x.code})\n" for x in report.checks)
    )
    try:
        destination = sys.stdout if output is None else output
        destination.write(text)
        destination.flush()
    except (OSError, ValueError):
        return max(3, report.exit_code)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
