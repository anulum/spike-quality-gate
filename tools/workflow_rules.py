# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — workflow job and action rules
"""Selected job roles, action contracts and controlled workflow reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROVENANCE_SHA256 = "d1c35ce4c0a19d47703b31475f021d9d9054a1a5c273b8c58a9a0d667df6070b"
ROLES = {
    "ci.yml": "correctness",
    "pre-commit.yml": "hook-parity",
    "docs.yml": "documentation",
    "security-audit.yml": "audit",
    "codeql.yml": "analysis",
    "sbom.yml": "inventory",
    "scorecard.yml": "analysis",
}
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_UV = "astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884"
CODEQL_INIT = "github/codeql-action/init@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee"
CODEQL_ANALYZE = "github/codeql-action/analyze@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee"
SCORECARD = (
    "docker://ghcr.io/ossf/scorecard-action@sha256:"
    "1e1481c65fc2407d3fd6ab18a23c741eb4d1c0d9359ebafc4b3ab13aa61d8627"
)
UV_CHECKSUM = "2b428396f12572d4429cf210ca234dd599a33b3af0958a4d5ed569d63e3f344f"
MAX_BYTES = 262_144


BASE_OPERATIONS: list[tuple[str, str]] = [
    ("uses", "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"),
    (
        "run",
        "mkdir -p .tool-cache/tmp .tool-cache/uv-cache .tool-cache/pre-commit .tool-cache/reports",
    ),
    ("uses", "astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884"),
    (
        "run",
        "uv venv --python 3.13.16 .venv\nuv pip sync --require-hashes --build-constraints requirements-dev.txt --python .venv/bin/python requirements-dev.txt",
    ),
]

APPROVED_OPERATIONS: dict[str, list[tuple[str, str]]] = {
    "ci.yml": [
        *BASE_OPERATIONS,
        (
            "run",
            "uv venv --python 3.12.14 .tool-cache/python-rejection\nuv pip sync --require-hashes --python .tool-cache/python-rejection/bin/python requirements-rejection.txt",
        ),
        ("run", "make native-tools"),
        ("run", "make ci"),
    ],
    "codeql.yml": [
        *BASE_OPERATIONS,
        (
            "run",
            "mkdir -p .tool-cache/codeql\ncurl --fail --location --proto '=https' --tlsv1.2 --max-time 300 --output .tool-cache/codeql/bundle.tar.gz https://github.com/github/codeql-action/releases/download/codeql-bundle-v2.27.2/codeql-bundle-linux64.tar.gz\nsha256sum --check --strict <<'CHECKSUM'\nf002864be6dd8d5d7bdb123aaf7291ec8e291012bd9f70b6d2362f730db52aeb  .tool-cache/codeql/bundle.tar.gz\nCHECKSUM\ntest \"$(wc -c < .tool-cache/codeql/bundle.tar.gz)\" -eq 692996129",
        ),
        ("uses", "github/codeql-action/init@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee"),
        ("uses", "github/codeql-action/analyze@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee"),
    ],
    "docs.yml": [*BASE_OPERATIONS, ("run", "make docs")],
    "pre-commit.yml": [*BASE_OPERATIONS, ("run", "make native-tools"), ("run", "make hook-check")],
    "sbom.yml": [*BASE_OPERATIONS, ("run", "make native-tools"), ("run", "make sbom")],
    "scorecard.yml": [
        ("uses", "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"),
        (
            "uses",
            "docker://ghcr.io/ossf/scorecard-action@sha256:1e1481c65fc2407d3fd6ab18a23c741eb4d1c0d9359ebafc4b3ab13aa61d8627",
        ),
    ],
    "security-audit.yml": [
        *BASE_OPERATIONS,
        ("run", "make native-tools"),
        ("run", "make source-audit"),
    ],
}


@dataclass(frozen=True)
class WorkflowIssue:
    """Locate a controlled workflow-policy diagnostic.

    Parameters
    ----------
    path : str
        Fixed repository-relative input name.
    code : str
        Authored diagnostic identifier.
    exit_code : int
        Refusal (2), unavailable input (3), or invalid invocation (4).
    """

    path: str
    code: str
    exit_code: int = 2


@dataclass(frozen=True)
class WorkflowReport:
    """Retain all structural and selected-source workflow diagnoses.

    Parameters
    ----------
    reasons : tuple of WorkflowIssue
        Every observed diagnosis, without received content or absolute paths.
    """

    reasons: tuple[WorkflowIssue, ...]

    @property
    def exit_code(self) -> int:
        """Return configuration, unavailable input, refusal, then success precedence."""
        return max((x.exit_code for x in self.reasons), default=0)

    def as_dict(self) -> dict[str, object]:
        """Return the named workflow-policy report without an execution verdict."""
        return {
            "gate": "workflow_policy",
            "scope": "local_scaffold",
            "status": {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[self.exit_code],
            "reasons": [{"path": x.path, "code": x.code} for x in self.reasons],
        }


def _action_valid(action: str, inputs: object) -> bool:
    if not isinstance(inputs, dict):
        return False
    if action == CHECKOUT:
        return inputs == {"persist-credentials": False, "fetch-depth": 0}
    if action == SETUP_UV:
        return (
            inputs.get("version") == "0.13.4"
            and inputs.get("python-version") == "3.13.16"
            and inputs.get("checksum") == UV_CHECKSUM
            and inputs.get("python-arch") == "x86_64"
            and inputs.get("cache-local-path") == ".tool-cache/uv-cache"
            and inputs.get("save-cache") is False
            and inputs.get("download-from-astral-mirror") is False
            and inputs.get("cache-dependency-glob")
            == "requirements-dev.txt\nrequirements-rejection.txt\npyproject.toml"
            and set(inputs)
            == {
                "version",
                "checksum",
                "python-version",
                "python-arch",
                "enable-cache",
                "cache-local-path",
                "cache-dependency-glob",
                "download-from-astral-mirror",
                "save-cache",
            }
            and inputs.get("enable-cache") is True
        )
    if action == CODEQL_INIT:
        return inputs == {
            "languages": "python",
            "build-mode": "none",
            "tools": ".tool-cache/codeql/bundle.tar.gz",
            "config": "paths:\n  - tools\n  - tests",
            "ram": 4096,
            "threads": 2,
        }
    if action == CODEQL_ANALYZE:
        return inputs == {
            "upload": "never",
            "upload-database": False,
            "output": ".tool-cache/reports/codeql",
            "skip-queries": False,
            "ram": 4096,
            "threads": 2,
        }
    return False


def check_job_policy(name: str, job: object, *, aggregate: bool) -> list[WorkflowIssue]:
    """Inspect one complete job against its selected role and bounded operations.

    Parameters
    ----------
    name : str
        Trusted repository-relative required workflow name.
    job : object
        Received YAML job object.
    aggregate : bool
        Whether this is the required correctness-result aggregate.

    Returns
    -------
    list of WorkflowIssue
        Every observed job/step/source-policy violation.
    """
    if name not in {".github/workflows/" + filename for filename in ROLES}:
        return [WorkflowIssue("workflow_policy", "workflow_name_not_selected")]
    reasons: list[WorkflowIssue] = []
    if not isinstance(job, dict):
        return [WorkflowIssue(name, "job_not_object")]
    allowed_job_keys = {
        "name",
        "runs-on",
        "timeout-minutes",
        "env",
        "steps",
        "permissions",
        "continue-on-error",
        "strategy",
        "if",
        "needs",
    }
    if set(job) - allowed_job_keys:
        reasons.append(WorkflowIssue(name, "job_fields_not_selected"))
    env = job.get("env")
    expected_env_keys = {"CI_JOB_CLASS", "CI_SOURCE_SCOPE"}
    if aggregate:
        expected_env_keys.add("VALIDATION_RESULT")
    if not isinstance(env, dict) or set(env) != expected_env_keys:
        reasons.append(WorkflowIssue(name, "job_environment_not_selected"))
    role = "aggregate" if aggregate else ROLES[Path(name).name]
    if (
        not isinstance(env, dict)
        or env.get("CI_JOB_CLASS") != role
        or env.get("CI_SOURCE_SCOPE")
        != ("required-job-results" if aggregate else "maintained-python-and-repository")
    ):
        reasons.append(WorkflowIssue(name, "job_scope_unclassified"))
    timeout = job.get("timeout-minutes")
    if type(timeout) is not int or not 1 <= timeout <= 30:
        reasons.append(WorkflowIssue(name, "job_timeout_unbounded"))
    if job.get("runs-on") != "ubuntu-24.04":
        reasons.append(WorkflowIssue(name, "runner_not_selected"))
    if "permissions" in job and job["permissions"] != {"contents": "read"}:
        reasons.append(WorkflowIssue(name, "job_permissions_not_read_only"))
    if job.get("continue-on-error", False) is not False:
        reasons.append(WorkflowIssue(name, "job_failure_hidden"))
    if "strategy" in job:
        strategy = job["strategy"]
        if not isinstance(strategy, dict) or strategy.get("fail-fast") is not False:
            reasons.append(WorkflowIssue(name, "matrix_cancels_evidence"))
        if strategy != {"fail-fast": False, "matrix": {"python-version": ["3.13.16"]}}:
            reasons.append(WorkflowIssue(name, "matrix_not_selected"))
    steps = job.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > 20:
        return [*reasons, WorkflowIssue(name, "steps_not_selected")]
    actions: list[str] = []
    operations: list[tuple[str, str]] = []
    runs: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            reasons.append(WorkflowIssue(name, "step_not_object"))
            continue
        if set(step) - {"name", "id", "uses", "with", "run", "env", "shell"}:
            reasons.append(WorkflowIssue(name, "step_fields_not_selected"))
        if "shell" in step and step["shell"] != "bash":
            reasons.append(WorkflowIssue(name, "step_shell_not_selected"))
        if any(key in step for key in ("if", "continue-on-error")):
            reasons.append(WorkflowIssue(name, "step_can_skip_required_work"))
        action = step.get("uses")
        command = step.get("run")
        if isinstance(action, str) and command is None:
            actions.append(action)
            operations.append(("uses", action))
            if action == SCORECARD:
                expected = {
                    "INPUT_RESULTS_FILE": "scorecard-results.json",
                    "INPUT_RESULTS_FORMAT": "json",
                    "INPUT_REPO_TOKEN": "$" + "{{ github.token }}",
                    "INPUT_INTERNAL_DEFAULT_TOKEN": "$" + "{{ github.token }}",
                    "INPUT_PUBLISH_RESULTS": "false",
                    "INPUT_FILE_MODE": "archive",
                    "INPUT_INTERNAL_PUBLISH_BASE_URL": "https://api.scorecard.dev",
                }
                if (
                    step.get("env") != expected
                    or Path(name).name != "scorecard.yml"
                    or "with" in step
                ):
                    reasons.append(WorkflowIssue(name, "scorecard_contract_changed"))
            elif "env" in step:
                reasons.append(WorkflowIssue(name, "action_environment_not_selected"))
            elif not _action_valid(action, step.get("with")):
                reasons.append(WorkflowIssue(name, "action_or_inputs_not_selected"))
        elif isinstance(command, str) and action is None:
            runs.append(command)
            operations.append(("run", command))
            expected_run_env = (
                {
                    "SPIKE_QUALITY_GATE_REJECTION_PYTHON": "$"
                    + "{{ github.workspace }}/.tool-cache/python-rejection/bin/python"
                }
                if command == "make ci"
                else None
            )
            if step.get("env") != expected_run_env or "with" in step:
                reasons.append(WorkflowIssue(name, "command_environment_not_selected"))
        else:
            reasons.append(WorkflowIssue(name, "step_operation_ambiguous"))
    if aggregate:
        if (
            job.get("needs") != ["validation"]
            or job.get("if") != "$" + "{{ always() }}"
            or runs != ['test "$VALIDATION_RESULT" = success']
            or actions
            or not isinstance(env, dict)
            or env.get("VALIDATION_RESULT") != "$" + "{{ needs.validation.result }}"
        ):
            reasons.append(WorkflowIssue(name, "aggregate_can_accept_missing_work"))
    else:
        if operations != APPROVED_OPERATIONS[Path(name).name]:
            reasons.append(WorkflowIssue(name, "operation_sequence_not_selected"))
        required = {
            "ci.yml": {"make ci", "make native-tools"},
            "pre-commit.yml": {"make hook-check", "make native-tools"},
            "docs.yml": {"make docs"},
            "security-audit.yml": {"make source-audit", "make native-tools"},
            "sbom.yml": {"make sbom", "make native-tools"},
            "codeql.yml": set(),
            "scorecard.yml": set(),
        }[Path(name).name]
        if CHECKOUT not in actions or not required.issubset(runs):
            reasons.append(WorkflowIssue(name, "required_surface_omitted"))
        if Path(name).name == "codeql.yml" and (
            CODEQL_INIT not in actions or CODEQL_ANALYZE not in actions
        ):
            reasons.append(WorkflowIssue(name, "codeql_analysis_omitted"))
        if Path(name).name == "scorecard.yml":
            expected_if = (
                "$"
                + "{{ github.event_name == 'pull_request' || github.ref == format('refs/heads/{0}', github.event.repository.default_branch) }}"
            )
            if SCORECARD not in actions or job.get("if") != expected_if:
                reasons.append(WorkflowIssue(name, "scorecard_scope_changed"))
        elif "if" in job:
            reasons.append(WorkflowIssue(name, "required_job_can_skip"))
    return reasons
