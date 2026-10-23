# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — native tool bootstrap contract tests
"""Exercise real selected archives, installed files, native commands and CLI."""

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

from bootstrap_native_tools import bootstrap_native_tools, main

SOURCE = Path(__file__).resolve().parents[1]
ARCHIVES = (
    "actionlint_1.7.12_linux_amd64.tar.gz",
    "gitleaks_8.30.1_linux_x64.tar.gz",
)
BINARY = ".tool-cache/native/bin/actionlint"
LICENCE = ".tool-cache/native/licences/gitleaks/LICENSE"


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Supply the actual selected receipt and original verified release archives."""
    root = tmp_path / "checkout"
    archives = root / ".tool-cache/native-downloads"
    archives.mkdir(parents=True)
    shutil.copyfile(SOURCE / "native-tool-provenance.json", root / "native-tool-provenance.json")
    for name in ARCHIVES:
        os.link(SOURCE / ".tool-cache/native-downloads" / name, archives / name)
    return root


@pytest.fixture
def installed(candidate: Path) -> Path:
    """Install the genuine archive members through the public production API."""
    report = bootstrap_native_tools(candidate, install=True)
    assert report.exit_code == 0, report.as_dict()
    return candidate


def _invoke(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            "--branch",
            "--source=tools",
            str(SOURCE / "tools/bootstrap_native_tools.py"),
            "--root",
            str(root),
            *args,
        ],
        cwd=SOURCE,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _codes(root: Path, *, install: bool = False) -> tuple[int, set[str]]:
    report = bootstrap_native_tools(root, install=install)
    value = report.as_dict()
    assert value["gate"] == "native_tools"
    assert value["scope"] == "selected_native_files"
    return report.exit_code, {issue.code for issue in report.reasons}


def test_real_installation_matches_official_bytes_and_runs_native_versions(installed: Path) -> None:
    """Execute the genuine installed binaries and independently check their hashes."""
    expected = {
        "actionlint": (
            "c872d6db8c6bf83a8eaa704fc93999f027d55dffbc63b8a6abdccb47df5f4cd4",
            "-version",
            "1.7.12",
        ),
        "gitleaks": (
            "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509",
            "version",
            "8.30.1",
        ),
    }
    for name, (digest, argument, version) in expected.items():
        binary = installed / ".tool-cache/native/bin" / name
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == digest
        actual = subprocess.run(
            [str(binary), argument],
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert actual.stdout.splitlines()[0] == version
    assert (installed / LICENCE).read_text().startswith("MIT License")
    assert _codes(installed) == (0, set())


def test_reinstallation_and_verification_preserve_all_source_and_native_bytes(
    installed: Path,
) -> None:
    """Verify both operations leave complete valid existing files unchanged."""
    before = {
        p.relative_to(installed): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in installed.rglob("*")
        if p.is_file()
    }
    assert bootstrap_native_tools(installed, install=True).exit_code == 0
    assert bootstrap_native_tools(installed).exit_code == 0
    after = {
        p.relative_to(installed): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in installed.rglob("*")
        if p.is_file()
    }
    assert before == after


def test_read_only_verification_never_installs_missing_tools(candidate: Path) -> None:
    """Distinguish missing native files from permission to install them."""
    report = bootstrap_native_tools(candidate)
    assert report.exit_code == 3
    assert len(report.reasons) == 4
    assert not (candidate / ".tool-cache/native").exists()


@pytest.mark.parametrize("mutation", ["missing", "short", "same_size", "long"])
def test_source_receipt_cannot_reselect_the_bootstrap_policy(
    candidate: Path, mutation: str
) -> None:
    """Reject independently altered exact receipt bytes before writing anything."""
    receipt = candidate / "native-tool-provenance.json"
    original = receipt.read_bytes()
    receipt.unlink()
    if mutation == "short":
        receipt.write_bytes(b"{}")
    elif mutation == "long":
        receipt.write_bytes(original + b" ")
    elif mutation == "same_size":
        receipt.write_bytes(original.replace(b"SPIKE-QUALITY-GATE", b"SPIKE-QUALITY-GATe", 1))
    code, reasons = _codes(candidate, install=True)
    assert code == (3 if mutation == "missing" else 2)
    assert reasons
    assert not (candidate / ".tool-cache/native").exists()


@pytest.mark.parametrize("mutation", ["missing", "directory", "short", "same_size", "link"])
def test_actual_archive_admission_precedes_native_installation(
    candidate: Path, mutation: str
) -> None:
    """Refuse changed archive inputs while retaining the other selected tool result."""
    path = candidate / ".tool-cache/native-downloads" / ARCHIVES[0]
    original = path.read_bytes()
    path.unlink()
    if mutation == "directory":
        path.mkdir()
    elif mutation == "short":
        path.write_bytes(original[:-1])
    elif mutation == "same_size":
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    elif mutation == "link":
        path.symlink_to(SOURCE / ".tool-cache/native-downloads" / ARCHIVES[0])
    code, reasons = _codes(candidate, install=True)
    assert code == (3 if mutation in {"missing", "directory"} else 2)
    assert reasons
    assert not (candidate / BINARY).exists()
    assert (candidate / ".tool-cache/native/bin/gitleaks").is_file()


@pytest.mark.parametrize("name", [BINARY, LICENCE])
@pytest.mark.parametrize("mutation", ["changed", "short", "link"])
def test_existing_native_members_are_never_silently_replaced(
    installed: Path,
    name: str,
    mutation: str,
) -> None:
    """Reject altered binaries and licences without overwriting their state."""
    path = installed / name
    data = path.read_bytes()
    if mutation == "changed":
        path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    elif mutation == "short":
        path.write_bytes(data[:-1])
    else:
        path.unlink()
        path.symlink_to(installed / "native-tool-provenance.json")
    before = path.lstat().st_mtime_ns
    assert _codes(installed, install=True)[0] == 2
    assert path.lstat().st_mtime_ns == before


def test_binary_must_remain_executable(installed: Path) -> None:
    """Refuse correct executable bytes with unusable installed permissions."""
    (installed / BINARY).chmod(0o644)
    assert _codes(installed) == (2, {"native_file_not_executable"})


def test_linked_root_and_cache_ancestors_do_not_redirect_output(candidate: Path) -> None:
    """Refuse both a linked checkout and a linked native output directory."""
    linked = candidate.parent / "linked"
    linked.symlink_to(candidate, target_is_directory=True)
    assert _codes(linked, install=True) == (2, {"native_path_link_refused"})
    native = candidate / ".tool-cache/native"
    target = candidate.parent / "external"
    target.mkdir()
    native.symlink_to(target, target_is_directory=True)
    assert _codes(candidate, install=True) == (2, {"native_path_link_refused"})
    assert not list(target.iterdir())


def test_unavailable_output_and_non_directory_root_remain_failures(candidate: Path) -> None:
    """Report genuine filesystem availability failures without raw exception text."""
    native = candidate / ".tool-cache/native"
    native.write_text("existing unrelated input")
    assert _codes(candidate, install=True) == (3, {"native_output_unavailable"})
    assert native.read_text() == "existing unrelated input"
    assert _codes(native) == (3, {"native_file_unavailable"})


def test_public_cli_results_and_real_report_output_failures(
    installed: Path, tmp_path: Path
) -> None:
    """Exercise real CLI parsing, JSON, human output and unusable report streams."""
    result = _invoke(installed, "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "gate": "native_tools",
        "scope": "selected_native_files",
        "operation": "verify",
        "status": "pass",
        "reasons": [],
    }
    assert _invoke(installed).stdout == "Native file identity: pass\n"
    refused = _invoke(installed / "missing")
    assert refused.returncode == 3
    assert refused.stdout == "Native file identity: unavailable\n"
    assert _invoke(installed, "--help").returncode == 0
    assert _invoke(installed, "--unknown").returncode == 4
    output = io.StringIO()
    assert main(["--root", str(installed), "--install", "--json"], stdout=output) == 0
    assert json.loads(output.getvalue())["operation"] == "install"
    closed = io.StringIO()
    closed.close()
    assert main(["--root", str(installed)], stdout=closed) == 3
    file = tmp_path / "readonly"
    file.write_text("preserved")
    with file.open() as readonly:
        assert main(["--root", str(installed)], stdout=readonly) == 3
    assert file.read_text() == "preserved"


def test_actual_make_entry_points_use_the_selected_local_tools() -> None:
    """Reach installation and verification through their actual public Make targets."""
    result = subprocess.run(
        ["make", "native-tools", "native-tools-check"],
        cwd=SOURCE,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"gate": "native_tools"' in result.stdout


@pytest.mark.parametrize("value", ["bad\0root", "\ud800"])
@pytest.mark.parametrize("install", [False, True])
def test_invalid_root_name_refuses_before_installation(value: str, install: bool) -> None:
    """Preserve invalid-root classification in both real bootstrap operation modes."""
    report = bootstrap_native_tools(Path(value), install=install)
    assert report.exit_code == 4
    assert report.as_dict()["reasons"] == [{"path": "invocation", "code": "invalid_root"}]
    output = io.StringIO()
    args = ["--root", value, "--json", *(["--install"] if install else [])]
    assert main(args, stdout=output) == 4
    assert json.loads(output.getvalue())["status"] == "invalid"

    plain = io.StringIO()
    options = ["--install"] if install else []
    assert main(["--root", value, *options], stdout=plain) == 4
    assert plain.getvalue() == "Native file identity: invalid\n"
