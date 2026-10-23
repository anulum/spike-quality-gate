# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real metadata API and CLI contracts
"""Exercise actual selected metadata through the library and subprocess command."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from check_repository_metadata import main, repository_schema, validate_repository_metadata

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "check_repository_metadata.py"
INPUTS = (
    "repository-domain.json",
    "schemas/repository-domain.schema.json",
    "requirements-dev.txt",
)


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Copy only the actual three consumed metadata inputs to an owned candidate."""
    for name in INPUTS:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    return tmp_path


def _invoke(
    root: Path, *arguments: str, json_output: bool = True
) -> subprocess.CompletedProcess[str]:
    command = [
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
    ]
    if json_output:
        command.append("--json")
    command.extend(arguments)
    return subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def _report(result: subprocess.CompletedProcess[str], exit_code: int) -> dict[str, object]:
    assert result.returncode == exit_code, result.stderr
    report: dict[str, object] = json.loads(result.stdout)
    assert set(report) == {"gate", "scope", "status", "reasons"}
    assert report["gate"] == "repository_metadata"
    assert report["scope"] == "local_scaffold"
    assert report["status"] == {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[exit_code]
    return report


def _api_report(root: Path, exit_code: int) -> dict[str, object]:
    report = validate_repository_metadata(root)
    assert report.exit_code == exit_code
    return report.as_dict()


def test_actual_selected_repository_and_repeated_command_are_stable(candidate: Path) -> None:
    """Accept real selected inputs without rewriting them or implying domain success."""
    before = {name: (candidate / name).read_bytes() for name in INPUTS}
    first = _invoke(candidate)
    second = _invoke(candidate)
    assert first.stdout == second.stdout
    assert _report(first, 0)["reasons"] == []
    assert str(candidate) not in first.stdout
    assert {name: (candidate / name).read_bytes() for name in INPUTS} == before
    assert validate_repository_metadata(candidate).exit_code == 0
    Draft202012Validator(repository_schema()).validate(
        json.loads((candidate / INPUTS[0]).read_text())
    )


def test_schema_generation_is_valid_and_has_no_persistent_mutable_selection() -> None:
    """Reproduce the committed schema through the public generator and external checker."""
    supplied: dict[str, object] = json.loads((ROOT / INPUTS[1]).read_text())
    generated = repository_schema()
    Draft202012Validator.check_schema(generated)
    assert generated == supplied
    generated["title"] = "changed local object"
    assert repository_schema() == supplied


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("repository_name", "another-project"),
        ("owner_group", "another-group"),
        ("lifecycle", "implemented_capability"),
        ("evidence_maturity", "qualified"),
        ("capabilities", ["run"]),
        ("claims", ["equivalent"]),
        ("qualified_owned_schema_ids", ["event_data_quality.report.v1"]),
        ("domain_runtime_dependencies", ["sc-neurocore"]),
        ("planned_owned_schema_ids", []),
        ("validation_profile.id", "another-profile"),
        ("validation_profile.revision", "older"),
        ("validation_profile.profile_sha256", "0" * 64),
        ("validation_profile.standard_sha256", "0" * 64),
        ("tooling_python.actual_version", "3.12.0"),
        ("tooling_python.design_baseline", "3.12"),
        ("tooling_python.supported_range", ">=3.12"),
        ("tooling_python.development_lock_sha256", "0" * 64),
        ("schema_id", "unselected-evidence-format"),
        ("claims", None),
        ("capabilities", False),
    ],
)
def test_each_selected_identity_claim_and_toolchain_boundary_refuses(
    candidate: Path, path: str, value: object
) -> None:
    """Reject every independently changed field through the real public file API."""
    target = candidate / INPUTS[0]
    metadata: dict[str, object] = json.loads(target.read_text())
    head, separator, tail = path.partition(".")
    if separator:
        block = metadata[head]
        assert isinstance(block, dict)
        block[tail] = value
    else:
        metadata[head] = value
    target.write_text(json.dumps(metadata))
    assert not Draft202012Validator(repository_schema()).is_valid(metadata)
    report = _api_report(candidate, 2)
    assert report["reasons"] == [{"path": INPUTS[0], "code": "metadata_not_selected"}]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"{",
        b"\xff",
        b'{"x":1,"x":2}',
        b'{"nested":{"x":1,"x":2}}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
    ],
)
def test_malformed_duplicate_and_nonfinite_metadata_refuses(candidate: Path, data: bytes) -> None:
    """Reject actual byte inputs before schema interpretation can normalise them."""
    (candidate / INPUTS[0]).write_bytes(data)
    assert _api_report(candidate, 2)["reasons"] == [
        {"path": INPUTS[0], "code": "invalid_metadata_json"}
    ]


@pytest.mark.parametrize(
    "data",
    [
        b"[]",
        b"null",
        b"false",
        b"1",
        b'{"repository_name":"x"}',
        pytest.param(b'{"nested":' * 2000 + b"0" + b"}" * 2000, id="unselected-nested-object"),
    ],
)
def test_wrong_root_shape_and_incomplete_population_refuse(candidate: Path, data: bytes) -> None:
    """Require the complete closed descriptor rather than a truthy partial result."""
    (candidate / INPUTS[0]).write_bytes(data)
    _api_report(candidate, 2)


@pytest.mark.parametrize("name", INPUTS)
def test_missing_required_input_is_unavailable(candidate: Path, name: str) -> None:
    """Distinguish missing real inputs from an accepted or ordinary refused candidate."""
    (candidate / name).unlink()
    assert _api_report(candidate, 3)["reasons"] == [
        {"path": name, "code": "required_input_unavailable"}
    ]


@pytest.mark.parametrize(("name", "exit_code"), [(INPUTS[0], 2), (INPUTS[1], 4), (INPUTS[2], 2)])
def test_each_input_has_a_bounded_read(candidate: Path, name: str, exit_code: int) -> None:
    """Refuse oversized metadata, schema and lock bytes with their declared precedence."""
    (candidate / name).write_bytes(b" " * 1_048_577)
    assert _api_report(candidate, exit_code)["reasons"] == [
        {"path": name, "code": "input_limit_exceeded"}
    ]


def test_candidate_schema_cannot_accept_its_own_new_claims(candidate: Path) -> None:
    """Reject a weakened schema even when candidate content would satisfy that schema."""
    (candidate / INPUTS[1]).write_text('{"type":"object"}\n')
    (candidate / INPUTS[0]).write_text('{"claims":["equivalent"]}\n')
    assert _report(_invoke(candidate), 4)["reasons"] == [
        {"path": INPUTS[1], "code": "schema_not_selected"},
        {"path": INPUTS[0], "code": "metadata_not_selected"},
    ]


def test_schema_identity_uses_exact_selected_bytes(candidate: Path) -> None:
    """Do not silently rebind a reformatted or changed schema."""
    path = candidate / INPUTS[1]
    path.write_bytes(path.read_bytes() + b"\n")
    _api_report(candidate, 4)


def test_changed_lock_is_not_qualified_by_unchanged_metadata(candidate: Path) -> None:
    """Check actual lock bytes independently of their declared digest."""
    path = candidate / INPUTS[2]
    path.write_bytes(path.read_bytes() + b"\n")
    assert _report(_invoke(candidate), 2)["reasons"] == [
        {"path": INPUTS[2], "code": "development_lock_changed"}
    ]


def test_all_missing_inputs_remain_visible(candidate: Path) -> None:
    """Keep the full input failure population in deterministic order."""
    for name in INPUTS:
        (candidate / name).unlink()
    assert _report(_invoke(candidate), 3)["reasons"] == [
        {"path": INPUTS[1], "code": "required_input_unavailable"},
        {"path": INPUTS[0], "code": "required_input_unavailable"},
        {"path": INPUTS[2], "code": "required_input_unavailable"},
    ]


def test_unavailable_precedes_refusal_and_configuration_precedes_unavailable(
    candidate: Path,
) -> None:
    """Preserve the selected 4 then 3 then 2 outcome order across real input failures."""
    (candidate / INPUTS[2]).unlink()
    (candidate / INPUTS[0]).write_text("{}")
    _report(_invoke(candidate), 3)
    (candidate / INPUTS[1]).write_text("{}")
    _report(_invoke(candidate), 4)


def test_plain_text_diagnostics_and_informational_help(candidate: Path) -> None:
    """Exercise the public human-readable command without treating help as validation."""
    result = _invoke(candidate, json_output=False)
    assert result.returncode == 0
    assert result.stdout == "repository_metadata: pass\n"
    (candidate / INPUTS[0]).write_text("{}")
    result = _invoke(candidate, json_output=False)
    assert result.returncode == 2
    assert "repository-domain.json: metadata_not_selected" in result.stdout
    help_result = _invoke(candidate, "--help")
    assert help_result.returncode == 0
    assert "Repository root" in help_result.stdout


@pytest.mark.parametrize("arguments", [("--unknown",), ("--root",)])
def test_invalid_invocation_is_a_controlled_configuration_outcome(
    candidate: Path, arguments: tuple[str, ...]
) -> None:
    """Return authored diagnostics instead of an interpreter traceback or ignored argument."""
    _report(_invoke(candidate, *arguments), 4)


def test_public_report_destination_and_output_failures(candidate: Path, tmp_path: Path) -> None:
    """Use real streams to verify report delivery and refusal on unavailable output."""
    output = io.StringIO()
    assert main(["--root", str(candidate), "--json"], output=output) == 0
    assert json.loads(output.getvalue())["reasons"] == []
    output.close()
    assert main(["--root", str(candidate), "--json"], output=output) == 3
    destination = tmp_path / "report.txt"
    destination.write_text("existing output")
    with destination.open("r") as read_only:
        assert main(["--root", str(candidate), "--json"], output=read_only) == 3
        (candidate / INPUTS[1]).write_text("{}")
        assert main(["--root", str(candidate), "--json"], output=read_only) == 4
    assert destination.read_text() == "existing output"


def test_actual_unsupported_interpreter_is_not_qualified_by_selected_metadata(
    candidate: Path,
) -> None:
    """Refuse the unchanged selected descriptor under a genuinely different runtime."""
    executable = shutil.which(os.environ.get("SPIKE_QUALITY_GATE_REJECTION_PYTHON", "python3.12"))
    assert executable is not None, "A real rejection-test Python with coverage is required"
    result = subprocess.run(
        [
            executable,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--parallel-mode",
            "--source=tools",
            str(SOURCE),
            "--root",
            str(candidate),
            "--json",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert _report(result, 3)["reasons"] == [
        {"path": "tooling_python", "code": "interpreter_not_selected"}
    ]


@pytest.mark.parametrize("value", ["bad\0root", "\ud800"])
def test_invalid_root_name_is_reported_by_api_and_cli(value: str) -> None:
    """Reject invalid filesystem names before source reads without leaking exceptions."""
    report = validate_repository_metadata(Path(value))
    assert report.exit_code == 4
    assert report.as_dict()["reasons"] == [{"path": "invocation", "code": "invalid_root"}]
    output = io.StringIO()
    assert main(["--root", value, "--json"], output=output) == 4
    assert json.loads(output.getvalue())["status"] == "invalid"
