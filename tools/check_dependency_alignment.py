# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — development dependency alignment
"""Compare selected locks, tooling inputs and actual installed metadata read-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, TypedDict, cast

from bootstrap_native_tools import bootstrap_native_tools

PROVENANCE_SHA256 = "41bdf38a17aa806e32d0c65af9d6d6f08a06354683f4b9438ba071f13cb3c2c3"
MAX_INPUT_BYTES = 2_097_152


class _Selection(TypedDict):
    file_sha256: dict[str, str]
    installed_metadata_sha256: dict[str, str]
    console_scripts: list[str]


@dataclass(frozen=True)
class DependencyIssue:
    """Locate a dependency failure without exposing received metadata.

    Parameters
    ----------
    path : str
        Selected repository-relative input, distribution or fixed scope name.
    code : str
        Authored diagnostic identifier.
    exit_code : int
        Refusal (2), unavailable input/output (3), or invalid invocation (4).
    """

    path: str
    code: str
    exit_code: int = 2


@dataclass(frozen=True)
class DependencyReport:
    """Retain every dependency-alignment diagnostic.

    Parameters
    ----------
    reasons : tuple of DependencyIssue
        Complete deterministic diagnoses for the named alignment scope.
    """

    reasons: tuple[DependencyIssue, ...]

    @property
    def exit_code(self) -> int:
        """Return configuration, availability, refusal, then success precedence."""
        return max((issue.exit_code for issue in self.reasons), default=0)

    def as_dict(self) -> dict[str, object]:
        """Describe selected inputs and metadata, without audit or runtime claims."""
        return {
            "gate": "dependency_alignment",
            "scope": "selected_tooling_inputs_and_installed_metadata",
            "status": {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[self.exit_code],
            "reasons": [{"path": x.path, "code": x.code} for x in self.reasons],
        }


def _read(root: Path, name: str) -> bytes | DependencyIssue:
    path = root / name
    current = path
    while current != root:
        if current.is_symlink():
            return DependencyIssue(name, "input_link_refused")
        current = current.parent
    if root.is_symlink():
        return DependencyIssue(name, "input_link_refused")
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            return DependencyIssue(name, "input_not_regular")
        with path.open("rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
    except OSError:
        return DependencyIssue(name, "input_unavailable", 3)
    if len(data) > MAX_INPUT_BYTES:
        return DependencyIssue(name, "input_limit_exceeded")
    return data


def _installed(selection: _Selection) -> list[DependencyIssue]:
    reasons: list[DependencyIssue] = []
    site = Path(sysconfig.get_path("purelib"))
    expected = selection["installed_metadata_sha256"]
    directories = {Path(name).parts[0] for name in expected}
    try:
        seen = 0
        for entry in site.iterdir():
            seen += 1
            if seen > 4096:
                reasons.append(
                    DependencyIssue("installed_environment", "site_entry_limit_exceeded")
                )
                break
            if entry.name.endswith((".dist-info", ".egg-info")):
                if entry.name not in directories:
                    reasons.append(
                        DependencyIssue("installed_environment", "unselected_distribution")
                    )
    except OSError:
        reasons.append(DependencyIssue("installed_environment", "site_unavailable", 3))
    for name, digest in expected.items():
        data = _read(site, name)
        if isinstance(data, DependencyIssue):
            reasons.append(data)
        elif hashlib.sha256(data).hexdigest() != digest:
            reasons.append(DependencyIssue(name, "installed_metadata_not_selected"))
    for name in selection["console_scripts"]:
        path = Path(sys.prefix) / "bin" / name
        if not path.is_file() or not os.access(path, os.X_OK):
            reasons.append(DependencyIssue(name, "selected_console_script_unavailable", 3))
    return reasons


def validate_dependency_alignment(root: Path) -> DependencyReport:
    """Check source-selected tooling inputs and this interpreter's installed graph.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected checkout. Every file is read-only and bounded to two
        MiB. No input field can select policy, a command or a metadata location.

    Returns
    -------
    DependencyReport
        Exact selected-file and installed-METADATA alignment with all diagnoses.

    Notes
    -----
    The receipt is selected by a digest compiled into maintained source before
    it is decoded. Its complete 103-package graph, active version constraints,
    extras closure, licences and source-artifact lock membership were checked
    when selecting the source. Runtime compares every original METADATA byte.
    It also requires the selected interpreter and executable console
    files, and verifies the separately selected native-tool files. It never
    imports installed packages, invokes tools, audits vulnerabilities, verifies
    all installed payload files, or qualifies hosted workflows/domain results.
    """
    try:
        if b"\0" in os.fsencode(root):
            raise ValueError("invalid repository root")
    except ValueError:
        return DependencyReport((DependencyIssue("invocation", "invalid_repository_root", 4),))
    root = Path(os.path.abspath(root))
    reasons: list[DependencyIssue] = []
    if sys.version_info != (3, 13, 16, "final", 0):
        reasons.append(DependencyIssue("tooling_python", "interpreter_not_selected", 3))
    if sys.prefix == sys.base_prefix:
        reasons.append(DependencyIssue("installed_environment", "virtual_environment_required", 3))
    receipt = _read(root, "dependency-provenance.json")
    if isinstance(receipt, DependencyIssue):
        return DependencyReport(tuple([*reasons, receipt]))
    if hashlib.sha256(receipt).hexdigest() != PROVENANCE_SHA256:
        return DependencyReport(
            tuple([*reasons, DependencyIssue("dependency-provenance.json", "receipt_not_selected")])
        )
    # The digest selects the reviewed complete document before this typed projection.
    selection = cast(_Selection, json.loads(receipt)["selection"])
    for name, digest in selection["file_sha256"].items():
        data = _read(root, name)
        if isinstance(data, DependencyIssue):
            reasons.append(data)
        elif hashlib.sha256(data).hexdigest() != digest:
            reasons.append(DependencyIssue(name, "tooling_input_not_selected"))
    reasons.extend(_installed(selection))
    native = bootstrap_native_tools(root)
    reasons.extend(DependencyIssue(x.path, x.code, x.exit_code) for x in native.reasons)
    return DependencyReport(tuple(sorted(reasons, key=lambda x: (x.path, x.code, x.exit_code))))


class _Arguments(argparse.Namespace):
    root: str
    json: bool


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    """Run the dependency CLI with fixed diagnostics and read-only inputs.

    Parameters
    ----------
    argv : list of str or None
        Explicit arguments, or process arguments when None.
    stdout : text stream or None
        Report destination, defaulting to process standard output.

    Returns
    -------
    int
        Zero for this named check, 2 for refusal, 3 for unavailable input or
        output, and 4 for invalid invocation. Help is informational only.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument("--root", default=".", help="Read-only checkout root.")
    parser.add_argument("--json", action="store_true", help="Emit a JSON report.")
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        report = DependencyReport((DependencyIssue("invocation", "invalid_arguments", 4),))
        json_output = True
    else:
        json_output = args.json
        report = (
            DependencyReport((DependencyIssue("invocation", "unknown_arguments", 4),))
            if unknown
            else validate_dependency_alignment(Path(args.root))
        )
    document = report.as_dict()
    text = (
        json.dumps(document, sort_keys=True, indent=2) + "\n"
        if json_output
        else "dependency_alignment: "
        + str(document["status"])
        + "\n"
        + "".join(f"{issue.path}: {issue.code}\n" for issue in report.reasons)
    )
    destination = sys.stdout if stdout is None else stdout
    try:
        destination.write(text)
        destination.flush()
    except (OSError, ValueError):
        return max(3, report.exit_code)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
