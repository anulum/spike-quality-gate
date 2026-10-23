# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — preflight orchestration
"""Run only maintained finite commands and retain their actual scoped outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # nosec B404  # Required bounded native tool execution.
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from check_repository_metadata import REPOSITORY_NAME
from repository_policy import (
    DIRECTORIES,
    PUBLIC_PATHS,
    InventoryIssue,
    admit_root,
    read_inventory_input,
)

PYTHON = ".venv/bin/python"


@dataclass(frozen=True)
class Check:
    """Select one maintained command without using received executable names.

    Parameters
    ----------
    name : str
        Stable check identifier.
    command : tuple of str
        Source-selected command and arguments.
    timeout : int
        Maximum direct-child lifetime in seconds.
    gate : str or None
        Exact JSON guard identifier, or None for a native exit-only command.
    """

    name: str
    command: tuple[str, ...]
    timeout: int
    gate: str | None = None


CHECKS = (
    Check(
        "repository-metadata",
        (PYTHON, "tools/check_repository_metadata.py", "--json"),
        30,
        "repository_metadata",
    ),
    Check(
        "source-provenance",
        (PYTHON, "tools/check_source_provenance.py", "--json"),
        30,
        "source_provenance",
    ),
    Check(
        "workflow-policy",
        (PYTHON, "tools/check_workflow_policy.py", "--json"),
        30,
        "workflow_policy",
    ),
    Check(
        "dependency-alignment",
        (PYTHON, "tools/check_dependency_alignment.py", "--json"),
        30,
        "dependency_alignment",
    ),
    Check(
        "native-tools", (PYTHON, "tools/bootstrap_native_tools.py", "--json"), 30, "native_tools"
    ),
    Check(
        "repository-inventory",
        (PYTHON, "tools/check_repository_inventory.py", "--json"),
        60,
        "repository_inventory",
    ),
    Check("ruff", (".venv/bin/ruff", "check", "tools", "tests"), 60),
    Check("format", (".venv/bin/ruff", "format", "--check", "tools", "tests"), 60),
    Check("mypy", (".venv/bin/mypy", "--strict", "tools", "tests"), 120),
    Check("reuse", (".venv/bin/reuse", "--no-multiprocessing", "lint"), 60),
    Check("documentation", ("/usr/bin/make", "docs"), 120),
    Check("bandit", (".venv/bin/bandit", "-r", "tools", "-q"), 60),
    Check(
        "gitleaks",
        (
            ".tool-cache/native/bin/gitleaks",
            "dir",
            ".",
            "--no-banner",
            "--redact",
            "--ignore-gitleaks-allow",
            "--gitleaks-ignore-path",
            "/dev/null",
            "--timeout",
            "30",
        ),
        60,
    ),
    Check("actionlint", (".tool-cache/native/bin/actionlint", "-color", "-shellcheck="), 60),
    Check(
        "zizmor",
        (
            ".venv/bin/zizmor",
            "--offline",
            "--no-config",
            "--no-ignores",
            "--strict-collection",
            ".github/workflows",
        ),
        60,
    ),
    Check("dependency-audits", ("/usr/bin/make", "dependency-audits"), 300),
    Check("sbom", ("/usr/bin/make", "sbom"), 120),
    Check("tests", ("/usr/bin/make", "test-ci"), 900),
)


AUXILIARY_CHECKS = (Check("source-spdx", (".venv/bin/reuse", "spdx"), 60),)


@dataclass(frozen=True)
class CheckResult:
    """Retain a real check outcome without printing child output or exceptions.

    Parameters
    ----------
    name : str
        Source-selected check identifier.
    status : str
        Pass, refused, unavailable, invalid or not_run.
    exit_code : int
        Controlled 0/2/3/4 meaning; not_run uses refusal.
    code : str
        Fixed reason for the actual result.
    stdout_sha256 : str or None
        Actual bounded stdout digest, when the child completed.
    """

    name: str
    status: str
    exit_code: int
    code: str
    stdout_sha256: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a diagnostic check record, never its private log."""
        return {
            "name": self.name,
            "status": self.status,
            "exit_code": self.exit_code,
            "code": self.code,
            "stdout_sha256": self.stdout_sha256,
        }


def run_check(root: Path, name: str) -> CheckResult:
    """Execute one source-selected check with finite private child logs.

    Parameters
    ----------
    root : pathlib.Path
        Checkout containing its selected actual tooling environment.
    name : str
        Exact maintained check name; never an executable or argument selector.

    Returns
    -------
    CheckResult
        Actual direct-child outcome, or fixed configuration/unavailability
        refusal. Completed native output is bounded to one MiB per stream.

    Notes
    -----
    Logs are temporary files in the checkout's cache; no child text reaches the
    caller. subprocess.run waits for its direct child, including its timeout
    cleanup. Each launched tool remains responsible for its own descendants.
    This does not attest descendant cleanup or a system-wide resource ceiling.
    """
    selected = next((x for x in (*CHECKS, *AUXILIARY_CHECKS) if x.name == name), None)
    if selected is None:
        return CheckResult("invocation", "invalid", 4, "unknown_check")
    admitted = admit_root(root)
    if isinstance(admitted, InventoryIssue):
        return CheckResult(name, "invalid", 4, "invalid_root")
    root = admitted
    cache = root / ".tool-cache" / "preflight"
    if isinstance(admit_root(cache), InventoryIssue):
        return CheckResult(name, "refused", 2, "cache_link_refused")
    try:
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="check-", dir=cache) as temporary:
            directory = Path(temporary)
            environment = {
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "TMPDIR": str(directory),
                "XDG_CACHE_HOME": str(root / ".tool-cache"),
                "PRE_COMMIT_HOME": str(root / ".tool-cache" / "pre-commit"),
            }
            command = selected.command
            working_directory = root
            if name in {"gitleaks", "source-spdx"}:
                projection = directory / REPOSITORY_NAME
                projection.mkdir()
                for relative in sorted(PUBLIC_PATHS - DIRECTORIES):
                    data = read_inventory_input(root, relative)
                    if isinstance(data, InventoryIssue):
                        return CheckResult(
                            name,
                            {2: "refused", 3: "unavailable", 4: "invalid"}[data.exit_code],
                            data.exit_code,
                            "source_projection_refused",
                        )
                    target = projection / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                command = tuple(str(projection) if x == "." else x for x in command)
                environment.pop("GITLEAKS_CONFIG", None)
                environment.pop("GITLEAKS_CONFIG_TOML", None)
                if name == "source-spdx":
                    command = (
                        str(root / command[0]),
                        "--no-multiprocessing",
                        "--root",
                        str(projection),
                        *command[1:],
                    )
                    working_directory = projection
            with (
                (directory / "stdout").open("w+b") as stdout,
                (directory / "stderr").open("w+b") as stderr,
            ):
                result = subprocess.run(  # nosec B603  # Only source-selected argument vectors; no shell.
                    command,
                    cwd=working_directory,
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=selected.timeout,
                    check=False,
                )
                stdout.seek(0)
                raw = stdout.read(1_048_577)
                stderr.seek(0, 2)
                if len(raw) > 1_048_576 or stderr.tell() > 1_048_576:
                    return CheckResult(name, "refused", 2, "child_output_limit")
                if name == "source-spdx" and result.returncode == 0:
                    destination = root / ".tool-cache/reports/source.spdx"
                    if isinstance(admit_root(destination), InventoryIssue):
                        return CheckResult(name, "refused", 2, "source_output_link_refused")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(raw)
    except (OSError, subprocess.SubprocessError):
        return CheckResult(name, "unavailable", 3, "required_check_unavailable")
    digest = hashlib.sha256(raw).hexdigest()
    exit_code = 0 if result.returncode == 0 else 2
    if selected.gate is not None:
        try:
            document: object = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            return CheckResult(name, "refused", 2, "invalid_child_report", digest)
        if (
            not isinstance(document, dict)
            or document.get("gate") != selected.gate
            or document.get("status")
            != {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}.get(result.returncode)
            or not isinstance(document.get("reasons"), list)
            or bool(document["reasons"]) != (result.returncode != 0)
        ):
            return CheckResult(name, "refused", 2, "invalid_child_report", digest)
        exit_code = result.returncode
    return CheckResult(
        name,
        {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[exit_code],
        exit_code,
        "check_passed" if exit_code == 0 else "check_failed",
        digest,
    )


class _Arguments(argparse.Namespace):
    root: str
    check: str
    json: bool


def main(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    """Run one named infrastructure check without clearing the full preflight.

    Parameters
    ----------
    argv : list of str or None
        Explicit command arguments or the current process arguments.
    output : text stream or None
        Destination for the scoped report; standard output by default.

    Returns
    -------
    int
        The named check's controlled 0/2/3/4 result. No omitted check is qualified.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument("--root", default=".")
    parser.add_argument("--check", default="")
    parser.add_argument("--json", action="store_true")
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        result = CheckResult("invocation", "invalid", 4, "invalid_arguments")
    else:
        result = (
            CheckResult("invocation", "invalid", 4, "unknown_arguments")
            if unknown
            else run_check(Path(args.root), args.check)
        )
    document = {
        "gate": "preflight_check",
        "scope": "single_named_infrastructure_check",
        **result.as_dict(),
    }
    try:
        destination = sys.stdout if output is None else output
        destination.write(json.dumps(document, sort_keys=True, indent=2) + "\n")
        destination.flush()
    except (OSError, ValueError):
        return max(3, result.exit_code)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
