# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real inventory behaviour
"""Exercise actual native Git root, branch, index and ignore behaviour."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repository_git import inspect_repository_git

ROOT = Path(__file__).resolve().parents[1]


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=root, capture_output=True, check=True, timeout=15)


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Create an actual unborn main with the real private-path ignore policy."""
    _git(tmp_path, "init", "-q", "--initial-branch=main")
    (tmp_path / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
    return tmp_path


def test_actual_checkout_and_unborn_fixture_are_native(candidate: Path) -> None:
    """Accept only the actual required branch/index/ignore scope."""
    assert inspect_repository_git(ROOT) == ()
    assert inspect_repository_git(candidate) == ()


def test_populated_public_index_is_accepted(candidate: Path) -> None:
    """Accept actual approved sources staged together for an initial commit."""
    for name in ("README.md", "LICENSE"):
        (candidate / name).write_bytes((ROOT / name).read_bytes())
    _git(candidate, "add", "--", "README.md", "LICENSE")
    assert inspect_repository_git(candidate) == ()


def test_actual_branch_remote_index_and_ignore_failures_are_retained(candidate: Path) -> None:
    """Inspect real native metadata after normal independent Git mutations."""
    _git(candidate, "symbolic-ref", "HEAD", "refs/heads/other")
    _git(candidate, "remote", "add", "origin", "https://example.invalid/fixture.git")
    (candidate / ".gitignore").write_text("")
    private = candidate / "docs/internal"
    private.mkdir(parents=True)
    (private / "nonsecret-fixture.md").write_text("nonsecret adverse index fixture")
    _git(candidate, "add", "--", "docs/internal/nonsecret-fixture.md")
    (candidate / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
    (candidate / ".gitignore").write_text(
        (candidate / ".gitignore").read_text().replace("/docs/internal/", "/not-internal/")
    )
    reasons = inspect_repository_git(candidate)
    assert {x.code for x in reasons} == {
        "initial_branch_not_main",
        "initial_remote_present",
        "unapproved_tracked_path",
        "private_paths_not_ignored",
    }
    assert all("fixture" not in x.path for x in reasons)


def test_parent_repository_is_not_the_selected_checkout(candidate: Path) -> None:
    """Refuse a nested directory even when native Git finds its parent."""
    child = candidate / "child"
    child.mkdir()
    assert "not_repository_root" in {x.code for x in inspect_repository_git(child)}


def test_missing_native_repository_and_invalid_root_refuse(tmp_path: Path) -> None:
    """Map actual failed native queries and invalid roots to safe diagnoses."""
    (tmp_path / ".git").write_text("gitdir: missing-repository\n")
    assert inspect_repository_git(tmp_path)[0].code == "git_query_unavailable"
    assert inspect_repository_git(tmp_path / "absent")[0].code == "git_query_unavailable"
    assert inspect_repository_git(Path("bad\0root"))[0].exit_code == 4


def test_large_actual_index_output_is_refused(candidate: Path) -> None:
    """Bound an actual native index listing without a substitute executable."""
    # Actual regular public inputs, indexed normally; no force-add/private bypass.
    for number in range(4200):
        (candidate / (str(number).zfill(5) + "x" * 245)).touch()
    _git(candidate, "add", "--all")
    assert inspect_repository_git(candidate)[0].code == "git_output_limit"
