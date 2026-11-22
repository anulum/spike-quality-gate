# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real inventory behaviour
"""Exercise acyclic generation, independent verification and exclusive real outputs."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from check_repository_inventory import inventory_operation, main
from repository_policy import DIRECTORIES, PUBLIC_PATHS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/check_repository_inventory.py"
INPUTS = ("repository-domain.json", "schemas/repository-domain.schema.json", "requirements-dev.txt")


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Copy actual metadata inputs without requiring an inventory or full tree."""
    for name in INPUTS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    return tmp_path


def _invoke(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--parallel-mode",
            "--source=tools",
            str(SOURCE),
            "--root",
            str(root),
            *arguments,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_generation_is_acyclic_deterministic_and_independently_bound(candidate: Path) -> None:
    """Generate from real metadata before the complete required tree exists."""
    before = {name: (candidate / name).read_bytes() for name in INPUTS}
    first = candidate / "first.json"
    second = candidate / "second.json"
    one = _invoke(candidate, "--mode", "generate", "--output", str(first), "--json")
    two = _invoke(candidate, "--mode", "generate", "--output", str(second), "--json")
    assert one.returncode == two.returncode == 0
    assert one.stdout == two.stdout
    assert json.loads(one.stdout)["scope"] == "validated_metadata_generation"
    assert first.read_bytes() == second.read_bytes()
    value = json.loads(first.read_bytes())
    assert value == {
        "repository_name": "SPIKE-QUALITY-GATE",
        "lifecycle": "public_repository",
        "evidence_maturity": "architecture_only",
        "capabilities": [],
        "claims": [],
        "qualified_owned_schema_ids": [],
        "source_metadata": {
            "path": "repository-domain.json",
            "sha256": hashlib.sha256(before["repository-domain.json"]).hexdigest(),
        },
    }
    assert {name: (candidate / name).read_bytes() for name in INPUTS} == before
    assert inventory_operation(candidate).exit_code == 3


def test_real_completed_tree_and_native_index_verify_readonly(tmp_path: Path) -> None:
    """Verify actual authored implementation through the public CLI and native Git."""
    for name in sorted(PUBLIC_PATHS - DIRECTORIES):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main"], cwd=tmp_path, check=True, timeout=15
    )
    before = (tmp_path / "capability-inventory.json").read_bytes()
    result = _invoke(tmp_path, "--json")
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["scope"] == "initial_repository_tree_and_index"
    assert (tmp_path / "capability-inventory.json").read_bytes() == before
    (tmp_path / "README.md").unlink()
    result = _invoke(tmp_path, "--json")
    assert result.returncode == 3
    assert any(x["path"] == "README.md" for x in json.loads(result.stdout)["reasons"])


@pytest.mark.parametrize("kind", ["file", "directory", "link"])
def test_exclusive_publication_preserves_every_existing_target(candidate: Path, kind: str) -> None:
    """Refuse real occupied outputs without rewriting their contents or link."""
    output = candidate / "occupied"
    if kind == "file":
        output.write_bytes(b"keep this original")
    elif kind == "directory":
        output.mkdir()
    else:
        output.symlink_to(candidate / INPUTS[0])
    report = inventory_operation(candidate, mode="generate", output=output)
    assert report.exit_code == 2
    assert report.reasons[0].code == "exclusive_output_exists"
    assert not list(candidate.glob(".inventory-*"))
    if kind == "file":
        assert output.read_bytes() == b"keep this original"
    elif kind == "link":
        assert output.is_symlink()
    else:
        assert output.is_dir()


def test_output_availability_links_and_invalid_name_are_safe(candidate: Path) -> None:
    """Map real failed creation and linked parents without exposing caller paths."""
    missing = inventory_operation(candidate, mode="generate", output=candidate / "absent/out")
    assert missing.exit_code == 3
    (candidate / "linked").symlink_to(candidate / "schemas", target_is_directory=True)
    assert (
        inventory_operation(candidate, mode="generate", output=candidate / "linked/out").exit_code
        == 2
    )
    for name in ("bad\0output", "\ud800"):
        assert inventory_operation(candidate, mode="generate", output=Path(name)).exit_code == 4


@pytest.mark.parametrize(
    "mode,output", [("other", None), ("generate", None), ("verify", Path("out"))]
)
def test_invalid_mode_output_combinations_refuse(
    candidate: Path, mode: str, output: Path | None
) -> None:
    """Prevent generation or rewriting through an invalid operation combination."""
    assert inventory_operation(candidate, mode=mode, output=output).exit_code == 4


def test_metadata_and_linked_input_fail_before_output(candidate: Path) -> None:
    """Refuse actual changed source identity, schema and linked input dependencies."""
    metadata = candidate / INPUTS[0]
    original = metadata.read_bytes()
    metadata.write_bytes(original.replace(b"SPIKE-QUALITY-GATE", b"wrong-owner"))
    output = candidate / "new"
    assert inventory_operation(candidate, mode="generate", output=output).exit_code == 2
    assert not output.exists()
    metadata.unlink()
    metadata.symlink_to(ROOT / INPUTS[0])
    assert (
        inventory_operation(candidate, mode="generate", output=output).reasons[0].code
        == "input_link_refused"
    )
    assert inventory_operation(Path("bad\0root"), mode="generate", output=output).exit_code == 4


@pytest.mark.parametrize(
    "raw",
    [
        b'{"claims":[],"claims":[]}',
        b'{"claims":NaN}',
        b'{"claims":Infinity}',
        b'"\\ud800"',
        b"\xff",
        b"{",
        b"[" * 1200 + b"]" * 1200,
        b'{"claims":["not implemented"]}',
        b"null",
    ],
)
def test_malformed_unqualified_or_unknown_inventory_never_qualifies(
    candidate: Path, raw: bytes
) -> None:
    """Reject strict JSON failures and mismatched initial populations."""
    (candidate / "capability-inventory.json").write_bytes(raw)
    report = inventory_operation(candidate)
    assert any(
        x.code in {"invalid_inventory_json", "inventory_not_selected"} for x in report.reasons
    )
    assert report.exit_code != 0


def test_json_text_help_invocation_and_real_report_output_failure(candidate: Path) -> None:
    """Exercise actual public CLI projections and closed destination handling."""
    for arguments in (["--mode", "bad"], ["--unknown"], ["--mode"]):
        stream = io.StringIO()
        assert main([*arguments, "--json"], output=stream) == 4
        assert json.loads(stream.getvalue())["status"] == "invalid"
    for json_flag in ([], ["--json"]):
        stream = io.StringIO()
        assert main(["--root", str(candidate), *json_flag], output=stream) == 3
        assert stream.getvalue()
    help_result = _invoke(candidate, "--help")
    assert help_result.returncode == 0
    assert "usage:" in help_result.stdout
    closed = io.StringIO()
    closed.close()
    assert main(["--root", str(candidate)], output=closed) == 3
    assert main(["--unknown"], output=closed) == 4


def test_native_probe_success_cannot_authorise_an_unselected_private_exception(
    tmp_path: Path,
) -> None:
    """Reject a real filename-specific ignore exception missed by finite native probes."""
    from repository_git import inspect_repository_git

    for name in PUBLIC_PATHS - DIRECTORIES:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main"], cwd=tmp_path, check=True, timeout=15
    )
    ignore = tmp_path / ".gitignore"
    ignore.write_text(
        ignore.read_text()
        + "\n!/docs/internal/\n/docs/internal/**\n!/docs/internal/nonsecret-specific.md\n"
    )
    private = tmp_path / "docs/internal/nonsecret-specific.md"
    private.parent.mkdir(parents=True)
    private.write_text("nonsecret private policy fixture")
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "docs/internal/nonsecret-specific.md"],
        cwd=tmp_path,
        check=False,
        timeout=15,
    )
    assert result.returncode == 1
    assert inspect_repository_git(tmp_path) == ()
    report = inventory_operation(tmp_path)
    assert report.exit_code == 2
    assert any(
        x.path == ".gitignore" and x.code == "configuration_not_selected" for x in report.reasons
    )
