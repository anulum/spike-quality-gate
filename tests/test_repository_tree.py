# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real inventory behaviour
"""Inspect actual maintained source and ordinary adverse filesystem fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from repository_policy import DIRECTORIES, MAX_ENTRIES, MAX_FILE_BYTES, PUBLIC_PATHS
from repository_tree import inspect_repository_tree

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Copy actual authored public files; never synthesize missing implementation."""
    for name in sorted(PUBLIC_PATHS - DIRECTORIES):
        source = ROOT / name
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return tmp_path


def test_actual_complete_public_structure(candidate: Path) -> None:
    """Require real authored source for every selected initial path."""
    assert inspect_repository_tree(ROOT) == ()
    assert inspect_repository_tree(candidate) == ()


def test_required_kind_and_missing_path_refuse(candidate: Path) -> None:
    """Reject a real directory substituted for a source and a missing document."""
    (candidate / "README.md").unlink()
    (candidate / "tools/preflight.py").unlink()
    (candidate / "tools/preflight.py").mkdir()
    codes = {(x.path, x.code) for x in inspect_repository_tree(candidate)}
    assert ("README.md", "required_path_unavailable") in codes
    assert ("tools/preflight.py", "required_path_wrong_kind") in codes


def test_actual_ignored_private_docs_and_cache_are_outside_cohort(candidate: Path) -> None:
    """Permit retained private docs/cache contents without inspecting their bytes."""
    for name in ("docs/internal/state.md", ".tool-cache/native/data.bin"):
        path = candidate / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"private excluded fixture")
    assert inspect_repository_tree(candidate) == ()
    (candidate / "docs/internal/state.md").unlink()
    (candidate / "docs/internal").rmdir()
    (candidate / "docs/internal").symlink_to(ROOT / "docs/internal", target_is_directory=True)
    assert "source_link_refused" in {x.code for x in inspect_repository_tree(candidate)}


def test_unaccounted_generated_state_links_and_large_inputs_refuse(candidate: Path) -> None:
    """Reject actual unknown sources, forbidden ignored trees and oversized bytes."""
    (candidate / "unexpected.py").write_text("value = 1")
    (candidate / "src").mkdir()
    (candidate / "src/.env").write_bytes(b"nonsecret invalid fixture")
    (candidate / ".coordination").mkdir()
    (candidate / "linked.md").symlink_to(ROOT / "README.md")
    (candidate / "oversized.bin").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    codes = {x.code for x in inspect_repository_tree(candidate)}
    assert codes >= {
        "unaccounted_public_file",
        "unaccounted_directory",
        "forbidden_actual_state",
        "source_link_refused",
        "source_limit_exceeded",
    }


def test_source_count_and_directory_read_failure_are_located(candidate: Path) -> None:
    """Refuse a real oversized cohort and unavailable source directory."""
    directory = candidate / "tests"
    directory.chmod(0o111)
    try:
        assert "source_directory_unavailable" in {
            x.code for x in inspect_repository_tree(candidate)
        }
    finally:
        directory.chmod(0o700)
    for number in range(MAX_ENTRIES + 1):
        (candidate / f"extra-{number}").touch()
    assert "tree_limit_exceeded" in {x.code for x in inspect_repository_tree(candidate)}


def test_invalid_name_and_nonregular_source_are_refused(candidate: Path) -> None:
    """Refuse unsupported encoded filenames and a real Unix-domain socket."""
    import os
    import socket
    from contextlib import chdir

    invalid = os.fsencode(candidate) + b"/invalid-\xff"
    descriptor = os.open(invalid, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(descriptor)
    with chdir(candidate), socket.socket(socket.AF_UNIX) as endpoint:
        endpoint.bind("input.sock")
        codes = {x.code for x in inspect_repository_tree(candidate)}
        assert {"invalid_source_name", "source_not_regular"} <= codes


def test_invalid_root_is_not_traversed() -> None:
    """Reject NUL before listing a repository."""
    assert inspect_repository_tree(Path("bad\0root"))[0].exit_code == 4
