# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real inventory behaviour
"""Run actual maintained checks and ordinary missing-environment refusals."""

from __future__ import annotations

import shutil
from pathlib import Path

from preflight_checks import run_check

ROOT = Path(__file__).resolve().parents[1]


def test_actual_native_and_json_checks_report_their_real_exit() -> None:
    """Execute actual metadata and native Ruff with no fabricated child result."""
    for name in ("repository-metadata", "ruff"):
        result = run_check(ROOT, name)
        assert result.exit_code == 0, result
        assert result.status == "pass"
        assert result.code == "check_passed"
        assert len(str(result.stdout_sha256)) == 64


def test_real_guard_refusal_is_retained(tmp_path: Path) -> None:
    """Run the actual guard with real missing source inputs."""
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").symlink_to(ROOT / ".venv/bin/python")
    (tmp_path / "tools").mkdir()
    shutil.copyfile(
        ROOT / "tools/check_repository_metadata.py", tmp_path / "tools/check_repository_metadata.py"
    )
    result = run_check(tmp_path, "repository-metadata")
    assert result.status == "unavailable"
    assert result.exit_code == 3
    assert result.code == "check_failed"


def test_native_bootstrap_missing_input_preserves_unavailability(tmp_path: Path) -> None:
    """Propagate the real bootstrap report and exit through the named-check boundary."""
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").symlink_to(ROOT / ".venv/bin/python")
    (tmp_path / "tools").mkdir()
    shutil.copyfile(
        ROOT / "tools/bootstrap_native_tools.py", tmp_path / "tools/bootstrap_native_tools.py"
    )
    result = run_check(tmp_path, "native-tools")
    assert result.exit_code == 3
    assert result.status == "unavailable"
    assert result.code == "check_failed"


def test_invalid_missing_and_linked_cache_are_distinct(tmp_path: Path) -> None:
    """Refuse unsupported selectors, invalid roots and real unavailable executables."""
    assert run_check(ROOT, "not-a-command").exit_code == 4
    assert run_check(Path("bad\0root"), "ruff").exit_code == 4
    assert run_check(tmp_path, "ruff").code == "required_check_unavailable"
    (tmp_path / "cache").mkdir()
    (tmp_path / ".tool-cache/preflight").rmdir()
    (tmp_path / ".tool-cache").rmdir()
    (tmp_path / ".tool-cache").symlink_to(tmp_path / "cache", target_is_directory=True)
    assert run_check(tmp_path, "ruff").code == "cache_link_refused"


def test_real_broken_source_cannot_forge_a_successful_child_report(tmp_path: Path) -> None:
    """Reject a genuine copied guard after an adverse syntax mutation."""
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").symlink_to(ROOT / ".venv/bin/python")
    (tmp_path / "tools").mkdir()
    source = (ROOT / "tools/check_repository_metadata.py").read_text()
    (tmp_path / "tools/check_repository_metadata.py").write_text(source + "\ninvalid syntax here\n")
    assert run_check(tmp_path, "repository-metadata").code == "invalid_child_report"


def test_real_wrong_gate_report_is_refused(tmp_path: Path) -> None:
    """Detect an actual copied guard after a source-level report-identity mutation."""
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").symlink_to(ROOT / ".venv/bin/python")
    (tmp_path / "tools").mkdir()
    source = (ROOT / "tools/check_repository_metadata.py").read_text()
    source = source.replace('"gate": "repository_metadata"', '"gate": "wrong_gate"')
    (tmp_path / "tools/check_repository_metadata.py").write_text(source)
    assert run_check(tmp_path, "repository-metadata").code == "invalid_child_report"


def test_real_native_output_limit_and_nonzero_status(tmp_path: Path) -> None:
    """Bound actual Ruff output and retain native failures without rewriting source."""
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/ruff").symlink_to(ROOT / ".venv/bin/ruff")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tests").mkdir()
    source = tmp_path / "tools/invalid.py"
    source.write_text("invalid syntax here\n")
    assert run_check(tmp_path, "ruff").code == "check_failed"
    source.write_text("".join(f"import unused_module_{number}\n" for number in range(15000)))
    result = run_check(tmp_path, "ruff")
    assert result.code == "child_output_limit", result
    assert "unused_module" not in str(result.as_dict())


def test_actual_secret_scanner_uses_only_public_projection(tmp_path: Path) -> None:
    """Run the real scanner on actual selected source and refuse a missing input."""
    assert run_check(ROOT, "gitleaks").exit_code == 0
    assert run_check(ROOT, "source-spdx").exit_code == 0
    result = run_check(tmp_path, "gitleaks")
    assert result.code == "source_projection_refused"
    assert result.exit_code == 3


def test_single_named_check_cli_and_destination_failures(tmp_path: Path) -> None:
    """Exercise actual scoped child CLI and fixed invocation/output diagnostics."""
    import io
    import json
    import os
    import subprocess
    import sys

    from preflight_checks import main

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--parallel-mode",
            "--source=tools",
            str(ROOT / "tools/preflight_checks.py"),
            "--root",
            str(ROOT),
            "--check",
            "repository-metadata",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["scope"] == "single_named_infrastructure_check"
    for arguments in (["--check"], ["--unknown"], []):
        stream = io.StringIO()
        assert main(arguments, output=stream) == 4
        assert json.loads(stream.getvalue())["status"] == "invalid"
    closed = io.StringIO()
    closed.close()
    assert main(["--root", str(tmp_path), "--check", "ruff"], output=closed) == 3
    assert main(["--unknown"], output=closed) == 4


def test_real_software_inventories_match_source_bytes_and_installed_versions(
    tmp_path: Path,
) -> None:
    """Exercise actual Make/native SBOM producers and compare independent source facts."""
    import hashlib
    import json
    import os
    import subprocess
    from importlib.metadata import distributions

    from packaging.utils import canonicalize_name

    from repository_policy import DIRECTORIES, PUBLIC_PATHS

    for name in PUBLIC_PATHS - DIRECTORIES:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    for name in (
        ".tool-cache/native/bin/actionlint",
        ".tool-cache/native/bin/gitleaks",
        ".tool-cache/native/licences/actionlint/LICENSE.txt",
        ".tool-cache/native/licences/gitleaks/LICENSE",
    ):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.link(ROOT / name, destination)
    (tmp_path / ".venv").symlink_to(ROOT / ".venv", target_is_directory=True)
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main"], cwd=tmp_path, check=True, timeout=15
    )
    private = tmp_path / "docs/internal/nonsecret-inventory-fixture.md"
    private.parent.mkdir(parents=True)
    private.write_text("PRIVATE_BITSTREAM_SBOM_FIXTURE_20261022")
    result = run_check(tmp_path, "sbom")
    assert result.exit_code == 0, result
    text = (tmp_path / ".tool-cache/reports/source.spdx").read_text()
    records: dict[str, str] = {}
    for block in text.split("FileName: ./")[1:]:
        lines = block.splitlines()
        records[lines[0]] = next(
            x.removeprefix("FileChecksum: SHA1: ")
            for x in lines
            if x.startswith("FileChecksum: SHA1: ")
        )
    ancillary = {name for name in PUBLIC_PATHS if name.endswith(".license")} | {
        "LICENSE",
        "LICENSES/AGPL-3.0-or-later.txt",
        "REUSE.toml",
    }
    assert set(records) == PUBLIC_PATHS - DIRECTORIES - ancillary
    assert all(
        records[name] == hashlib.sha1((ROOT / name).read_bytes(), usedforsecurity=False).hexdigest()
        for name in records
    )
    assert not any(name.startswith("docs/internal/") for name in records)
    assert "PRIVATE_BITSTREAM_SBOM_FIXTURE_20261022" not in text
    bom = json.loads((tmp_path / ".tool-cache/reports/tooling.cdx.json").read_bytes())
    actual = {canonicalize_name(x["name"]): x["version"] for x in bom["components"]}
    expected = {canonicalize_name(x.metadata["Name"]): x.version for x in distributions()}
    assert actual == expected
    assert len(actual) == 103
    assert bom["bomFormat"] == "CycloneDX"

    target = tmp_path / ".tool-cache/reports/source.spdx"
    original = private.read_bytes()
    target.unlink()
    target.symlink_to(private)
    assert run_check(tmp_path, "source-spdx").code == "source_output_link_refused"
    assert private.read_bytes() == original
    target.unlink()
    target.mkdir()
    assert run_check(tmp_path, "source-spdx").code == "required_check_unavailable"
