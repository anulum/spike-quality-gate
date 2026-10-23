# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — repository inventory
"""Inspect actual initial source paths independently of generated declarations."""

from __future__ import annotations

import stat
from pathlib import Path

from repository_policy import (
    DIRECTORIES,
    EXCLUDED,
    FORBIDDEN_NAMES,
    MAX_ENTRIES,
    MAX_FILE_BYTES,
    PUBLIC_PATHS,
    REQUIRED_PATHS,
    InventoryIssue,
    admit_root,
    inspect_repository_configuration,
)


def inspect_repository_tree(root: Path) -> tuple[InventoryIssue, ...]:
    """Check required kinds and the bounded source-selected public tree.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected repository. Known caches and private documentation are
        excluded after their enclosing path is checked for links.

    Returns
    -------
    tuple of InventoryIssue
        Missing/wrong required paths, unsupported public material, forbidden
        actual state, links, source-size limits and unavailable directories.

    Notes
    -----
    This is a project-owned source-cohort check, not an ecosystem auditor or a
    scan of cache contents. Native attribution, rendered docs and Git-index
    publication constraints remain separate checks.
    """
    admitted = admit_root(root)
    if isinstance(admitted, InventoryIssue):
        return (admitted,)
    root = admitted
    reasons = list(inspect_repository_configuration(root))
    for name in sorted(REQUIRED_PATHS):
        path = root / name
        try:
            mode = path.lstat().st_mode
        except OSError:
            reasons.append(InventoryIssue(name, "required_path_unavailable", 3))
            continue
        expected_kind = stat.S_ISDIR if name in DIRECTORIES else stat.S_ISREG
        if not expected_kind(mode):
            reasons.append(InventoryIssue(name, "required_path_wrong_kind"))
    containers = {str(Path(name).parent) for name in PUBLIC_PATHS}
    containers |= {str(parent) for name in PUBLIC_PATHS for parent in Path(name).parents}
    pending = [root]
    count = 0
    while pending:
        directory = pending.pop()
        try:
            entries = []
            for path in directory.iterdir():
                count += 1
                if count > MAX_ENTRIES:
                    return (*reasons, InventoryIssue("source_tree", "tree_limit_exceeded"))
                entries.append(path)
            for path in sorted(entries):
                name = path.relative_to(root).as_posix()
                try:
                    name.encode("utf-8")
                except UnicodeError:
                    reasons.append(InventoryIssue("source_tree", "invalid_source_name"))
                    continue
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode):
                    reasons.append(InventoryIssue(name, "source_link_refused"))
                elif path.name in FORBIDDEN_NAMES or path.name.startswith(".env"):
                    reasons.append(InventoryIssue(name, "forbidden_actual_state"))
                elif name in EXCLUDED or path.name == "__pycache__":
                    continue
                elif stat.S_ISDIR(mode):
                    if name not in containers:
                        reasons.append(InventoryIssue(name, "unaccounted_directory"))
                    pending.append(path)
                elif not stat.S_ISREG(mode):
                    reasons.append(InventoryIssue(name, "source_not_regular"))
                else:
                    if name not in PUBLIC_PATHS:
                        reasons.append(InventoryIssue(name, "unaccounted_public_file"))
                    if path.stat().st_size > MAX_FILE_BYTES:
                        reasons.append(InventoryIssue(name, "source_limit_exceeded"))
        except OSError:
            reasons.append(
                InventoryIssue(
                    directory.relative_to(root).as_posix(), "source_directory_unavailable", 3
                )
            )
    return tuple(reasons)
