# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real complete workflow input boundary
"""Exercise the public workflow policy against actual repository inputs and CLI."""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from check_repository_metadata import LIFECYCLE, REPOSITORY_NAME
from check_workflow_policy import main, validate_workflow_policy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/check_workflow_policy.py"


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Copy the actual maintained source cohort without private data or native environments."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=15,
    )
    for raw in result.stdout.split(b"\0"):
        if raw:
            name = raw.decode()
            target = tmp_path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
    return tmp_path


def _api(root: Path, expected: int) -> list[object]:
    report = validate_workflow_policy(root)
    assert report.exit_code == expected, report.as_dict()
    document = report.as_dict()
    assert document["gate"] == "workflow_policy"
    assert document["scope"] == "local_scaffold"
    assert document["status"] == {0: "pass", 2: "refused", 3: "unavailable"}[expected]
    assert str(root) not in json.dumps(document)
    assert "executed" not in document and "qualified" not in document
    reasons = document["reasons"]
    assert isinstance(reasons, list)
    return reasons


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
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def test_real_workflow_definitions_and_native_cli_are_stable_and_read_only(candidate: Path) -> None:
    """Accept all real input files without implying native-tool, Make or hosted execution."""
    inputs = [
        candidate / "workflow-provenance.json",
        *sorted((candidate / ".github/workflows").glob("*.yml")),
    ]
    before = {p: p.read_bytes() for p in inputs}
    assert _api(candidate, 0) == []
    first = _invoke(candidate, "--json")
    second = _invoke(candidate, "--json")
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["reasons"] == []
    assert {p: p.read_bytes() for p in inputs} == before


@pytest.mark.parametrize(
    "name",
    ["workflow-provenance.json", ".github/workflows/ci.yml", ".github/workflows/codeql.yml"],
)
def test_each_required_source_input_is_not_optional(candidate: Path, name: str) -> None:
    """Locate unavailable actual files without treating an incomplete source population as pass."""
    (candidate / name).unlink()
    assert {"path": name, "code": "required_input_unavailable"} in _api(candidate, 3)


@pytest.mark.parametrize("name", ["workflow-provenance.json", ".github/workflows/ci.yml"])
def test_input_byte_limits_and_source_links_refuse(candidate: Path, name: str) -> None:
    """Apply finite reads and ordinary source-alias refusal at the public file boundary."""
    path = candidate / name
    original = path.read_bytes()
    path.write_bytes(b" " * 262_145)
    assert {"path": name, "code": "input_limit_exceeded"} in _api(candidate, 2)
    path.unlink()
    target = candidate / ".tool-cache/selected-input"
    target.parent.mkdir()
    target.write_bytes(original)
    path.symlink_to(target)
    assert {"path": name, "code": "workflow_link_refused"} in _api(candidate, 2)


def test_received_provenance_cannot_select_its_own_action_policy(candidate: Path) -> None:
    """Refuse a changed declaration independently of the supplied workflows."""
    path = candidate / "workflow-provenance.json"
    document = json.loads(path.read_text())
    document["source_actions"] = []
    path.write_text(json.dumps(document))
    assert {"path": "workflow-provenance.json", "code": "source_receipt_not_selected"} in _api(
        candidate, 2
    )


@pytest.mark.parametrize("data", [b"", b"[]", b"jobs: [", b"\xff", b"on: {}\non: {}"])
def test_malformed_or_nonobject_workflow_source_refuses(candidate: Path, data: bytes) -> None:
    """Preserve actual YAML parse and workflow-shape refusals."""
    (candidate / ".github/workflows/ci.yml").write_bytes(data)
    assert _api(candidate, 2)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("on", {"push": {"paths": ["src/**"]}}, "required_trigger_surface_filtered"),
        ("on", {"pull_request_target": {}}, "required_trigger_surface_filtered"),
        ("permissions", {"contents": "write"}, "permissions_not_read_only"),
        ("concurrency", None, "concurrency_not_selected"),
        ("defaults", {"run": {"shell": "sh"}}, "shell_defaults_not_selected"),
        ("env", {"UV_LINK_MODE": "copy"}, "tooling_environment_not_selected"),
        ("jobs", [], "jobs_not_object"),
        ("unknown", True, "workflow_fields_not_selected"),
    ],
)
def test_real_workflow_top_level_policy_mutations_are_independently_refused(
    candidate: Path,
    field: str,
    value: object,
    code: str,
) -> None:
    """Keep run-always triggers, read-only authority and the selected toolchain environment."""
    path = candidate / ".github/workflows/ci.yml"
    document = yaml.safe_load(path.read_text())
    document[field] = value
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    assert {"path": ".github/workflows/ci.yml", "code": code} in _api(candidate, 2)


def test_unknown_workflows_and_jobs_cannot_silently_escape_classification(candidate: Path) -> None:
    """Refuse actual extra source files and job populations without echoing their values."""
    path = candidate / ".github/workflows/ci.yml"
    document = yaml.safe_load(path.read_text())
    document["jobs"]["unclassified"] = copy.deepcopy(document["jobs"]["validation"])
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    assert {"path": ".github/workflows/ci.yml", "code": "job_set_not_classified"} in _api(
        candidate, 2
    )
    extra = candidate / ".github/workflows/extra.yaml"
    extra.write_bytes(path.read_bytes())
    assert {"path": ".github/workflows", "code": "workflow_set_not_classified"} in _api(
        candidate, 2
    )


def test_secret_context_is_semantic_and_not_a_comment_substring(candidate: Path) -> None:
    """Inspect actual parsed expressions while allowing an ordinary explanatory comment."""
    path = candidate / ".github/workflows/docs.yml"
    path.write_text(path.read_text() + "\n# No secrets.VALUE dependency is used.\n")
    assert _api(candidate, 0) == []
    document = yaml.safe_load(path.read_text())
    document["name"] = "$" + "{{ secrets.PRIVATE_VALUE }}"
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    assert {
        "path": ".github/workflows/docs.yml",
        "code": "secret_dependent_workflow_refused",
    } in _api(candidate, 2)


def test_unavailable_root_keeps_workflow_and_analysis_availability_visible(tmp_path: Path) -> None:
    """Do not promote an empty inaccessible source tree to successful static analysis."""
    reasons = _api(tmp_path / "absent", 3)
    assert {"path": ".github/workflows", "code": "workflow_directory_unavailable"} in reasons
    assert {"path": "source_tree", "code": "analysis_source_unavailable"} in reasons


def test_codeql_scope_enrols_actual_new_languages_and_python_locations(candidate: Path) -> None:
    """Detect newly committed analysis surfaces instead of trusting an unchanged declared matrix."""
    root_python = candidate / "application.py"
    root_python.write_bytes((candidate / "tools/check_repository_metadata.py").read_bytes())
    assert {"path": "source_tree", "code": "python_analysis_scope_omitted"} in _api(candidate, 2)
    root_python.unlink()
    native = candidate / "src/counterpart.rs"
    native.parent.mkdir()
    native.write_text("new analysis surface")
    assert {"path": "source_tree", "code": "analysis_language_not_selected"} in _api(candidate, 2)


def test_actual_caches_and_private_sources_do_not_enter_the_analysis_scope(candidate: Path) -> None:
    """Use the same declared finite source exclusions without claiming publication inspection."""
    for relative in [
        ".tool-cache/environment/module.py",
        "docs/internal/review.py",
        "tools/__pycache__/ignored.py",
    ]:
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("outside this declared source cohort")
    assert _api(candidate, 0) == []


def test_cli_human_help_invocation_and_real_report_streams(candidate: Path, tmp_path: Path) -> None:
    """Exercise the native CLI and actual report-output failure semantics."""
    result = _invoke(candidate)
    assert result.returncode == 0 and result.stdout == "workflow_policy: pass\n"
    for arguments in [("--root",), ("--unknown",)]:
        invalid = _invoke(candidate, "--json", *arguments)
        assert invalid.returncode == 4
        assert json.loads(invalid.stdout)["status"] == "invalid"
    help_result = _invoke(candidate, "--help")
    assert help_result.returncode == 0 and "Repository root" in help_result.stdout
    output = io.StringIO()
    assert main(["--root", str(candidate), "--json"], output=output) == 0
    assert json.loads(output.getvalue())["reasons"] == []
    output.close()
    assert main(["--root", str(candidate)], output=output) == 3
    destination = tmp_path / "report.txt"
    destination.write_text("preserved")
    with destination.open("r") as readonly:
        assert main(["--root", str(candidate)], output=readonly) == 3
        assert main(["--unknown"], output=readonly) == 4
    assert destination.read_text() == "preserved"


@pytest.mark.parametrize("value", ["bad\0root", "\ud800"])
def test_invalid_root_name_is_reported_by_api_and_cli(value: str) -> None:
    """Refuse unsupported root names through the actual API and command dispatcher."""
    report = validate_workflow_policy(Path(value))
    assert report.exit_code == 4
    assert report.as_dict()["reasons"] == [{"path": "invocation", "code": "invalid_root"}]
    output = io.StringIO()
    assert main(["--root", value, "--json"], output=output) == 4
    assert json.loads(output.getvalue())["status"] == "invalid"


def test_selected_workflow_receipt_states_the_repository_lifecycle() -> None:
    """Bind the selected workflow receipt to the descriptor's repository and lifecycle."""
    receipt = json.loads((ROOT / "workflow-provenance.json").read_text(encoding="utf-8"))
    assert receipt["repository_name"] == REPOSITORY_NAME
    assert receipt["lifecycle"] == LIFECYCLE
