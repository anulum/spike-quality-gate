# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — repository inventory
"""Define the bounded initial repository cohort and safe inventory diagnostics."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

REQUIRED_PATHS = frozenset(
    (
        ".editorconfig",
        ".gitattributes",
        ".github/CODEOWNERS",
        ".github/FUNDING.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/dependabot.yml",
        ".github/pull_request_template.md",
        ".github/workflows/ci.yml",
        ".github/workflows/codeql.yml",
        ".github/workflows/docs.yml",
        ".github/workflows/pre-commit.yml",
        ".github/workflows/sbom.yml",
        ".github/workflows/scorecard.yml",
        ".github/workflows/security-audit.yml",
        ".gitignore",
        ".pre-commit-config.yaml",
        ".zenodo.json",
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "CONTRIBUTORS.md",
        "GOVERNANCE.md",
        "LICENSE",
        "LICENSES",
        "Makefile",
        "NOTICE.md",
        "README.md",
        "REUSE.toml",
        "ROADMAP.md",
        "SECURITY.md",
        "SUPPORT.md",
        "VALIDATION.md",
        "docs/ARCHITECTURE.md",
        "docs/THREAT_MODEL.md",
        "docs/adr/0001-repository-boundary.md",
        "pyproject.toml",
        "requirements-dev.txt",
        "tests",
        "tools/preflight.py",
        "repository-domain.json",
        "schemas/repository-domain.schema.json",
        "capability-inventory.json",
        "mkdocs.yml",
        "tools/check_repository_metadata.py",
        "tools/check_source_provenance.py",
        "tools/check_workflow_policy.py",
        "tools/check_dependency_alignment.py",
        "tools/check_documentation.py",
        "tools/check_repository_inventory.py",
        "docs/assets/anulum_logo_company.jpg",
        "docs/assets/anulum_logo.png",
        "docs/assets/fortis_studio_logo.jpg",
        "repository-domain.json.license",
        "schemas/repository-domain.schema.json.license",
        "capability-inventory.json.license",
        ".zenodo.json.license",
        "requirements-dev.in",
        "dependency-provenance.json",
        "dependency-provenance.json.license",
        "docs/index.md",
        "docs/validation-tooling.md",
        "tests/test_repository_metadata.py",
        "tests/test_source_provenance.py",
        "tests/test_workflow_policy.py",
        "tests/test_dependency_alignment.py",
        "tests/test_documentation.py",
        "tests/test_repository_inventory.py",
        "tests/test_preflight.py",
    )
)
PUBLIC_PATHS = REQUIRED_PATHS | frozenset(
    (
        "LICENSES/AGPL-3.0-or-later.txt",
        "native-tool-provenance.json",
        "native-tool-provenance.json.license",
        "requirements-rejection.in",
        "requirements-rejection.txt",
        "tests/test_documentation_html.py",
        "tests/test_documentation_policy.py",
        "tests/test_documentation_hooks.py",
        "tests/test_native_tools.py",
        "tests/test_preflight_checks.py",
        "tests/test_repository_git.py",
        "tests/test_repository_policy.py",
        "tests/test_repository_tree.py",
        "tests/test_workflow_rules.py",
        "tests/test_workflow_yaml.py",
        "tools/bootstrap_native_tools.py",
        "tools/documentation_html.py",
        "tools/documentation_policy.py",
        "tools/documentation_hooks.py",
        "tools/preflight_checks.py",
        "tools/repository_git.py",
        "tools/repository_policy.py",
        "tools/repository_tree.py",
        "tools/workflow_rules.py",
        "tools/workflow_yaml.py",
        "workflow-provenance.json",
        "workflow-provenance.json.license",
    )
)

SELECTED_CONFIGURATION = {
    ".gitignore": "1496cf35bb79982687452b079916f97ce553b4b52fd8a327d57806bc7383e2a3",
    ".gitattributes": "9a502800cfb44908c7778b7e919b0df652930d06bb0e34a971eecf159b98e25b",
    ".github/dependabot.yml": "27644f2cb8877960aceee2447a358e548e00bad6c677886cf67d21363f77f23e",
}
DIRECTORIES = frozenset({"LICENSES", "tests"})
EXCLUDED = frozenset(
    {
        ".git",
        ".venv",
        ".tool-cache",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "site",
        "dist",
        "build",
        "node_modules",
        "target",
        "docs/internal",
    }
)
FORBIDDEN_NAMES = frozenset(
    {
        ".coordination",
        "04_ARCANE_SAPIENCE",
        "agentic-shared",
        "agentic_project_memory",
        "agentic_group_memory",
        "AGENTS.md",
        "CLAUDE.md",
        "CODEX.md",
        "GEMINI.md",
        "GROK.md",
        "KIMI.md",
        "CREDENTIALS.md",
        "BACKUP",
        "ARCHIVE",
    }
)
MAX_FILE_BYTES = 4_194_304
MAX_ENTRIES = 512


@dataclass(frozen=True)
class InventoryIssue:
    """Locate an inventory diagnosis without exposing received contents.

    Parameters
    ----------
    path : str
        Repository-relative input or fixed operation name.
    code : str
        Authored diagnosis.
    exit_code : int
        Refusal, unavailability or invocation/configuration failure.
    """

    path: str
    code: str
    exit_code: int = 2


@dataclass(frozen=True)
class InventoryReport:
    """Describe generation or independent complete-tree inspection.

    Parameters
    ----------
    reasons : tuple of InventoryIssue
        All fixed diagnoses, in deterministic order.
    operation : str
        Generate or verify; generation never qualifies the complete tree.
    """

    reasons: tuple[InventoryIssue, ...]
    operation: str

    @property
    def exit_code(self) -> int:
        """Return configuration, availability, refusal, then success precedence."""
        return max((x.exit_code for x in self.reasons), default=0)

    def as_dict(self) -> dict[str, object]:
        """Return only the requested repository-infrastructure result."""
        return {
            "gate": "repository_inventory",
            "scope": (
                "validated_metadata_generation"
                if self.operation == "generate"
                else "initial_repository_tree_and_index"
            ),
            "operation": self.operation,
            "status": {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[self.exit_code],
            "reasons": [{"path": x.path, "code": x.code} for x in self.reasons],
        }


def admit_root(root: Path) -> Path | InventoryIssue:
    """Normalize a caller root and refuse invalid names or linked ancestors.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected checkout.

    Returns
    -------
    pathlib.Path or InventoryIssue
        Absolute lexical path, or a controlled diagnostic.
    """
    try:
        str(root).encode("utf-8")
        if "\0" in str(root):
            raise ValueError("invalid name")
        root = Path(os.path.abspath(root))
        if any(p.is_symlink() for p in (root, *root.parents)):
            return InventoryIssue("repository_root", "root_link_refused")
    except (UnicodeError, ValueError):
        return InventoryIssue("invocation", "invalid_root", 4)
    return root


def read_inventory_input(root: Path, name: str) -> bytes | InventoryIssue:
    """Read one fixed regular input without following a linked parent.

    Parameters
    ----------
    root : pathlib.Path
        Admitted absolute repository.
    name : str
        Maintained relative input name, never a received path selector.

    Returns
    -------
    bytes or InventoryIssue
        At most four MiB, or a fixed located diagnosis.
    """
    path = root / name
    if any(p.is_symlink() for p in (path, *path.parents)):
        return InventoryIssue(name, "input_link_refused")
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            return InventoryIssue(name, "input_not_regular")
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE_BYTES + 1)
    except OSError:
        return InventoryIssue(name, "input_unavailable", 3)
    if len(data) > MAX_FILE_BYTES:
        return InventoryIssue(name, "input_limit_exceeded")
    return data


def inspect_repository_configuration(root: Path) -> tuple[InventoryIssue, ...]:
    """Verify selected initial ignore, file-attribute and update-policy bytes.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected checkout; no received configuration chooses policy.

    Returns
    -------
    tuple of InventoryIssue
        Every unavailable or unselected configuration input. Exact ignore-byte
        selection complements native probes, which alone cannot establish the
        ignore result for every possible private filename.
    """
    admitted = admit_root(root)
    if isinstance(admitted, InventoryIssue):
        return (admitted,)
    reasons: list[InventoryIssue] = []
    for name, digest in SELECTED_CONFIGURATION.items():
        raw = read_inventory_input(admitted, name)
        if isinstance(raw, InventoryIssue):
            reasons.append(raw)
        elif hashlib.sha256(raw).hexdigest() != digest:
            reasons.append(InventoryIssue(name, "configuration_not_selected"))
    return tuple(reasons)
