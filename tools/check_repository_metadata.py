# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — local repository metadata validation
"""Validate the source-selected local descriptor without granting domain acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, TextIO

REPOSITORY_NAME = "SPIKE-QUALITY-GATE"
#: The Tier-0 lifecycle phase: the repository is published at its canonical public remote.
LIFECYCLE = "public_repository"
#: The canonical public remote: the lower-case repository name under the owner account.
PUBLIC_REMOTE = "https://github.com/anulum/spike-quality-gate"
PROFILE_SHA256 = "f453a70eae008c41f8d26a1f495ec3636f64739bcedb9caac0bdf8774300905c"
STANDARD_SHA256 = "8421674a61444474447fad2f4d2bfc54dc5a1ea12ae988785e57dbcab385938c"
LOCK_SHA256 = "a4d78e0883168db6e4dbfe868e1b407da23f824ffa3c79add8910ff4396ae306"
MAX_INPUT_BYTES = 1_048_576


@dataclass(frozen=True)
class Issue:
    """Locate a controlled diagnostic without echoing supplied metadata.

    Parameters
    ----------
    path : str
        Fixed repository-relative input name.
    code : str
        Authored diagnostic identifier.
    exit_code : int
        Refusal (2), unavailable input (3), or invalid configuration (4).
    """

    path: str
    code: str
    exit_code: int


@dataclass(frozen=True)
class Report:
    """Describe only the complete named repository-metadata check.

    Parameters
    ----------
    reasons : tuple of Issue
        Every located diagnostic, retained in deterministic input order.
    """

    reasons: tuple[Issue, ...]

    @property
    def exit_code(self) -> int:
        """Return configuration, availability, refusal, then success precedence."""
        return max((issue.exit_code for issue in self.reasons), default=0)

    def as_dict(self) -> dict[str, object]:
        """Return the diagnostic report, with no scientific acceptance field.

        Returns
        -------
        dict
            Gate, scope, status and controlled located reasons.
        """
        status = {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[self.exit_code]
        return {
            "gate": "repository_metadata",
            "scope": "local_scaffold",
            "status": status,
            "reasons": [{"path": issue.path, "code": issue.code} for issue in self.reasons],
        }


def repository_schema() -> dict[str, object]:
    """Construct the selected closed local-governance schema.

    Returns
    -------
    dict
        Source-selected identity, empty claims, planned names and toolchain tuple.

    Notes
    -----
    This is a local repository descriptor, not a registered evidence schema.
    The returned object is fresh and cannot mutate a trusted global schema.
    """
    empty: dict[str, object] = {"type": "array", "maxItems": 0}
    profile = {
        "id": {"const": "gotm.enterprise-repository-tier0.local-scaffold"},
        "revision": {"const": "2026-10-04"},
        "profile_sha256": {"const": PROFILE_SHA256},
        "standard_sha256": {"const": STANDARD_SHA256},
    }
    python = {
        "actual_version": {"const": "3.13.16"},
        "design_baseline": {"const": "3.13"},
        "supported_range": {"const": ">=3.13.16,<3.14"},
        "development_lock_sha256": {"const": LOCK_SHA256},
    }
    properties = {
        "repository_name": {"const": REPOSITORY_NAME},
        "owner_group": {"const": "SC-NEUROMORPHIC-COMPUTING-SYSTEMS"},
        "lifecycle": {"const": LIFECYCLE},
        "public_remote": {"const": PUBLIC_REMOTE},
        "evidence_maturity": {"const": "architecture_only"},
        "capabilities": empty,
        "claims": empty,
        "qualified_owned_schema_ids": empty,
        "domain_runtime_dependencies": empty,
        "planned_owned_schema_ids": {
            "const": [
                "event_data_quality.report.v1",
            ]
        },
        "validation_profile": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(profile),
            "properties": profile,
        },
        "tooling_python": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(python),
            "properties": python,
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Spike Quality Gate local repository metadata",
        "type": "object",
        "additionalProperties": False,
        "required": sorted(properties),
        "properties": properties,
    }


def _selected_metadata() -> dict[str, object]:
    """Construct the single source-selected descriptor without a runtime schema plugin."""
    return {
        "repository_name": REPOSITORY_NAME,
        "owner_group": "SC-NEUROMORPHIC-COMPUTING-SYSTEMS",
        "lifecycle": LIFECYCLE,
        "public_remote": PUBLIC_REMOTE,
        "evidence_maturity": "architecture_only",
        "capabilities": [],
        "claims": [],
        "qualified_owned_schema_ids": [],
        "domain_runtime_dependencies": [],
        "planned_owned_schema_ids": [
            "event_data_quality.report.v1",
        ],
        "validation_profile": {
            "id": "gotm.enterprise-repository-tier0.local-scaffold",
            "revision": "2026-10-04",
            "profile_sha256": PROFILE_SHA256,
            "standard_sha256": STANDARD_SHA256,
        },
        "tooling_python": {
            "actual_version": "3.13.16",
            "design_baseline": "3.13",
            "supported_range": ">=3.13.16,<3.14",
            "development_lock_sha256": LOCK_SHA256,
        },
    }


def _schema_bytes() -> bytes:
    return (json.dumps(repository_schema(), sort_keys=True, indent=2) + "\n").encode("utf-8")


def _read(root: Path, relative: str, invalid_exit: int) -> bytes | Issue:
    try:
        with (root / relative).open("rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
    except OSError:
        return Issue(relative, "required_input_unavailable", 3)
    if len(data) > MAX_INPUT_BYTES:
        return Issue(relative, "input_limit_exceeded", invalid_exit)
    return data


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate member")
        result[key] = value
    return result


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError("nonfinite JSON constant")


def validate_repository_metadata(root: Path) -> Report:
    """Validate all selected inputs independently of a generated inventory.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected repository containing the three fixed input paths.

    Returns
    -------
    Report
        Complete metadata-only outcome with all input diagnostics preserved.

    Notes
    -----
    Inputs are read-only and bounded to one MiB each. Neither input fields nor
    an on-disk schema can select a different validator or policy. This check
    checks the executing interpreter version, without qualifying the complete
    installed package graph or domain behaviour.
    Invalid UTF-8 or NUL-containing root names return an invocation diagnosis.
    """
    try:
        str(root).encode("utf-8")
        if "\0" in str(root):
            raise ValueError("invalid root")
    except ValueError:
        return Report((Issue("invocation", "invalid_root", 4),))
    reasons: list[Issue] = []
    if sys.version_info != (3, 13, 16, "final", 0):
        reasons.append(Issue("tooling_python", "interpreter_not_selected", 3))
    schema = _read(root, "schemas/repository-domain.schema.json", 4)
    if isinstance(schema, Issue):
        reasons.append(schema)
    elif schema != _schema_bytes():
        reasons.append(Issue("schemas/repository-domain.schema.json", "schema_not_selected", 4))
    descriptor = _read(root, "repository-domain.json", 2)
    if isinstance(descriptor, Issue):
        reasons.append(descriptor)
    else:
        try:
            value: object = json.loads(
                descriptor.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (UnicodeError, ValueError, RecursionError):
            reasons.append(Issue("repository-domain.json", "invalid_metadata_json", 2))
        else:
            if value != _selected_metadata():
                reasons.append(Issue("repository-domain.json", "metadata_not_selected", 2))
    lock = _read(root, "requirements-dev.txt", 2)
    if isinstance(lock, Issue):
        reasons.append(lock)
    elif hashlib.sha256(lock).hexdigest() != LOCK_SHA256:
        reasons.append(Issue("requirements-dev.txt", "development_lock_changed", 2))
    return Report(tuple(reasons))


class _Arguments(argparse.Namespace):
    root: str
    json: bool


def main(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    """Run the public metadata command with deterministic safe diagnostics.

    Parameters
    ----------
    argv : list of str or None, optional
        Explicit command arguments, or the current process arguments.
    output : text stream or None, optional
        Report destination, defaulting to standard output.

    Returns
    -------
    int
        Zero for this metadata gate only, 2 for refusal, 3 for unavailable
        inputs or output, and 4 for invalid invocation or configuration.
        Help is a separate informational operation and exits zero.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument("--root", default=".", help="Repository root; inputs are never modified.")
    parser.add_argument("--json", action="store_true", help="Emit the diagnostic JSON report.")
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        report = Report((Issue("invocation", "invalid_arguments", 4),))
        json_output = True
    else:
        json_output = args.json
        report = (
            Report((Issue("invocation", "unknown_arguments", 4),))
            if unknown
            else validate_repository_metadata(Path(args.root))
        )
    document = report.as_dict()
    text = (
        json.dumps(document, sort_keys=True, indent=2) + "\n"
        if json_output
        else "repository_metadata: "
        + str(document["status"])
        + "\n"
        + "".join(f"{issue.path}: {issue.code}\n" for issue in report.reasons)
    )
    destination = sys.stdout if output is None else output
    try:
        destination.write(text)
        destination.flush()
    except (OSError, ValueError):
        return max(3, report.exit_code)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
