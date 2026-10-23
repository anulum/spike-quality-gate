# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real workflow YAML decoding
"""Exercise the public YAML decoder on actual workflow bytes and refusal inputs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from workflow_rules import MAX_BYTES, WorkflowIssue
from workflow_yaml import load_workflow_yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "filename",
    [
        "ci.yml",
        "pre-commit.yml",
        "docs.yml",
        "security-audit.yml",
        "codeql.yml",
        "sbom.yml",
        "scorecard.yml",
    ],
)
def test_actual_workflow_source_decodes_without_losing_native_scalar_types(filename: str) -> None:
    """Preserve actual workflow triggers, permissions and bounded numeric timeout values."""
    name = ".github/workflows/" + filename
    value = load_workflow_yaml((ROOT / name).read_bytes(), name)
    assert isinstance(value, dict)
    assert value["permissions"] == {"contents": "read"}
    assert value["on"] == {"push": {}, "pull_request": {}, "workflow_dispatch": {}}
    assert type(value["jobs"]["validation"]["timeout-minutes"]) is int


def test_github_boolean_resolution_does_not_mutate_the_other_native_loader() -> None:
    """Keep unquoted on/yes keys literal while preserving native true/false values."""
    before = yaml.safe_load("on: true\n")
    value = load_workflow_yaml(b"on: true\nyes: yes\nflag: false\nother: [True, False]\n", "input")
    assert value == {"on": True, "yes": "yes", "flag": False, "other": [True, False]}
    assert yaml.safe_load("on: true\n") == before == {True: True}


@pytest.mark.parametrize(
    "data",
    [
        b"\xff",
        b"jobs: [",
        b"jobs: 1\njobs: 2\n",
        b"jobs: {x: {a: 1, a: 2}}",
        b"1: non-string-key",
        b"nested: {true: unsupported-key}",
        b'name: "\\ud800"',
        b"name: .nan",
        b"name: .inf",
        b"name: -.inf",
    ],
)
def test_malformed_ambiguous_and_nonfinite_workflow_bytes_are_refused(data: bytes) -> None:
    """Return controlled diagnostics for real decoder inputs without echoing their content."""
    issue = load_workflow_yaml(data, "workflow.yml")
    assert isinstance(issue, WorkflowIssue)
    assert issue.path == "workflow.yml"
    assert issue.code == "invalid_workflow_yaml"
    assert issue.exit_code == 2


@pytest.mark.parametrize(
    "data",
    [
        b"data: &selected value\n",
        b"data: *missing\n",
        b"data: !unregistered value\n",
        b"data:\n" + b"- x\n" * 5001,
    ],
)
def test_unselected_alias_tag_and_token_populations_refuse(data: bytes) -> None:
    """Enforce the finite authored YAML feature and token population."""
    issue = load_workflow_yaml(data, "workflow.yml")
    assert isinstance(issue, WorkflowIssue)
    assert issue.code == "yaml_construct_not_selected"


def test_public_parser_byte_limit_is_enforced_without_a_filesystem_wrapper() -> None:
    """Apply the same byte boundary to direct decoder consumers."""
    issue = load_workflow_yaml(b" " * (MAX_BYTES + 1), "workflow.yml")
    assert isinstance(issue, WorkflowIssue)
    assert issue.code == "input_limit_exceeded"


def test_real_missing_yaml_package_is_unavailable_in_an_owned_environment(tmp_path: Path) -> None:
    """Run the actual public CLI with real coverage installed and PyYAML absent."""
    environment = tmp_path / "coverage-only"
    uv = ROOT / ".venv/bin/uv"
    env = {**os.environ, "UV_LINK_MODE": "hardlink"}
    create = subprocess.run(
        [str(uv), "venv", "--python", sys.executable, str(environment)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert create.returncode == 0, create.stderr
    python = environment / "bin/python"
    install = subprocess.run(
        [
            str(uv),
            "pip",
            "sync",
            "--require-hashes",
            "--python",
            str(python),
            str(ROOT / "requirements-rejection.txt"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    result = subprocess.run(
        [
            str(python),
            "-m",
            "coverage",
            "run",
            "--branch",
            "--parallel-mode",
            "--source=tools",
            str(ROOT / "tools/check_workflow_policy.py"),
            "--root",
            str(ROOT),
            "--json",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 3, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "unavailable"
    assert len(report["reasons"]) == 7
    assert {x["code"] for x in report["reasons"]} == {"required_yaml_parser_unavailable"}
