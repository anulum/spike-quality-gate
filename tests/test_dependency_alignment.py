# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — dependency alignment contract tests
"""Exercise actual locks, source inputs, isolated installations and public commands."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from importlib.metadata import distributions
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from check_dependency_alignment import main, validate_dependency_alignment

SOURCE = Path(__file__).resolve().parents[1]
RECEIPT = json.loads((SOURCE / "dependency-provenance.json").read_bytes())
INPUTS = tuple(RECEIPT["selection"]["file_sha256"])
NATIVE_FILES = (
    ".tool-cache/native/bin/actionlint",
    ".tool-cache/native/bin/gitleaks",
    ".tool-cache/native/licences/actionlint/LICENSE.txt",
    ".tool-cache/native/licences/gitleaks/LICENSE",
)


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Supply real selected inputs and immutable native files without copying binaries."""
    root = tmp_path / "checkout"
    root.mkdir()
    for name in (*INPUTS, "dependency-provenance.json"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, path)
    for name in NATIVE_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        os.link(SOURCE / name, path)
    return root


@pytest.fixture(scope="module")
def isolated_environment(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Install the actual lock offline through uv with immutable hard-linked payloads."""
    root = tmp_path_factory.mktemp("dependency-environment") / "venv"
    uv = SOURCE / ".venv/bin/uv"
    for command in (
        [str(uv), "venv", "--python", sys.executable, str(root)],
        [
            str(uv),
            "pip",
            "sync",
            "--offline",
            "--require-hashes",
            "--build-constraints",
            str(SOURCE / "requirements-dev.txt"),
            "--python",
            str(root / "bin/python"),
            str(SOURCE / "requirements-dev.txt"),
        ],
        [str(uv), "pip", "check", "--python", str(root / "bin/python")],
    ):
        actual = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        assert actual.returncode == 0, actual.stdout + actual.stderr
        assert "falling back" not in actual.stderr.lower()
    yield root
    shutil.rmtree(root)


def _invoke(root: Path, *args: str, python: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(python) if python is not None else sys.executable,
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            "--branch",
            "--source=tools",
            str(SOURCE / "tools/check_dependency_alignment.py"),
            "--root",
            str(root),
            *args,
        ],
        cwd=SOURCE,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def _codes(root: Path) -> tuple[int, set[str]]:
    report = validate_dependency_alignment(root)
    assert report.as_dict()["scope"] == "selected_tooling_inputs_and_installed_metadata"
    return report.exit_code, {issue.code for issue in report.reasons}


def test_actual_public_api_cli_and_make_preserve_selected_inputs(candidate: Path) -> None:
    """Exercise public entry points and verify deterministic read-only outcomes."""
    before = {
        name: (candidate / name).read_bytes() for name in (*INPUTS, "dependency-provenance.json")
    }
    assert _codes(candidate) == (0, set())
    first = _invoke(candidate, "--json")
    second = _invoke(candidate, "--json")
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout) == {
        "gate": "dependency_alignment",
        "scope": "selected_tooling_inputs_and_installed_metadata",
        "status": "pass",
        "reasons": [],
    }
    make = subprocess.run(
        ["make", "dependencies"],
        cwd=SOURCE,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert make.returncode == 0, make.stdout + make.stderr
    hook = subprocess.run(
        [str(SOURCE / ".venv/bin/pre-commit"), "run", "dependency-alignment", "--all-files"],
        cwd=SOURCE,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert hook.returncode == 0, hook.stdout + hook.stderr
    assert "Passed" in hook.stdout
    assert all((candidate / name).read_bytes() == data for name, data in before.items())


def test_actual_reinstalled_graph_passes_the_public_command(
    candidate: Path, isolated_environment: Path
) -> None:
    """Independently resolve the selected lock through uv and check the fresh installation."""
    report = _invoke(candidate, "--json", python=isolated_environment / "bin/python")
    assert report.returncode == 0, report.stdout + report.stderr


def test_source_receipt_matches_actual_metadata_and_each_package_lock_block() -> None:
    """Check licences, raw dependencies and archive membership using independent metadata APIs."""
    installed = {canonicalize_name(d.metadata["Name"]): d for d in distributions()}
    assert len(installed) == len(RECEIPT["packages"]) == 103
    direct = {
        canonicalize_name(Requirement(line).name)
        for line in (SOURCE / "requirements-dev.in").read_text().splitlines()
        if line and not line.startswith("#")
    }
    assert len(direct) == 24
    lock = (SOURCE / "requirements-dev.txt").read_text()
    blocks: dict[str, str] = {}
    current = ""
    for line in lock.splitlines():
        if line and not line.startswith((" ", "#")):
            current = canonicalize_name(Requirement(line.removesuffix(" \\")).name)
            blocks[current] = ""
        elif current:
            blocks[current] += line + "\n"
    for record in RECEIPT["packages"]:
        name = record["name"]
        actual = installed[name]
        assert record["version"] == actual.version
        assert record["role"] == ("direct" if name in direct else "transitive")
        assert record["licence_expression"] == actual.metadata.get("License-Expression")
        assert record["licence_label"] == actual.metadata.get("License")
        assert record["licence_classifiers"] == [
            x for x in actual.metadata.get_all("Classifier", []) if x.startswith("License ::")
        ]
        assert record["requires_dist"] == (actual.requires or [])
        assert "--hash=sha256:" + record["source_artifact"]["sha256"] in blocks[name]
        assert (
            hashlib.sha256(
                actual.locate_file(record["installed_metadata_path"]).read_bytes()
            ).hexdigest()
            == record["installed_metadata_sha256"]
        )


@pytest.mark.parametrize("name", INPUTS)
def test_every_input_is_independently_source_selected(candidate: Path, name: str) -> None:
    """Refuse changed direct pins, hashes, hooks, tool selectors and workflow configurations."""
    path = candidate / name
    path.write_bytes(path.read_bytes() + b"\n")
    report = validate_dependency_alignment(candidate)
    assert report.exit_code == 2
    assert any(x.path == name and x.code == "tooling_input_not_selected" for x in report.reasons)


@pytest.mark.parametrize(
    "mutation,expected",
    [("missing", 3), ("directory", 2), ("linked", 2), ("oversized", 2)],
)
def test_source_input_availability_and_bounds(
    candidate: Path, mutation: str, expected: int
) -> None:
    """Distinguish unavailable input from nonregular, linked and oversized files."""
    path = candidate / "requirements-dev.in"
    path.unlink()
    if mutation == "directory":
        path.mkdir()
    elif mutation == "linked":
        path.symlink_to(SOURCE / "requirements-dev.in")
    elif mutation == "oversized":
        path.write_bytes(b"x" * 2_097_153)
    assert _codes(candidate)[0] == expected


@pytest.mark.parametrize("field", ["licence_label", "requires_dist", "purpose", "version"])
def test_metadata_projection_cannot_be_forged_in_received_receipt(
    candidate: Path, field: str
) -> None:
    """Refuse altered descriptions even when original installed METADATA hashes stay intact."""
    value = json.loads((candidate / "dependency-provenance.json").read_bytes())
    value["packages"][0][field] = "RECEIVED_TEXT_MUST_NOT_ESCAPE"
    (candidate / "dependency-provenance.json").write_text(json.dumps(value))
    actual = _invoke(candidate, "--json")
    assert actual.returncode == 2
    assert "receipt_not_selected" in actual.stdout
    assert "RECEIVED_TEXT" not in actual.stdout + actual.stderr


def test_missing_receipt_is_unavailable_and_other_errors_remain_visible(candidate: Path) -> None:
    """Retain controlled receipt availability without trusting a substituted receipt."""
    (candidate / "dependency-provenance.json").unlink()
    assert _codes(candidate) == (3, {"input_unavailable"})


def test_linked_checkout_and_linked_input_ancestor_refuse(candidate: Path, tmp_path: Path) -> None:
    """Refuse source links at both the root and nested input directory."""
    linked = tmp_path / "linked"
    linked.symlink_to(candidate, target_is_directory=True)
    assert _codes(linked) == (2, {"input_link_refused"})
    original = candidate / ".github/workflows"
    original.rename(candidate / ".github/retained-workflows")
    original.symlink_to("retained-workflows", target_is_directory=True)
    assert "input_link_refused" in _codes(candidate)[1]


@pytest.mark.parametrize(
    "mutation,expected",
    [("missing", 3), ("changed", 2), ("directory", 2), ("linked", 2), ("long", 2)],
)
def test_actual_installed_metadata_changes_refuse(
    candidate: Path, isolated_environment: Path, mutation: str, expected: int
) -> None:
    """Change only disposable copied metadata in a real separately installed environment."""
    site = isolated_environment / "lib/python3.13/site-packages"
    name = "packaging-26.3.dist-info/METADATA"
    path = site / name
    original = path.read_bytes()
    path.unlink()
    try:
        if mutation == "changed":
            path.write_bytes(original.replace(b"Version: 26.3", b"Version: 26.4"))
        elif mutation == "directory":
            path.mkdir()
        elif mutation == "linked":
            path.symlink_to(SOURCE / ".venv/lib/python3.13/site-packages" / name)
        elif mutation == "long":
            path.write_bytes(b"x" * 2_097_153)
        actual = _invoke(candidate, "--json", python=isolated_environment / "bin/python")
        assert actual.returncode == expected, actual.stdout + actual.stderr
        assert name in actual.stdout
    finally:
        if path.is_dir() and not path.is_symlink():
            path.rmdir()
        elif path.exists() or path.is_symlink():
            path.unlink()
        path.write_bytes(original)


def test_unselected_distribution_is_refused_without_echoing_its_name(
    candidate: Path, isolated_environment: Path
) -> None:
    """Detect extra installed metadata without publishing its supplied directory name."""
    path = isolated_environment / "lib/python3.13/site-packages/RECEIVED_TEXT.dist-info"
    path.mkdir()
    try:
        actual = _invoke(candidate, "--json", python=isolated_environment / "bin/python")
        assert actual.returncode == 2
        assert "unselected_distribution" in actual.stdout
        assert "RECEIVED_TEXT" not in actual.stdout + actual.stderr
    finally:
        path.rmdir()


@pytest.mark.parametrize("mutation", ["missing", "not_executable"])
def test_selected_console_script_must_exist_and_be_executable(
    candidate: Path, isolated_environment: Path, mutation: str
) -> None:
    """Refuse both absent and nonexecutable real selected console entry points."""
    path = isolated_environment / "bin/ruff"
    retained = isolated_environment / "bin/retained-ruff"
    path.rename(retained)
    if mutation == "not_executable":
        path.write_bytes(b"nonexecutable file")
    try:
        actual = _invoke(candidate, "--json", python=isolated_environment / "bin/python")
        assert actual.returncode == 3
        assert "selected_console_script_unavailable" in actual.stdout
    finally:
        if mutation == "not_executable":
            path.unlink()
        retained.rename(path)


def test_missing_native_tool_cannot_pass_dependency_alignment(candidate: Path) -> None:
    """Retain the selected native-file gate rather than checking declarations alone."""
    (candidate / NATIVE_FILES[0]).unlink()
    assert "native_file_unavailable" in _codes(candidate)[1]


def test_wrong_actual_interpreter_refuses(candidate: Path) -> None:
    """Use the genuine separately selected rejection runtime, never a changed version string."""
    selected = shutil.which(os.environ.get("SPIKE_QUALITY_GATE_REJECTION_PYTHON", "python3.12"))
    assert selected is not None
    rejection = Path(selected)
    actual = _invoke(candidate, "--json", python=rejection)
    assert actual.returncode == 3, actual.stdout + actual.stderr
    assert "interpreter_not_selected" in actual.stdout


def test_selected_base_interpreter_requires_a_virtual_environment(candidate: Path) -> None:
    """Refuse a genuine supported interpreter running outside a virtual environment."""
    executable = Path(sys.base_prefix) / "bin/python3.13"
    environment = dict(os.environ, PYTHONPATH=str(SOURCE / ".venv/lib/python3.13/site-packages"))
    environment.pop("VIRTUAL_ENV", None)
    actual = subprocess.run(
        [
            str(executable),
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            "--branch",
            "--source=tools",
            str(SOURCE / "tools/check_dependency_alignment.py"),
            "--root",
            str(candidate),
            "--json",
        ],
        cwd=SOURCE,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert actual.returncode == 3, actual.stdout + actual.stderr
    report = json.loads(actual.stdout)
    assert report["status"] == "unavailable"
    codes = {reason["code"] for reason in report["reasons"]}
    assert "virtual_environment_required" in codes
    assert "interpreter_not_selected" not in codes


@pytest.mark.parametrize("args", [("--root",), ("--json=received",), ("--unknown",)])
def test_invalid_cli_arguments_are_controlled(args: tuple[str, ...]) -> None:
    """Return authored invocation diagnostics without interpreter error text."""
    output = io.StringIO()
    assert main(["--json", *args], stdout=output) == 4
    assert json.loads(output.getvalue())["status"] == "invalid"


def test_plain_text_failure_and_closed_output_preserve_real_exit_codes(candidate: Path) -> None:
    """Exercise textual diagnostics and output failure without discarding configuration refusal."""
    (candidate / "requirements-dev.in").unlink()
    output = io.StringIO()
    assert main(["--root", str(candidate)], stdout=output) == 3
    assert "requirements-dev.in: input_unavailable" in output.getvalue()
    output.close()
    assert main(["--root", str(candidate)], stdout=output) == 3
    assert main(["--unknown"], stdout=output) == 4


def test_successful_report_to_unavailable_output_is_not_success(candidate: Path) -> None:
    """Use a real unwritable stream as the public API report destination."""
    with (candidate / "requirements-dev.in").open("r") as output:
        assert main(["--root", str(candidate), "--json"], stdout=output) == 3


def test_help_is_informational_and_does_not_claim_alignment() -> None:
    """Exercise the real help operation independently of a successful gate report."""
    actual = _invoke(SOURCE, "--help")
    assert actual.returncode == 0
    assert "--root" in actual.stdout and '"status"' not in actual.stdout


def test_installed_directory_population_is_bounded(
    candidate: Path, isolated_environment: Path
) -> None:
    """Refuse an oversized real site directory instead of scanning indefinitely."""
    site = isolated_environment / "lib/python3.13/site-packages"
    created = [site / f"selected-limit-fixture-{i}" for i in range(4097)]
    try:
        for path in created:
            path.touch()
        actual = _invoke(candidate, "--json", python=isolated_environment / "bin/python")
        assert actual.returncode == 2
        assert "site_entry_limit_exceeded" in actual.stdout
    finally:
        for path in created:
            path.unlink()


def test_missing_actual_installed_directory_is_unavailable(
    candidate: Path, isolated_environment: Path, tmp_path: Path
) -> None:
    """Run the public API after loading it and removing only the owned metadata location."""
    site = isolated_environment / "lib/python3.13/site-packages"
    driver = tmp_path / "missing_site.py"
    driver.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "from check_dependency_alignment import validate_dependency_alignment\n"
        "site=Path(sys.argv[1]); retained=site.with_name('retained-site')\n"
        "site.rename(retained)\ntry:\n"
        " report=validate_dependency_alignment(Path(sys.argv[2]))\n"
        " print(json.dumps(report.as_dict())); result=report.exit_code\n"
        "finally:\n retained.rename(site)\nraise SystemExit(result)\n"
    )
    environment = dict(os.environ, PYTHONPATH=str(SOURCE / "tools"))
    actual = subprocess.run(
        [
            str(isolated_environment / "bin/python"),
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            "--branch",
            "--source=tools",
            str(driver),
            str(site),
            str(candidate),
        ],
        cwd=SOURCE,
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert actual.returncode == 3, actual.stdout + actual.stderr
    assert "site_unavailable" in actual.stdout
    assert site.is_dir()


@pytest.mark.parametrize("value", ["\0", "\ud800"])
def test_invalid_root_arguments_have_fixed_public_diagnostics(value: str) -> None:
    """Refuse filesystem-unrepresentable API and CLI roots without exception text."""
    report = validate_dependency_alignment(Path(value))
    assert report.exit_code == 4
    assert report.as_dict()["reasons"] == [
        {"path": "invocation", "code": "invalid_repository_root"}
    ]
    output = io.StringIO()
    assert main(["--root", value, "--json"], stdout=output) == 4
    assert json.loads(output.getvalue()) == report.as_dict()
