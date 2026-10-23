# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real workflow job contracts
"""Mutate actual maintained workflow jobs through the public job-policy API."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from workflow_rules import WorkflowReport, check_job_policy

ROOT = Path(__file__).resolve().parents[1]


def _job(filename: str) -> dict[str, object]:
    document = yaml.safe_load((ROOT / ".github/workflows" / filename).read_text())
    job: dict[str, object] = document["jobs"]["validation"]
    return job


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
def test_actual_complete_job_roles_and_selected_actions_are_admitted(filename: str) -> None:
    """Check every real required source job rather than a hand-written minimal job."""
    assert check_job_policy(".github/workflows/" + filename, _job(filename), aggregate=False) == []


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("env", {}, "job_scope_unclassified"),
        ("env", "not-an-object", "job_environment_not_selected"),
        ("timeout-minutes", 0, "job_timeout_unbounded"),
        ("timeout-minutes", True, "job_timeout_unbounded"),
        ("timeout-minutes", 31, "job_timeout_unbounded"),
        ("runs-on", "self-hosted", "runner_not_selected"),
        ("permissions", {"contents": "write"}, "job_permissions_not_read_only"),
        ("continue-on-error", True, "job_failure_hidden"),
        ("unknown-field", True, "job_fields_not_selected"),
        ("strategy", {}, "matrix_cancels_evidence"),
        ("strategy", "bad", "matrix_not_selected"),
        ("steps", [], "steps_not_selected"),
        ("steps", "bad", "steps_not_selected"),
        ("steps", [{}] * 21, "steps_not_selected"),
        ("steps", [None], "step_not_object"),
        ("if", "false", "required_job_can_skip"),
    ],
)
def test_real_job_field_failures_are_located_without_weakening_other_controls(
    field: str,
    value: object,
    code: str,
) -> None:
    """Reject unclassified scope, privilege, hidden failure and unbounded job mutations."""
    job = _job("ci.yml")
    job[field] = value
    reasons = check_job_policy(".github/workflows/ci.yml", job, aggregate=False)
    assert code in {x.code for x in reasons}


def test_job_object_and_trusted_workflow_location_are_required() -> None:
    """Return authored errors for an unavailable job object or unselected workflow name."""
    assert (
        check_job_policy(".github/workflows/ci.yml", None, aggregate=False)[0].code
        == "job_not_object"
    )
    assert check_job_policy("another.yml", {}, aggregate=False)[0].path == "workflow_policy"


def test_one_selected_matrix_preserves_evidence_and_cannot_add_environments() -> None:
    """Admit only the selected baseline row with fail-fast disabled."""
    job = _job("docs.yml")
    job["strategy"] = {"fail-fast": False, "matrix": {"python-version": ["3.13.16"]}}
    assert check_job_policy(".github/workflows/docs.yml", job, aggregate=False) == []
    job["strategy"] = {"fail-fast": False, "matrix": {"python-version": ["3.13.16", "3.14"]}}
    assert "matrix_not_selected" in {
        x.code for x in check_job_policy(".github/workflows/docs.yml", job, aggregate=False)
    }


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("if", "false", "step_can_skip_required_work"),
        ("continue-on-error", False, "step_fields_not_selected"),
        ("shell", "sh", "step_shell_not_selected"),
        ("run", "true", "step_operation_ambiguous"),
        ("uses", "actions/checkout@v7", "action_or_inputs_not_selected"),
        ("with", None, "action_or_inputs_not_selected"),
        ("env", {"OTHER": "value"}, "action_environment_not_selected"),
        ("unknown-field", 1, "step_fields_not_selected"),
    ],
)
def test_actual_step_admission_refuses_conditional_ambiguous_and_unselected_operations(
    field: str,
    value: object,
    code: str,
) -> None:
    """Exercise real checkout-step mutations through the complete job boundary."""
    job = _job("docs.yml")
    steps = job["steps"]
    assert isinstance(steps, list)
    step = steps[0]
    assert isinstance(step, dict)
    step[field] = value
    assert code in {
        x.code for x in check_job_policy(".github/workflows/docs.yml", job, aggregate=False)
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("version", "latest"),
        ("checksum", "0" * 64),
        ("python-version", "3.12.14"),
        ("python-arch", "aarch64"),
        ("cache-local-path", "/tmp/cache"),
        ("save-cache", True),
        ("enable-cache", False),
        ("download-from-astral-mirror", True),
        ("cache-dependency-glob", "*.py"),
        ("unexpected", "input"),
    ],
)
def test_uv_tool_cache_and_interpreter_selection_cannot_drift(key: str, value: object) -> None:
    """Refuse each actual setup input independently, keeping the remaining job intact."""
    job = _job("ci.yml")
    steps = job["steps"]
    assert isinstance(steps, list)
    settings = steps[2]["with"]
    settings[key] = value
    assert "action_or_inputs_not_selected" in {
        x.code for x in check_job_policy(".github/workflows/ci.yml", job, aggregate=False)
    }


def test_required_commands_actions_order_and_environments_are_not_replaceable() -> None:
    """Keep the real operation sequence and command-specific runtime fixture."""
    original = _job("ci.yml")
    job = copy.deepcopy(original)
    steps = job["steps"]
    assert isinstance(steps, list)
    steps[-1]["run"] = "true"
    codes = {x.code for x in check_job_policy(".github/workflows/ci.yml", job, aggregate=False)}
    assert {"required_surface_omitted", "operation_sequence_not_selected"} <= codes
    job = copy.deepcopy(original)
    steps = job["steps"]
    assert isinstance(steps, list)
    steps[-1]["env"] = {"SPIKE_QUALITY_GATE_REJECTION_PYTHON": "unknown"}
    assert "command_environment_not_selected" in {
        x.code for x in check_job_policy(".github/workflows/ci.yml", job, aggregate=False)
    }
    job = _job("docs.yml")
    steps = job["steps"]
    assert isinstance(steps, list)
    steps[0]["with"]["persist-credentials"] = True
    assert "action_or_inputs_not_selected" in {
        x.code for x in check_job_policy(".github/workflows/docs.yml", job, aggregate=False)
    }


def test_real_codeql_analysis_cannot_be_dropped_or_published() -> None:
    """Retain the actual init/query execution and explicit no-upload settings."""
    job = _job("codeql.yml")
    steps = job["steps"]
    assert isinstance(steps, list)
    steps[-1]["with"]["upload"] = "always"
    assert "action_or_inputs_not_selected" in {
        x.code for x in check_job_policy(".github/workflows/codeql.yml", job, aggregate=False)
    }
    steps.pop()
    assert "codeql_analysis_omitted" in {
        x.code for x in check_job_policy(".github/workflows/codeql.yml", job, aggregate=False)
    }


def test_source_matched_scorecard_entrypoint_and_no_publish_contract_are_required() -> None:
    """Preserve the actual immutable image, complete inputs and supported execution context."""
    job = _job("scorecard.yml")
    steps = job["steps"]
    assert isinstance(steps, list)
    steps[-1]["env"]["INPUT_PUBLISH_RESULTS"] = "true"
    assert "scorecard_contract_changed" in {
        x.code for x in check_job_policy(".github/workflows/scorecard.yml", job, aggregate=False)
    }
    steps.pop()
    assert "scorecard_scope_changed" in {
        x.code for x in check_job_policy(".github/workflows/scorecard.yml", job, aggregate=False)
    }


def test_actual_aggregate_refuses_missing_failed_or_hidden_required_result() -> None:
    """Require the real upstream result without constructing a fake successful producer."""
    document = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    original = document["jobs"]["gate"]
    assert check_job_policy(".github/workflows/ci.yml", original, aggregate=True) == []
    for key, value in [
        ("needs", []),
        ("if", "false"),
        ("steps", [{"run": "true"}]),
        ("env", {"CI_JOB_CLASS": "aggregate", "CI_SOURCE_SCOPE": "required-job-results"}),
    ]:
        job = copy.deepcopy(original)
        job[key] = value
        assert "aggregate_can_accept_missing_work" in {
            x.code for x in check_job_policy(".github/workflows/ci.yml", job, aggregate=True)
        }
    report = WorkflowReport(
        tuple(check_job_policy(".github/workflows/ci.yml", {"steps": []}, aggregate=False))
    )
    assert report.exit_code == 2
    assert report.as_dict()["status"] == "refused"


@pytest.mark.parametrize(
    "replacement",
    [
        "",
        "--build-constraints requirements-rejection.txt ",
        "--build-constraints /tmp/build-constraints.txt ",
    ],
)
def test_source_build_constraints_cannot_be_omitted_or_replaced(replacement: str) -> None:
    """Refuse a real bootstrap job that stops enforcing the selected build graph.

    Parameters
    ----------
    replacement : str
        Missing or alternate constraint selection in an otherwise valid job.
    """
    job = _job("ci.yml")
    steps = job["steps"]
    assert isinstance(steps, list)
    command = steps[3]["run"]
    steps[3]["run"] = command.replace("--build-constraints requirements-dev.txt ", replacement)
    assert "operation_sequence_not_selected" in {
        x.code for x in check_job_policy(".github/workflows/ci.yml", job, aggregate=False)
    }
