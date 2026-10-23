# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — source and rendered documentation contract tests
"""Exercise genuine native artifacts, source changes, builds and public commands."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from check_documentation import main, validate_documentation
from repository_policy import PUBLIC_PATHS

SOURCE = Path(__file__).resolve().parents[1]


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    """Supply actual source plus immutable native artifacts without duplicating binaries."""
    root = tmp_path / "checkout"
    root.mkdir()
    for path in [
        *SOURCE.glob("*.md"),
        SOURCE / "mkdocs.yml",
        SOURCE / "CITATION.cff",
        SOURCE / ".zenodo.json",
        SOURCE / "Makefile",
        SOURCE / "LICENSE",
    ]:
        shutil.copyfile(path, root / path.name)
    for relative in sorted(name for name in PUBLIC_PATHS if name.startswith(("docs/", "tools/"))):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, target)
    for path in (SOURCE / ".tool-cache/site").rglob("*"):
        if path.is_file():
            target = root / path.relative_to(SOURCE)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, target)
    (root / ".venv").symlink_to(SOURCE / ".venv", target_is_directory=True)
    return root


def _write(path: Path, text: str | bytes) -> None:
    path.unlink()
    path.write_bytes(text.encode() if isinstance(text, str) else text)


def _codes(root: Path) -> tuple[int, set[str]]:
    actual = validate_documentation(root)
    assert actual.as_dict()["scope"] == "source_and_rendered_documentation"
    assert actual.as_dict()["builder_execution_attested"] is False
    return actual.exit_code, {x.code for x in actual.reasons}


def _invoke(root: Path, *args: str, python: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(python) if python is not None else sys.executable,
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            "--branch",
            "--source=tools",
            str(SOURCE / "tools/check_documentation.py"),
            "--root",
            str(root),
            *args,
        ],
        cwd=SOURCE,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_actual_api_cli_make_and_normal_docs_hook(candidate: Path) -> None:
    """Run genuine entry points and retain the read-only inspector/build distinction."""
    source = candidate / "README.md"
    original = source.read_bytes(), source.stat().st_mtime_ns
    assert _codes(candidate) == (0, set())
    first = _invoke(candidate, "--json")
    second = _invoke(candidate, "--json")
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["builder_execution_attested"] is False
    assert (source.read_bytes(), source.stat().st_mtime_ns) == original
    for cmd in [
        ["make", "docs"],
        [str(SOURCE / ".venv/bin/pre-commit"), "run", "docs", "--all-files"],
    ]:
        actual = subprocess.run(
            cmd, cwd=SOURCE, capture_output=True, text=True, timeout=30, check=False
        )
        assert actual.returncode == 0, actual.stdout + actual.stderr


@pytest.mark.parametrize(
    "symbol",
    [
        "check_repository_metadata.validate_repository_metadata",
        "check_repository_metadata.Report",
        "check_repository_metadata.Report.as_dict",
    ],
)
def test_missing_public_api_target_refuses_despite_valid_module_links(
    candidate: Path, symbol: str
) -> None:
    """Reject incomplete native API navigation even when every remaining link resolves."""
    path = candidate / ".tool-cache/site/validation-tooling/index.html"
    text = path.read_text()
    assert f'id="{symbol}"' in text
    changed = text.replace(f'id="{symbol}"', 'id="removed-public-target"').replace(
        f'href="#{symbol}"', 'href="#check_repository_metadata"'
    )
    _write(path, changed)
    code, reasons = _codes(candidate)
    assert code == 2
    assert "rendered_api_symbol_unavailable" in reasons
    actual = _invoke(candidate, "--json")
    assert actual.returncode == 2
    assert "rendered_api_symbol_unavailable" in actual.stdout


def test_changed_public_api_needs_a_fresh_native_documentation_build(candidate: Path) -> None:
    """Detect a real source API rename and accept its independently rendered new target."""
    path = candidate / "tools/check_repository_metadata.py"
    path.write_text(
        path.read_text().replace(
            "def validate_repository_metadata(", "def inspect_repository_metadata(", 1
        )
    )
    assert "rendered_api_symbol_unavailable" in _codes(candidate)[1]
    built = subprocess.run(
        ["make", "docs"],
        cwd=candidate,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    assert _codes(candidate) == (0, set())


@pytest.mark.parametrize("contents", [b"def invalid(\n", b"\xff"])
def test_invalid_documented_python_source_cannot_inherit_native_html(
    candidate: Path, contents: bytes
) -> None:
    """Refuse actual invalid source bytes while retaining the earlier valid native artifact."""
    (candidate / "tools/check_repository_metadata.py").write_bytes(contents)
    code, reasons = _codes(candidate)
    assert code == 2
    assert {"invalid_api_source", "invalid_document_utf8"} & reasons


def test_native_symbol_directive_does_not_replace_selected_module_policy(candidate: Path) -> None:
    """Keep the selected module scope even when the real renderer accepts a class target."""
    path = candidate / "docs/validation-tooling.md"
    path.write_text(path.read_text() + "\n::: check_repository_metadata.Report\n")
    built = subprocess.run(
        [str(SOURCE / ".venv/bin/mkdocs"), "build", "--strict", "--clean"],
        cwd=candidate,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    code, reasons = _codes(candidate)
    assert code == 2
    assert "api_reference_unavailable" in reasons


def test_real_renderer_failure_stops_make_before_final_inspection(candidate: Path) -> None:
    """Use a genuinely unresolved native API reference, not a fake failing executable."""
    path = candidate / "docs/validation-tooling.md"
    path.write_text(path.read_text() + "\n::: module_that_is_not_implemented\n")
    actual = subprocess.run(
        ["make", "docs"],
        cwd=candidate,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert actual.returncode != 0
    assert "module_that_is_not_implemented" in actual.stdout + actual.stderr
    assert "tools/check_documentation.py --root . --json" not in actual.stdout


def test_configuration_refusal_precedes_any_real_builder(candidate: Path) -> None:
    """Stop the native build chain before altered configuration could select another plugin."""
    path = candidate / "mkdocs.yml"
    path.write_text(path.read_text() + "\n")
    actual = subprocess.run(
        ["make", "docs"],
        cwd=candidate,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert actual.returncode != 0
    assert "documentation_configuration_not_selected" in actual.stdout
    assert "mkdocs build" not in actual.stdout


def test_existing_output_must_match_new_source_and_a_fresh_build_repairs_it(
    candidate: Path,
) -> None:
    """Reject stale native HTML, then exercise the real updated source-to-artifact path."""
    path = candidate / "docs/index.md"
    path.write_text(path.read_text() + "\n## Additional explanation\n\nCurrent source paragraph.\n")
    assert {"rendered_headings_differ", "rendered_text_differs"} <= _codes(candidate)[1]
    built = subprocess.run(
        ["make", "docs"],
        cwd=candidate,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    assert _codes(candidate) == (0, set())


@pytest.mark.parametrize(
    "reference,code",
    [
        ("missing.md", "local_link_unavailable"),
        ("README.md#absent-heading", "local_anchor_unavailable"),
        ("../outside.md", "local_link_outside_scope"),
        ("docs/internal/private.md", "private_document_link"),
        ("javascript:example", "unsupported_link_scheme"),
        ("http://[", "invalid_document_link"),
        ("https://", "invalid_document_link"),
        ("mailto:", "invalid_document_link"),
        ("%00", "invalid_document_link"),
    ],
)
def test_actual_source_links_refuse_invalid_targets(
    candidate: Path, reference: str, code: str
) -> None:
    """Inspect real Markdown/HTML links without following an external service."""
    path = candidate / "README.md"
    path.write_text(path.read_text() + '\n<a href="' + reference + '">example</a>\n')
    assert code in _codes(candidate)[1]


@pytest.mark.parametrize(
    "reference",
    [
        "README.md#spike-quality-gate",
        "/README.md#spike-quality-gate",
        "https://example.invalid/not-queried",
        "http://example.invalid/not-queried",
        "//example.invalid/not-queried",
        "mailto:no-send@example.invalid",
    ],
)
def test_valid_local_or_external_link_syntax_is_not_external_availability(
    candidate: Path, reference: str
) -> None:
    """Accept syntax while performing no external URL request or mail operation."""
    path = candidate / "README.md"
    path.write_text(path.read_text() + '\n<a href="' + reference + '">example</a>\n')
    assert _codes(candidate) == (0, set())


@pytest.mark.parametrize(
    "body,code",
    [
        ("SPDX" + "-License-Identifier: AGPL-3.0-or-later", "private_or_provenance_text_visible"),
        ("<!-- user/terminal-example -->", "private_or_provenance_text_visible"),
        ("SCPARCH-01", "private_or_provenance_text_visible"),
        ("QGARCH-01", "private_or_provenance_text_visible"),
        ("10.99999/example", "unsupported_publication_claim"),
        ("pip install spike-quality-gate", "unsupported_publication_claim"),
        ("spike-quality-gate inspect", "unsupported_publication_claim"),
        ("spike-quality-gate compare", "unsupported_publication_claim"),
        ("spike-quality-gate verify", "unsupported_publication_claim"),
        ("SPIKE-QUALITY-GATE RUN", "unsupported_publication_claim"),
        ("SPIKE-QUALITY-GATE CHECK", "unsupported_publication_claim"),
        ("uv pip install spike-quality-gate", "unsupported_publication_claim"),
        ("https://pypi.org/project/spike_quality_gate", "unsupported_publication_claim"),
        ("https://pypi.org/project/spike-quality-gate", "unsupported_publication_claim"),
        ("spike-quality-gate check", "unsupported_publication_claim"),
        (
            '<img src="https://img.shields.io/badge/example-pass-green">',
            "unsupported_publication_claim",
        ),
        ("::: module_that_is_not_implemented", "api_reference_unavailable"),
        ("::: check_documentation", "api_reference_outside_renderer"),
    ],
)
def test_source_provenance_private_and_unimplemented_claims_refuse(
    candidate: Path, body: str, code: str
) -> None:
    """Refuse unsupported public statements without removing honest baseline nonclaims."""
    path = candidate / "README.md"
    path.write_text(path.read_text() + "\n\n" + body + "\n")
    assert code in _codes(candidate)[1]


@pytest.mark.parametrize("change", ["missing_unreleased", "fake_release"])
def test_changelog_does_not_invent_a_release(candidate: Path, change: str) -> None:
    """Keep initial changelog semantics aligned with the actual unreleased repository."""
    path = candidate / "CHANGELOG.md"
    text = path.read_text()
    if change == "missing_unreleased":
        text = text.replace("## [Unreleased]", "## Changes")
    else:
        text += "\n## [0.0.1]\n"
    path.write_text(text)
    assert "release_not_selected" in _codes(candidate)[1]


def test_required_initial_nonclaim_cannot_silently_disappear(candidate: Path) -> None:
    """Refuse removal of the current explicit unsupported runtime boundary."""
    path = candidate / "README.md"
    path.write_text(
        path.read_text().replace("There is no installed event-quality package", "Changed boundary")
    )
    assert "initial_nonclaim_missing" in _codes(candidate)[1]


def test_additional_root_markdown_is_inspected(candidate: Path) -> None:
    """Inspect newly introduced root pages rather than only the original required names."""
    (candidate / "NEW-NOTE.md").write_text("# Note\n\nuser/terminal-example\n")
    assert "private_or_provenance_text_visible" in _codes(candidate)[1]


def test_private_source_is_excluded_but_never_linkable_or_publishable(candidate: Path) -> None:
    """Keep ignored internal material outside the source cohort and reject a rendered copy."""
    private = candidate / "docs/internal/note.md"
    private.parent.mkdir()
    private.write_text("user/terminal-example\n")
    assert _codes(candidate) == (0, set())
    leaked = candidate / ".tool-cache/site/internal/note.txt"
    leaked.parent.mkdir()
    leaked.write_text("not a public page")
    assert "private_rendered_path" in _codes(candidate)[1]


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("utf8", "invalid_document_utf8"),
        ("oversized", "document_limit_exceeded"),
        ("directory", "document_not_regular"),
        ("empty", "document_content_empty"),
    ],
)
def test_actual_source_decoding_type_and_size_admission(
    candidate: Path, mutation: str, code: str
) -> None:
    """Refuse malformed source documents through actual files."""
    path = candidate / "SUPPORT.md"
    path.unlink()
    if mutation == "utf8":
        path.write_bytes(b"\xff")
    elif mutation == "oversized":
        path.write_bytes(b"x" * 2_097_153)
    elif mutation == "directory":
        path.mkdir()
    else:
        path.write_text("<!-- empty -->")
    assert code in _codes(candidate)[1]


def test_missing_source_directory_and_missing_native_page_remain_unavailable(
    candidate: Path,
) -> None:
    """Retain actual missing-input outcomes instead of claiming a complete inspected build."""
    shutil.rmtree(candidate / "docs")
    assert _codes(candidate)[0] == 3
    (candidate / ".tool-cache/site/index.html").unlink()
    assert "rendered_html_unavailable" not in _codes(candidate)[1]


@pytest.mark.parametrize("where", ["source", "rendered"])
def test_linked_document_directories_refuse(candidate: Path, where: str) -> None:
    """Reject linked source and native artifact directories before traversing them."""
    path = candidate / ("docs" if where == "source" else ".tool-cache/site")
    retained = path.with_name(path.name + "-retained")
    path.rename(retained)
    path.symlink_to(retained, target_is_directory=True)
    assert "documentation_link_refused" in _codes(candidate)[1]


def test_link_target_and_linked_api_source_refuse(candidate: Path) -> None:
    """Keep local assets and native API sources inside the maintained regular-file tree."""
    path = candidate / "linked.md"
    path.symlink_to(SOURCE / "README.md")
    readme = candidate / "README.md"
    readme.write_text(readme.read_text() + "\n[linked](linked.md)\n")
    assert "documentation_link_refused" in _codes(candidate)[1]
    api = candidate / "tools/check_dependency_alignment.py"
    api.unlink()
    api.symlink_to(SOURCE / "tools/check_dependency_alignment.py")
    assert "api_reference_unavailable" in _codes(candidate)[1]


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_page", "rendered_page_unavailable"),
        ("missing_api", "rendered_api_unavailable"),
        ("invalid_utf8", "invalid_document_utf8"),
        ("private_text", "private_or_provenance_text_visible"),
        ("fake_doi", "unsupported_publication_claim"),
    ],
)
def test_actual_native_output_is_inspected(candidate: Path, mutation: str, code: str) -> None:
    """Change disposable genuine rendered artifacts while preserving the source originals."""
    path = candidate / ".tool-cache/site/validation-tooling/index.html"
    text = path.read_text()
    if mutation == "missing_page":
        path.unlink()
    elif mutation == "missing_api":
        _write(path, text.replace('id="check_dependency_alignment"', 'id="changed-api"'))
    elif mutation == "invalid_utf8":
        _write(path, b"\xff")
    elif mutation == "private_text":
        _write(path, text + "<p>user/terminal-example</p>")
    else:
        _write(path, text + "<p>10.99999/example</p>")
    assert code in _codes(candidate)[1]


def test_all_absent_native_html_cannot_pass(candidate: Path) -> None:
    """Require actual native HTML, not just an existing output directory."""
    for path in (candidate / ".tool-cache/site").rglob("*.html"):
        path.unlink()
    assert _codes(candidate)[0] == 3
    assert "rendered_html_unavailable" in _codes(candidate)[1]


@pytest.mark.parametrize("where,number", [("docs", 513), (".tool-cache/site", 1025), (".", 513)])
def test_source_root_and_native_output_tree_walks_are_bounded(
    candidate: Path, where: str, number: int
) -> None:
    """Refuse excessive actual directory entries rather than silently truncating a passing cohort."""
    for index in range(number):
        (candidate / where / f"entry-limit-{index}.txt").touch()
    assert "document_tree_limit" in _codes(candidate)[1]


def test_plain_text_invalid_arguments_help_and_unavailable_report_streams(candidate: Path) -> None:
    """Preserve authored diagnostics and real output failures for public command operations."""
    output = io.StringIO()
    assert main(["--root", str(candidate)], stdout=output) == 0
    assert output.getvalue().startswith("documentation: pass")
    for args in [["--root"], ["--json=received"], ["--unknown"]]:
        target = io.StringIO()
        assert main(["--json", *args], stdout=target) == 4
        assert json.loads(target.getvalue())["status"] == "invalid"
    output.close()
    assert main(["--root", str(candidate)], stdout=output) == 3
    assert main(["--unknown"], stdout=output) == 4
    with (candidate / "README.md").open("r") as readonly:
        assert main(["--root", str(candidate)], stdout=readonly) == 3
    help_result = _invoke(candidate, "--help")
    assert help_result.returncode == 0 and "--configuration-only" in help_result.stdout


def test_configuration_only_cli_is_not_a_full_inspection(candidate: Path) -> None:
    """Keep explicit pre-build success separate from absent rendered output."""
    shutil.rmtree(candidate / ".tool-cache/site")
    actual = _invoke(candidate, "--configuration-only", "--json")
    assert actual.returncode == 0
    assert json.loads(actual.stdout)["scope"] == "selected_documentation_configuration"
    assert _invoke(candidate, "--json").returncode == 3


@pytest.mark.parametrize("value", ["\0", "\ud800"])
def test_invalid_root_arguments_refuse_without_interpreter_errors(value: str) -> None:
    """Exercise fixed diagnostics through both public API and CLI argument parsing."""
    assert _codes(Path(value)) == (4, {"invalid_root"})
    output = io.StringIO()
    assert main(["--root", value, "--json"], stdout=output) == 4


def test_actual_missing_markdown_library_is_unavailable(candidate: Path, tmp_path: Path) -> None:
    """Use a real isolated interpreter with coverage installed and no Markdown package."""
    environment = tmp_path / "without-docs-library"
    uv = str(SOURCE / ".venv/bin/uv")
    for command in [
        [uv, "venv", "--python", sys.executable, str(environment)],
        [
            uv,
            "pip",
            "sync",
            "--offline",
            "--require-hashes",
            "--python",
            str(environment / "bin/python"),
            str(SOURCE / "requirements-rejection.txt"),
        ],
    ]:
        actual = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        assert actual.returncode == 0, actual.stdout + actual.stderr
    result = _invoke(candidate, "--json", python=environment / "bin/python")
    assert result.returncode == 3
    assert "renderer_library_unavailable" in result.stdout
    shutil.rmtree(environment)


@pytest.mark.parametrize("where", ["source", "rendered"])
def test_total_document_bytes_are_bounded(candidate: Path, where: str) -> None:
    """Refuse excessive real source or artifact bytes before retaining an unbounded cohort."""
    content = "# Heading\n\n<!--" + "x" * 2_000_000 + "-->"
    root = candidate if where == "source" else candidate / ".tool-cache/site"
    suffix = ".md" if where == "source" else ".html"
    for number in range(9):
        (root / ("cohort-limit-" + str(number) + suffix)).write_text(content)
    assert "document_cohort_limit" in _codes(candidate)[1]


def test_linked_entry_inside_document_tree_is_refused(candidate: Path) -> None:
    """Refuse a real linked asset entry before reading or publishing its target."""
    path = candidate / "docs/assets/linked.png"
    path.symlink_to(SOURCE / "docs/assets/anulum_logo.png")
    assert "documentation_link_refused" in _codes(candidate)[1]


def test_unlistable_owned_root_is_not_a_complete_source_inspection(candidate: Path) -> None:
    """Retain directory-read failure even when named configuration files remain readable."""
    mode = candidate.stat().st_mode & 0o777
    candidate.chmod(0o111)
    try:
        code, reasons = _codes(candidate)
        assert code == 3
        assert "document_directory_unavailable" in reasons
    finally:
        candidate.chmod(mode)


def test_missing_actual_documented_api_cannot_inherit_existing_html(candidate: Path) -> None:
    """Refuse a source API that disappeared while its earlier native page still exists."""
    (candidate / "tools/check_dependency_alignment.py").unlink()
    assert "api_reference_unavailable" in _codes(candidate)[1]


@pytest.mark.parametrize("name", ["CONTRIBUTING", "GOVERNANCE", "SUPPORT", "SECURITY"])
def test_missing_rendered_root_policy_cannot_pass_source_inspection(
    candidate: Path, name: str
) -> None:
    """Require actual policy pages rather than accepting root Markdown alone."""
    (candidate / ".tool-cache/site" / name / "index.html").unlink()
    code, reasons = _codes(candidate)
    assert code == 3
    assert "rendered_page_unavailable" in reasons


def test_changed_root_policy_requires_a_fresh_native_build(candidate: Path) -> None:
    """Reject stale policy HTML and recover through the ordinary build chain."""
    path = candidate / "GOVERNANCE.md"
    path.write_text(path.read_text() + "\n## Review ownership\n\nRetain source responsibility.\n")
    assert {"rendered_headings_differ", "rendered_text_differs"} <= _codes(candidate)[1]
    built = subprocess.run(
        ["make", "docs"], cwd=candidate, capture_output=True, text=True, timeout=30, check=False
    )
    assert built.returncode == 0, built.stdout + built.stderr
    assert _codes(candidate) == (0, set())
