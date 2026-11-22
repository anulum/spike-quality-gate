# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — repository inventory
"""Generate an empty initial inventory or independently inspect its actual source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import NoReturn, TextIO

from check_repository_metadata import LIFECYCLE, REPOSITORY_NAME, validate_repository_metadata
from repository_git import inspect_repository_git
from repository_policy import InventoryIssue, InventoryReport, admit_root, read_inventory_input
from repository_tree import inspect_repository_tree


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate member")
        result[key] = value
    return result


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError("nonfinite constant")


def _create_output(output: Path, data: bytes) -> tuple[InventoryIssue, ...]:
    try:
        str(output).encode("utf-8")
        if "\0" in str(output):
            raise ValueError("invalid output")
        output = Path(os.path.abspath(output))
        if any(p.is_symlink() for p in (output.parent, *output.parent.parents)):
            return (InventoryIssue("output", "output_parent_link_refused"),)
    except (UnicodeError, ValueError):
        return (InventoryIssue("invocation", "invalid_output", 4),)
    try:
        with tempfile.TemporaryDirectory(prefix=".inventory-", dir=output.parent) as temporary:
            staged = Path(temporary) / "inventory.json"
            with staged.open("xb") as stream:
                stream.write(data)
                stream.flush()
            os.link(staged, output)
    except FileExistsError:
        return (InventoryIssue("output", "exclusive_output_exists"),)
    except OSError:
        return (InventoryIssue("output", "output_unavailable", 3),)
    return ()


def inventory_operation(
    root: Path, *, mode: str = "verify", output: Path | None = None
) -> InventoryReport:
    """Generate from validated source or verify the complete initial tree and index.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected repository containing the selected metadata inputs.
    mode : str
        Generate or verify, with verification as the read-only default.
    output : pathlib.Path or None
        Required exclusive new file for generation; forbidden for verification.

    Returns
    -------
    InventoryReport
        Scoped diagnostics with 4>3>2>0 precedence.

    Notes
    -----
    Generation requires neither a prior inventory nor a complete required tree.
    Its atomic exclusive publication uses a same-directory staged file and hard
    link; it never overwrites a file, directory or link. It is not a durability,
    concurrent-source-snapshot or power-failure guarantee. The attribution sidecar
    is authored separately. Verification never modifies repository inputs and
    checks source-selected policy independently of received inventory fields.
    """
    if mode not in {"generate", "verify"} or (mode == "generate") != (output is not None):
        return InventoryReport((InventoryIssue("invocation", "invalid_operation", 4),), mode)
    admitted = admit_root(root)
    if isinstance(admitted, InventoryIssue):
        return InventoryReport((admitted,), mode)
    root = admitted
    reasons: list[InventoryIssue] = []
    # The metadata reader has a narrower scope and must never follow linked inputs here.
    inputs: dict[str, bytes] = {}
    for name in (
        "schemas/repository-domain.schema.json",
        "repository-domain.json",
        "requirements-dev.txt",
    ):
        data = read_inventory_input(root, name)
        if isinstance(data, InventoryIssue):
            reasons.append(data)
        else:
            inputs[name] = data
    if reasons:
        return InventoryReport(tuple(reasons), mode)
    metadata = validate_repository_metadata(root)
    reasons.extend(InventoryIssue(x.path, x.code, x.exit_code) for x in metadata.reasons)
    if reasons:
        return InventoryReport(tuple(reasons), mode)
    raw = inputs["repository-domain.json"]
    expected: dict[str, object] = {
        "repository_name": REPOSITORY_NAME,
        "lifecycle": LIFECYCLE,
        "evidence_maturity": "architecture_only",
        "capabilities": [],
        "claims": [],
        "qualified_owned_schema_ids": [],
        "source_metadata": {
            "path": "repository-domain.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
    }
    if mode == "generate" and output is not None:
        encoded = (json.dumps(expected, sort_keys=True, indent=2) + "\n").encode("utf-8")
        return InventoryReport(_create_output(output, encoded), mode)
    inventory = read_inventory_input(root, "capability-inventory.json")
    if isinstance(inventory, InventoryIssue):
        reasons.append(inventory)
    else:
        try:
            value: object = json.loads(
                inventory.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            json.dumps(value, ensure_ascii=False).encode("utf-8")
        except (ValueError, UnicodeError, RecursionError):
            reasons.append(InventoryIssue("capability-inventory.json", "invalid_inventory_json"))
        else:
            if value != expected:
                reasons.append(
                    InventoryIssue("capability-inventory.json", "inventory_not_selected")
                )
    reasons.extend(inspect_repository_tree(root))
    reasons.extend(inspect_repository_git(root))
    return InventoryReport(tuple(reasons), mode)


class _Arguments(argparse.Namespace):
    root: str
    mode: str
    output: str | None
    json: bool


def main(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    """Run the inventory command with caller-safe diagnostics.

    Parameters
    ----------
    argv : list of str or None
        Explicit arguments or the process argument vector.
    output : text stream or None
        Report destination; standard output by default.

    Returns
    -------
    int
        Zero only for the named operation, refusal 2, unavailable 3, invalid 4.
        Help is informational and exits zero without validation.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument("--root", default=".")
    parser.add_argument("--mode", choices=("generate", "verify"), default="verify")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        report = InventoryReport((InventoryIssue("invocation", "invalid_arguments", 4),), "verify")
        json_output = True
    else:
        json_output = args.json
        report = (
            InventoryReport((InventoryIssue("invocation", "unknown_arguments", 4),), args.mode)
            if unknown
            else inventory_operation(
                Path(args.root),
                mode=args.mode,
                output=None if args.output is None else Path(args.output),
            )
        )
    document = report.as_dict()
    text = (
        json.dumps(document, sort_keys=True, indent=2) + "\n"
        if json_output
        else "repository_inventory: "
        + str(document["status"])
        + "\n"
        + "".join(f"{x.path}: {x.code}\n" for x in report.reasons)
    )
    try:
        destination = sys.stdout if output is None else output
        destination.write(text)
        destination.flush()
    except (OSError, ValueError):
        return max(3, report.exit_code)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
