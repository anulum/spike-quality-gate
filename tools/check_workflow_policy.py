# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — initial workflow policy
"""Check selected workflow policy without claiming native or hosted execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import TextIO

from workflow_rules import (
    MAX_BYTES,
    PROVENANCE_SHA256,
    ROLES,
    WorkflowIssue,
    WorkflowReport,
    check_job_policy,
)
from workflow_yaml import load_workflow_yaml


def _read(root: Path, name: str) -> bytes | WorkflowIssue:
    path = root / name
    try:
        if path.is_symlink():
            return WorkflowIssue(name, "workflow_link_refused")
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
    except OSError:
        return WorkflowIssue(name, "required_input_unavailable", 3)
    if len(data) > MAX_BYTES:
        return WorkflowIssue(name, "input_limit_exceeded")
    return data


def validate_workflow_policy(root: Path) -> WorkflowReport:
    """Inspect the seven required source-selected read-only workflow definitions.

    Parameters
    ----------
    root : pathlib.Path
        Repository source root; inputs are never modified.

    Returns
    -------
    WorkflowReport
        All structural/source diagnoses. Success does not establish native
        actionlint, complete Make/tool wiring, service settings or hosted runs.
        Invalid UTF-8 or NUL-containing roots produce invocation diagnosis 4.
    """
    try:
        str(root).encode("utf-8")
        if "\0" in str(root):
            raise ValueError("invalid root")
    except ValueError:
        return WorkflowReport((WorkflowIssue("invocation", "invalid_root", 4),))
    reasons: list[WorkflowIssue] = []
    provenance = _read(root, "workflow-provenance.json")
    if isinstance(provenance, WorkflowIssue):
        reasons.append(provenance)
    elif hashlib.sha256(provenance).hexdigest() != PROVENANCE_SHA256:
        reasons.append(WorkflowIssue("workflow-provenance.json", "source_receipt_not_selected"))
    try:
        actual = {
            p.name
            for p in (root / ".github/workflows").iterdir()
            if p.suffix.lower() in {".yml", ".yaml"}
        }
    except OSError:
        reasons.append(WorkflowIssue(".github/workflows", "workflow_directory_unavailable", 3))
    else:
        if actual != set(ROLES):
            reasons.append(WorkflowIssue(".github/workflows", "workflow_set_not_classified"))
    for filename in sorted(ROLES):
        name = ".github/workflows/" + filename
        data = _read(root, name)
        if isinstance(data, WorkflowIssue):
            reasons.append(data)
            continue
        value = load_workflow_yaml(data, name)
        if isinstance(value, WorkflowIssue):
            reasons.append(value)
            continue
        if not isinstance(value, dict):
            reasons.append(WorkflowIssue(name, "workflow_not_object"))
            continue
        if set(value) - {"name", "on", "permissions", "concurrency", "defaults", "env", "jobs"}:
            reasons.append(WorkflowIssue(name, "workflow_fields_not_selected"))
        expected_env = {"PYTHONDONTWRITEBYTECODE": "1"}
        if filename != "scorecard.yml":
            expected_env.update(
                {
                    "UV_LINK_MODE": "hardlink",
                    "UV_CACHE_DIR": "$" + "{{ github.workspace }}/.tool-cache/uv-cache",
                    "TMPDIR": "$" + "{{ github.workspace }}/.tool-cache/tmp",
                    "PRE_COMMIT_HOME": "$" + "{{ github.workspace }}/.tool-cache/pre-commit",
                }
            )
        if value.get("env") != expected_env:
            reasons.append(WorkflowIssue(name, "tooling_environment_not_selected"))
        if value.get("on") != {"push": {}, "pull_request": {}, "workflow_dispatch": {}}:
            reasons.append(WorkflowIssue(name, "required_trigger_surface_filtered"))
        if value.get("permissions") != {"contents": "read"}:
            reasons.append(WorkflowIssue(name, "permissions_not_read_only"))
        expected_group = "$" + "{{ github.workflow }}-" + "$" + "{{ github.ref }}"
        if value.get("concurrency") != {"group": expected_group, "cancel-in-progress": True}:
            reasons.append(WorkflowIssue(name, "concurrency_not_selected"))
        if value.get("defaults") != {"run": {"shell": "bash"}}:
            reasons.append(WorkflowIssue(name, "shell_defaults_not_selected"))
        pending: list[object] = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
            elif isinstance(item, str) and re.search(r"\$\{\{[^}]*\bsecrets\.", item):
                reasons.append(WorkflowIssue(name, "secret_dependent_workflow_refused"))
                break
        jobs = value.get("jobs")
        if not isinstance(jobs, dict):
            reasons.append(WorkflowIssue(name, "jobs_not_object"))
            continue
        expected_jobs = {"validation", "gate"} if filename == "ci.yml" else {"validation"}
        if set(jobs) != expected_jobs:
            reasons.append(WorkflowIssue(name, "job_set_not_classified"))
        for job_id, job in jobs.items():
            reasons.extend(check_job_policy(name, job, aggregate=job_id == "gate"))
    excluded = {
        ".git",
        ".venv",
        ".tool-cache",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "target",
        "dist",
        "build",
        "docs/internal",
    }

    def unavailable(_error: OSError) -> None:
        reasons.append(WorkflowIssue("source_tree", "analysis_source_unavailable", 3))

    for directory, dirs, files in root.walk(on_error=unavailable, follow_symlinks=False):
        dirs[:] = [
            d
            for d in dirs
            if (directory / d).relative_to(root).as_posix() not in excluded and d != "__pycache__"
        ]
        for filename in files:
            relative = (directory / filename).relative_to(root).as_posix()
            suffix = Path(filename).suffix.lower()
            if suffix == ".py" and not relative.startswith(("tools/", "tests/")):
                reasons.append(WorkflowIssue("source_tree", "python_analysis_scope_omitted"))
            elif suffix in {
                ".rs",
                ".js",
                ".ts",
                ".c",
                ".cpp",
                ".cs",
                ".go",
                ".rb",
                ".java",
                ".kt",
                ".swift",
            }:
                reasons.append(WorkflowIssue("source_tree", "analysis_language_not_selected"))
    return WorkflowReport(tuple(reasons))


class _Arguments(argparse.Namespace):
    root: str
    json: bool


def main(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    """Run the portable workflow-source check with controlled scoped reports.

    Parameters
    ----------
    argv : list of str or None, optional
        Command arguments, or the current process arguments.
    output : text stream or None, optional
        Report destination, defaulting to standard output.

    Returns
    -------
    int
        Zero for the named static check, 2 for refusal, 3 for unavailable
        input/parser/output and 4 for invalid invocation. Help is informational.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument(
        "--root", default=".", help="Repository root; workflow inputs are read-only."
    )
    parser.add_argument("--json", action="store_true", help="Emit the scoped JSON report.")
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        report = WorkflowReport((WorkflowIssue("invocation", "invalid_arguments", 4),))
        json_output = True
    else:
        json_output = args.json
        report = (
            WorkflowReport((WorkflowIssue("invocation", "unknown_arguments", 4),))
            if unknown
            else validate_workflow_policy(Path(args.root))
        )
    document = report.as_dict()
    text = (
        json.dumps(document, sort_keys=True, indent=2) + "\n"
        if json_output
        else "workflow_policy: "
        + str(document["status"])
        + "\n"
        + "".join(f"{x.path}: {x.code}\n" for x in report.reasons)
    )
    destination = sys.stdout if output is None else output
    try:
        destination.write(text)
        destination.flush()
    except (OSError, ValueError):
        return max(3, report.exit_code)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
