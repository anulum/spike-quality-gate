# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — repository inventory
"""Inspect the actual local Git root, branch, index and private-path ignores."""

from __future__ import annotations

import subprocess  # nosec B404  # Required bounded native tool execution.
from pathlib import Path

from repository_policy import EXCLUDED, PUBLIC_PATHS, InventoryIssue, admit_root

PRIVATE_PROBES = ("docs/internal/probe.md", "docs/internal/nested/probe.json")
MAX_GIT_BYTES = 1_048_576


def inspect_repository_git(root: Path) -> tuple[InventoryIssue, ...]:
    """Run bounded read-only Git queries without revealing native error text.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected initial scaffold, requiring actual local main and no remotes.

    Returns
    -------
    tuple of InventoryIssue
        Root, branch, remote, tracked-publication and private-ignore diagnoses.
        An unborn main is valid; a containing parent repository is not.

    Notes
    -----
    Git is a required host executable. This does not qualify its binary build,
    repository history, hooks, remote transport or hosted settings.
    """
    admitted = admit_root(root)
    if isinstance(admitted, InventoryIssue):
        return (admitted,)
    root = admitted
    reasons: list[InventoryIssue] = []
    commands: tuple[tuple[str, ...], ...] = (
        ("rev-parse", "--show-toplevel"),
        ("symbolic-ref", "--short", "HEAD"),
        ("remote",),
        ("ls-files", "--cached", "-z"),
        ("check-ignore", "--no-index", "-z", "--stdin"),
    )
    outputs: list[str] = []
    for arguments in commands:
        try:
            result = subprocess.run(  # nosec B603  # Only source-selected argument vectors; no shell.
                ["/usr/bin/git", "--no-optional-locks", "-c", "core.fsmonitor=false", *arguments],
                cwd=root,
                input="\0".join(PRIVATE_PROBES) + "\0",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError, UnicodeError):
            return (*reasons, InventoryIssue("git", "git_query_unavailable", 3))
        if len(result.stdout.encode("utf-8")) > MAX_GIT_BYTES:
            return (*reasons, InventoryIssue("git", "git_output_limit"))
        if result.returncode != 0 and arguments[0] != "check-ignore":
            return (*reasons, InventoryIssue("git", "git_query_unavailable", 3))
        outputs.append(result.stdout)
    if outputs[0].rstrip("\n") != str(root):
        reasons.append(InventoryIssue("git", "not_repository_root"))
    if outputs[1].rstrip("\n") != "main":
        reasons.append(InventoryIssue("git", "initial_branch_not_main"))
    if outputs[2]:
        reasons.append(InventoryIssue("git", "initial_remote_present"))
    for name in sorted(set(outputs[3].split("\0")) - {""}):
        if name not in PUBLIC_PATHS or any(
            name == item or name.startswith(item + "/") for item in EXCLUDED
        ):
            reasons.append(InventoryIssue("git_index", "unapproved_tracked_path"))
    if set(outputs[4].split("\0")) - {""} != set(PRIVATE_PROBES):
        reasons.append(InventoryIssue(".gitignore", "private_paths_not_ignored"))
    return tuple(reasons)
