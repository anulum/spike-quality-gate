# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real inventory behaviour
"""Exercise bounded real file admission and inventory result semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from repository_policy import (
    MAX_FILE_BYTES,
    InventoryIssue,
    InventoryReport,
    admit_root,
    read_inventory_input,
)

ROOT = Path(__file__).resolve().parents[1]


def test_actual_regular_source_and_admitted_relative_root() -> None:
    """Read actual descriptor bytes after lexical root admission."""
    root = admit_root(ROOT)
    assert root == ROOT
    assert (
        read_inventory_input(ROOT, "repository-domain.json")
        == (ROOT / "repository-domain.json").read_bytes()
    )
    assert admit_root(Path(".")) == Path.cwd()


@pytest.mark.parametrize("name", ["invalid\0root", "\ud800"])
def test_invalid_root_names_have_fixed_diagnostics(name: str) -> None:
    """Refuse unsupported caller root names before filesystem access."""
    assert admit_root(Path(name)) == InventoryIssue("invocation", "invalid_root", 4)


def test_linked_root_and_parent_are_refused(tmp_path: Path) -> None:
    """Refuse a real link both directly and as a parent."""
    (tmp_path / "actual").mkdir()
    link = tmp_path / "linked"
    link.symlink_to(tmp_path / "actual", target_is_directory=True)
    for root in (link, link / "child"):
        assert admit_root(root) == InventoryIssue("repository_root", "root_link_refused")


def test_real_file_kinds_limits_availability_and_parent_links(tmp_path: Path) -> None:
    """Reject actual missing, directory, link, oversized and unreadable inputs."""
    name = "input.json"
    path = tmp_path / name
    assert read_inventory_input(tmp_path, name) == InventoryIssue(name, "input_unavailable", 3)
    path.mkdir()
    assert read_inventory_input(tmp_path, name) == InventoryIssue(name, "input_not_regular")
    path.rmdir()
    path.symlink_to(ROOT / "repository-domain.json")
    assert read_inventory_input(tmp_path, name) == InventoryIssue(name, "input_link_refused")
    path.unlink()
    path.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    assert read_inventory_input(tmp_path, name) == InventoryIssue(name, "input_limit_exceeded")
    path.write_bytes(b"{}")
    path.chmod(0)
    try:
        assert read_inventory_input(tmp_path, name) == InventoryIssue(name, "input_unavailable", 3)
    finally:
        path.chmod(0o600)
    (tmp_path / "parent").symlink_to(ROOT / "schemas", target_is_directory=True)
    assert read_inventory_input(tmp_path, "parent/repository-domain.schema.json") == InventoryIssue(
        "parent/repository-domain.schema.json", "input_link_refused"
    )


def test_report_scopes_precedence_and_fresh_projection() -> None:
    """Keep generation distinct from verification and all failure precedence."""
    generate = InventoryReport((), "generate")
    assert generate.exit_code == 0
    assert generate.as_dict()["scope"] == "validated_metadata_generation"
    for code, status in [(2, "refused"), (3, "unavailable"), (4, "invalid")]:
        report = InventoryReport(
            tuple(InventoryIssue("input", "refused", x) for x in range(2, code + 1)), "verify"
        )
        assert report.exit_code == code
        assert report.as_dict()["status"] == status
        assert report.as_dict()["scope"] == "initial_repository_tree_and_index"
        assert len(report.reasons) == code - 1


def test_selected_actual_configuration_and_unavailable_drift_refuse(tmp_path: Path) -> None:
    """Validate original configuration and refuse changes without running received rules."""
    from repository_policy import inspect_repository_configuration

    for name in [".gitignore", ".gitattributes", ".github/dependabot.yml"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    assert inspect_repository_configuration(tmp_path) == ()
    (tmp_path / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes() + b"\n")
    (tmp_path / ".gitattributes").unlink()
    reasons = inspect_repository_configuration(tmp_path)
    assert {(x.path, x.code) for x in reasons} == {
        (".gitignore", "configuration_not_selected"),
        (".gitattributes", "input_unavailable"),
    }
    assert inspect_repository_configuration(Path("bad\0root"))[0].exit_code == 4
