# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — documentation configuration contract tests
"""Exercise source-selected configuration through its real public API."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from documentation_policy import validate_documentation_configuration

SOURCE = Path(__file__).resolve().parents[1]
INPUTS = ("mkdocs.yml", "CITATION.cff", ".zenodo.json", "tools/documentation_hooks.py")


@pytest.fixture
def configuration(tmp_path: Path) -> Path:
    """Supply only actual selected configuration, without rendered artifacts."""
    root = tmp_path / "configuration"
    root.mkdir()
    for name in INPUTS:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, root / name)
    return root


def test_configuration_success_never_attests_a_build_or_html(configuration: Path) -> None:
    """Verify the distinct configuration scope and complete read-only behaviour."""
    before = {name: (configuration / name).read_bytes() for name in INPUTS}
    actual = validate_documentation_configuration(configuration)
    assert actual.exit_code == 0
    assert actual.as_dict() == {
        "gate": "documentation",
        "scope": "selected_documentation_configuration",
        "builder_execution_attested": False,
        "status": "pass",
        "reasons": [],
    }
    assert not (configuration / ".tool-cache").exists()
    assert all((configuration / name).read_bytes() == data for name, data in before.items())


@pytest.mark.parametrize("name", INPUTS)
def test_changed_renderer_or_publication_bytes_refuse(configuration: Path, name: str) -> None:
    """Refuse alternate plugins, publication dates, release versions or DOI declarations."""
    path = configuration / name
    path.write_bytes(path.read_bytes() + b"\n")
    actual = validate_documentation_configuration(configuration)
    assert actual.exit_code == 2
    assert [(x.path, x.code) for x in actual.reasons] == [
        (name, "documentation_configuration_not_selected")
    ]


@pytest.mark.parametrize(
    "mutation,expected",
    [("missing", 3), ("directory", 2), ("linked", 2), ("oversized", 2)],
)
def test_config_files_have_real_type_availability_and_size_limits(
    configuration: Path, mutation: str, expected: int
) -> None:
    """Exercise actual bounded reads instead of substituting a filesystem response."""
    path = configuration / "mkdocs.yml"
    path.unlink()
    if mutation == "directory":
        path.mkdir()
    elif mutation == "linked":
        path.symlink_to(SOURCE / "mkdocs.yml")
    elif mutation == "oversized":
        path.write_bytes(b"x" * 2_097_153)
    assert validate_documentation_configuration(configuration).exit_code == expected


def test_linked_root_is_not_a_different_configuration_source(
    configuration: Path, tmp_path: Path
) -> None:
    """Reject all selected inputs reached through a linked checkout root."""
    root = tmp_path / "linked"
    root.symlink_to(configuration, target_is_directory=True)
    actual = validate_documentation_configuration(root)
    assert actual.exit_code == 2
    assert len(actual.reasons) == 4
    assert all(x.code == "documentation_link_refused" for x in actual.reasons)


@pytest.mark.parametrize("value", ["\0", "\ud800"])
def test_invalid_root_has_a_fixed_configuration_diagnostic(value: str) -> None:
    """Refuse invalid filesystem arguments without exposing interpreter text."""
    actual = validate_documentation_configuration(Path(value))
    assert actual.exit_code == 4
    assert actual.as_dict()["reasons"] == [{"path": "invocation", "code": "invalid_root"}]
