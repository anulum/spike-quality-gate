# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real source-attribution boundaries
"""Exercise actual maintained source cohorts through the public API and command."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from check_source_provenance import main, validate_source_provenance

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/check_source_provenance.py"
LICENCE_TAG = "SPDX" + "-License-Identifier"
COPYRIGHT_TAG = "SPDX" + "-FileCopyrightText"


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Copy the actual maintained Git cohort, including this new guard and its tests."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=15,
    )
    root = tmp_path / "source"
    root.mkdir()
    for raw in result.stdout.split(b"\0"):
        if raw:
            name = raw.decode("utf-8")
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
    return root


def _api(root: Path, expected: int) -> list[object]:
    result = validate_source_provenance(root)
    assert result.exit_code == expected, result.as_dict()
    document = result.as_dict()
    assert set(document) == {"gate", "scope", "status", "reasons"}
    assert document["gate"] == "source_provenance"
    assert document["scope"] == "local_scaffold"
    assert document["status"] == {0: "pass", 2: "refused", 3: "unavailable"}[expected]
    reasons = document["reasons"]
    assert isinstance(reasons, list)
    assert str(root) not in json.dumps(document)
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
        timeout=15,
    )


def test_actual_source_and_repeated_public_command_are_read_only(candidate: Path) -> None:
    """Accept the real current source and reproduce byte-stable scoped CLI diagnostics."""
    before = {p.relative_to(candidate): p.read_bytes() for p in candidate.rglob("*") if p.is_file()}
    assert _api(candidate, 0) == []
    first = _invoke(candidate, "--json")
    second = _invoke(candidate, "--json")
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["reasons"] == []
    assert {
        p.relative_to(candidate): p.read_bytes() for p in candidate.rglob("*") if p.is_file()
    } == before


@pytest.mark.parametrize(
    ("name", "old", "new"),
    [
        ("tools/check_repository_metadata.py", "Commercial license available", "licence missing"),
        ("README.md", "SPIKE-QUALITY-GATE —", "Other project —"),
        ("README.md", "<!--", "# visible header"),
        ("README.md", "-->", "not closed"),
        ("README.md", "<!--", ""),
        ("tools/check_repository_metadata.py", "# ORCID:", "# Identifier:"),
        (
            "repository-domain.json.license",
            "Commercial license available",
            "commercial route missing",
        ),
    ],
)
def test_native_fields_project_and_markdown_comment_are_enforced(
    candidate: Path,
    name: str,
    old: str,
    new: str,
) -> None:
    """Refuse real source and sidecar attribution changes without changing the source format."""
    path = candidate / name
    content = path.read_text()
    assert old in content
    path.write_text(content.replace(old, new, 1))
    assert {"path": name, "code": "native_header_invalid"} in _api(candidate, 2)


@pytest.mark.parametrize("data", [b"", b"# short\n", b"\xff"])
def test_empty_truncated_and_non_utf8_native_source_refuses(candidate: Path, data: bytes) -> None:
    """Reject actual source byte inputs rather than accepting an extension as provenance."""
    (candidate / "README.md").write_bytes(data)
    assert _api(candidate, 2)


def test_additional_conflicting_native_spdx_is_not_hidden_by_a_valid_header(
    candidate: Path,
) -> None:
    """Retain a real contradictory declaration instead of checking the first header only."""
    path = candidate / "tools/check_repository_metadata.py"
    path.write_text(path.read_text() + f"\n# {LICENCE_TAG}: MIT\n")
    assert {
        "path": "tools/check_repository_metadata.py",
        "code": "licence_declaration_conflict",
    } in _api(candidate, 2)


def test_real_shebang_and_unicode_source_name_keep_native_header_semantics(candidate: Path) -> None:
    """Accept a real executable prefix and UTF-8 source filename with the full original header."""
    path = candidate / "tools" / "données.py"
    path.write_bytes(
        b"#!/usr/bin/env python3\n"
        + (candidate / "tools/check_repository_metadata.py").read_bytes()
    )
    assert _api(candidate, 0) == []


@pytest.mark.parametrize(
    "name",
    [
        "LICENSE",
        "LICENSES/AGPL-3.0-or-later.txt",
        "REUSE.toml",
        "docs/assets/anulum_logo.png",
        "docs/assets/anulum_logo_company.jpg",
        "docs/assets/fortis_studio_logo.jpg",
    ],
)
def test_actual_selected_licences_branding_and_recipe_cannot_be_overwritten(
    candidate: Path,
    name: str,
) -> None:
    """Bind original source bytes independently of a candidate-supplied licence annotation."""
    path = candidate / name
    path.write_bytes(path.read_bytes() + b"\nchanged")
    assert {"path": name, "code": "selected_original_changed"} in _api(candidate, 2)


def test_missing_selected_original_is_unavailable_and_nonregular_original_is_refused(
    candidate: Path,
) -> None:
    """Report both actual source removal and an inadmissible directory at the licence path."""
    path = candidate / "LICENSE"
    path.unlink()
    assert {"path": "LICENSE", "code": "source_unavailable"} in _api(candidate, 3)
    path.mkdir()
    assert {"path": "LICENSE", "code": "source_not_regular"} in _api(candidate, 2)


def test_unavailable_root_does_not_become_an_empty_success(tmp_path: Path) -> None:
    """Keep the unavailable actual source tree and all missing selected originals visible."""
    reasons = _api(tmp_path / "absent", 3)
    assert {"path": ".", "code": "source_directory_unavailable"} in reasons
    assert {"path": "LICENSE", "code": "source_unavailable"} in reasons


def test_root_and_child_links_refuse_without_following_source_aliases(
    candidate: Path,
    tmp_path: Path,
) -> None:
    """Exercise ordinary owned source-path aliases, without any external file target."""
    alias = tmp_path / "alias"
    alias.symlink_to(candidate, target_is_directory=True)
    assert _api(alias, 2) == [{"path": "source_tree", "code": "source_link_refused"}]
    (candidate / "linked.py").symlink_to(candidate / "tools/check_repository_metadata.py")
    assert {"path": "linked.py", "code": "source_link_refused"} in _api(candidate, 2)


def test_oversized_real_source_and_finite_tree_budget_refuse(candidate: Path) -> None:
    """Enforce the documented source-byte and actual-entry limits."""
    path = candidate / "README.md"
    original = path.read_bytes()
    path.write_bytes(b" " * 4_194_305)
    assert {"path": "README.md", "code": "source_limit_exceeded"} in _api(candidate, 2)
    path.write_bytes(original)
    directory = candidate / "source_population"
    directory.mkdir()
    for number in range(513):
        (directory / f"source_{number}.py").write_bytes(b"unqualified")
    assert {"path": "source_tree", "code": "tree_limit_exceeded"} in _api(candidate, 2)


def test_unknown_public_format_refuses_but_real_private_and_cache_paths_are_outside_scope(
    candidate: Path,
) -> None:
    """Reject unclassified public bytes without claiming the separate repository-inventory gate."""
    for relative in (
        "docs/internal/review.bin",
        ".tool-cache/result.bin",
        "tools/__pycache__/module.pyc",
    ):
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"out of this declared source cohort")
    assert _api(candidate, 0) == []
    (candidate / "unexpected.bin").write_bytes(b"public unselected bytes")
    assert {"path": "unexpected.bin", "code": "source_format_not_selected"} in _api(candidate, 2)


@pytest.mark.parametrize("name", ["additional.json", "ADDITIONAL.JSON", "Additional.JsOn"])
def test_actual_case_preserving_exact_sidecar_is_required(candidate: Path, name: str) -> None:
    """Accept mixed-case JSON only with its exact adjacent, enrolled, regular sidecar."""
    path = candidate / name
    path.write_bytes((candidate / ".zenodo.json").read_bytes())
    assert {"path": name, "code": "exact_sidecar_not_enrolled"} in _api(candidate, 2)
    sidecar = candidate / (name + ".license")
    sidecar.write_bytes((candidate / ".zenodo.json.license").read_bytes())
    assert _api(candidate, 0) == []
    sidecar.unlink()
    sidecar.symlink_to(candidate / ".zenodo.json.license")
    assert _api(candidate, 2)


@pytest.mark.parametrize(
    "data",
    [
        b"{",
        b"\xff",
        b'{"x":1,"x":2}',
        b'{"nested":{"x":1,"x":2}}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b'{"x":"\\ud800"}',
        b'{"\\ud800":1}',
        b'["\\udfff"]',
    ],
)
def test_json_decoding_preserves_duplicate_numeric_and_unicode_refusals(
    candidate: Path,
    data: bytes,
) -> None:
    """Reject genuine malformed byte inputs through the same public source API."""
    (candidate / ".zenodo.json").write_bytes(data)
    assert {"path": ".zenodo.json", "code": "invalid_source_json"} in _api(candidate, 2)


@pytest.mark.parametrize("key", [LICENCE_TAG, "spdx_license_identifier"])
def test_top_level_json_licence_fields_must_agree(candidate: Path, key: str) -> None:
    """Check each optional enclosing-file declaration against the actual sidecar licence."""
    path = candidate / ".zenodo.json"
    document: dict[str, object] = json.loads(path.read_text())
    document[key] = "MIT"
    path.write_text(json.dumps(document))
    assert {"path": ".zenodo.json", "code": "json_licence_conflict"} in _api(candidate, 2)
    document[key] = "AGPL-3.0-or-later"
    path.write_text(json.dumps(document))
    assert _api(candidate, 0) == []


def test_finite_exact_numbers_and_nested_component_licences_keep_their_meaning(
    candidate: Path,
) -> None:
    """Do not rewrite finite JSON numbers or confuse component and enclosing-file licences."""
    path = candidate / ".zenodo.json"
    path.write_bytes(b'{"number":1e10000,"components":[{"license":"MIT"}]}')
    before = path.read_bytes()
    assert _api(candidate, 0) == []
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["missing", "duplicate", "empty", "embedded"])
def test_json_copyright_records_are_exact_and_unambiguous(candidate: Path, change: str) -> None:
    """Require both canonical records once and refuse duplicate or malformed publisher records."""
    path = candidate / ".zenodo.json.license"
    text = path.read_text()
    record = f"{COPYRIGHT_TAG}: 1996-2026 Miroslav Šotek <protoscience@anulum.li> (concepts)\n"
    if change == "missing":
        text = text.replace(record, "")
    elif change == "duplicate":
        text += record
    elif change == "empty":
        text += f"{COPYRIGHT_TAG}: \n"
    else:
        text += f"{COPYRIGHT_TAG}: invalid {COPYRIGHT_TAG}: embedded\n"
    path.write_text(text)
    assert {"path": ".zenodo.json.license", "code": "copyright_records_invalid"} in _api(
        candidate, 2
    )


def test_distinct_publisher_record_is_preserved_and_orphan_sidecar_refuses(candidate: Path) -> None:
    """Retain an additional original notice while refusing a sidecar whose source is absent."""
    path = candidate / ".zenodo.json.license"
    path.write_text(path.read_text() + f"{COPYRIGHT_TAG}: 2026 External Publisher\n")
    before = path.read_bytes()
    assert _api(candidate, 0) == []
    assert path.read_bytes() == before
    (candidate / ".zenodo.json").unlink()
    assert {"path": ".zenodo.json.license", "code": "orphan_json_sidecar"} in _api(candidate, 2)


def test_public_cli_failures_help_and_human_output(candidate: Path) -> None:
    """Keep native command results and invalid invocation diagnostics controlled and scoped."""
    human = _invoke(candidate)
    assert human.returncode == 0 and human.stdout == "source_provenance: pass\n"
    (candidate / "README.md").write_text("missing native attribution")
    refused = _invoke(candidate)
    assert refused.returncode == 2 and "README.md: native_header_invalid" in refused.stdout
    for arguments in [("--root",), ("--unknown",)]:
        result = _invoke(candidate, "--json", *arguments)
        assert result.returncode == 4
        assert json.loads(result.stdout)["status"] == "invalid"
    help_result = _invoke(candidate, "--help")
    assert help_result.returncode == 0 and "Source root" in help_result.stdout


def test_real_public_report_stream_and_write_failures_preserve_configuration_precedence(
    candidate: Path,
    tmp_path: Path,
) -> None:
    """Use actual open, closed and read-only streams without substituting report producers."""
    stream = io.StringIO()
    assert main(["--root", str(candidate), "--json"], output=stream) == 0
    assert json.loads(stream.getvalue())["reasons"] == []
    stream.close()
    assert main(["--root", str(candidate), "--json"], output=stream) == 3
    path = tmp_path / "existing-report.txt"
    path.write_text("preserved")
    with path.open("r") as readonly:
        assert main(["--root", str(candidate)], output=readonly) == 3
        assert main(["--unknown"], output=readonly) == 4
    assert path.read_text() == "preserved"


@pytest.mark.parametrize("data", [b"", b"# short\n", b"plain non-comment source"])
def test_missing_native_source_prefix_and_incomplete_header_refuse(
    candidate: Path,
    data: bytes,
) -> None:
    """Require actual native comment syntax and the full header on maintained Python."""
    (candidate / "tools/check_repository_metadata.py").write_bytes(data)
    assert {"path": "tools/check_repository_metadata.py", "code": "native_header_invalid"} in _api(
        candidate, 2
    )


def test_duplicate_additional_publisher_notice_refuses(candidate: Path) -> None:
    """Retain distinct publishers without permitting an ambiguous duplicate notice."""
    path = candidate / ".zenodo.json.license"
    path.write_text(path.read_text() + 2 * f"{COPYRIGHT_TAG}: 2026 External Publisher\n")
    assert {"path": ".zenodo.json.license", "code": "copyright_records_invalid"} in _api(
        candidate, 2
    )


def test_non_utf8_source_name_is_a_controlled_refusal(candidate: Path) -> None:
    """Reject an actual unrepresentable source name without echoing its raw bytes."""
    name = os.fsdecode(b"invalid-\xff.py")
    (candidate / name).write_bytes((candidate / "tools/check_repository_metadata.py").read_bytes())
    assert {"path": "source_tree", "code": "invalid_source_name"} in _api(candidate, 2)


def test_new_original_licence_needs_source_selection_even_with_a_project_header(
    candidate: Path,
) -> None:
    """Prevent a copied licence being relabelled as authored project text."""
    path = candidate / "LICENSES/unselected.txt"
    path.write_bytes((candidate / "requirements-dev.in").read_bytes())
    assert {"path": "LICENSES/unselected.txt", "code": "original_source_not_selected"} in _api(
        candidate, 2
    )


@pytest.mark.parametrize("data", [b"[]", b"null", b"false", b"1e10000", b'"measured input"'])
def test_legitimate_json_root_values_do_not_imply_a_domain_schema(
    candidate: Path,
    data: bytes,
) -> None:
    """Validate source attribution for ordinary JSON data without inventing a root-object schema."""
    path = candidate / "measurements.json"
    path.write_bytes(data)
    (candidate / "measurements.json.license").write_bytes(
        (candidate / ".zenodo.json.license").read_bytes()
    )
    assert _api(candidate, 0) == []
    assert path.read_bytes() == data


@pytest.mark.parametrize("value", ["bad\0root", "\ud800"])
def test_invalid_root_name_is_reported_by_api_and_cli(value: str) -> None:
    """Return a fixed invocation report instead of an encoding or filesystem exception."""
    report = validate_source_provenance(Path(value))
    assert report.exit_code == 4
    assert report.as_dict()["reasons"] == [{"path": "invocation", "code": "invalid_root"}]
    output = io.StringIO()
    assert main(["--root", value, "--json"], output=output) == 4
    assert json.loads(output.getvalue())["status"] == "invalid"
