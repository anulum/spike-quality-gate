# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — source and JSON attribution
"""Check native source attribution and selected original bytes without domain claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import NoReturn, TextIO

LICENCE_TAG = "SPDX" + "-License-Identifier"
COPYRIGHT_TAG = "SPDX" + "-FileCopyrightText"
PROJECT_PREFIX = "SPIKE-QUALITY-GATE — "
HEADER = (
    f"{LICENCE_TAG}: AGPL-3.0-or-later",
    "Commercial license available",
    "© Concepts 1996–2026 Miroslav Šotek. All rights reserved.",
    "© Code 2020–2026 Miroslav Šotek. All rights reserved.",
    "ORCID: 0009-0009-3560-0851",
    "Contact: www.anulum.li | protoscience@anulum.li",
)
COPYRIGHTS = (
    "1996-2026 Miroslav Šotek <protoscience@anulum.li> (concepts)",
    "2020-2026 Miroslav Šotek <protoscience@anulum.li> (code)",
)
MAX_SOURCE_BYTES = 4_194_304
MAX_TREE_ENTRIES = 512
EXCLUDED = frozenset(
    {
        ".git",
        ".venv",
        ".tool-cache",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "docs/internal",
        "site",
        "dist",
        "build",
        "node_modules",
        "target",
    }
)
SELECTED_ORIGINALS = {
    "LICENSE": "d8a6cc31abc16b6748c7a21f21611f5a1ec33f67d22ca23d7da1c19b95496bee",
    "LICENSES/AGPL-3.0-or-later.txt": "d8a6cc31abc16b6748c7a21f21611f5a1ec33f67d22ca23d7da1c19b95496bee",
    "REUSE.toml": "98b34ca864b4df8bf85ffa7bc22a6e6301900a90fd292a03bb733657719ab603",
    "docs/assets/anulum_logo.png": "fe4b3b24226e87045d4aac09284f30ee8a83bd95f9af0509272a063e284067d3",
    "docs/assets/anulum_logo_company.jpg": "d98a731a2b4b3b8880979d2e2f2c5cb722cc45d3f75b988e81c301902c7d1143",
    "docs/assets/fortis_studio_logo.jpg": "844c5d764c8ad0a030e8f7b83c7e878bb4ebec42ea6e40223f65f344769568c0",
}
COMMENT_SUFFIXES = frozenset({".py", ".md", ".yml", ".yaml", ".toml", ".cff", ".in", ".txt"})
COMMENT_NAMES = frozenset(
    {".editorconfig", ".gitattributes", ".gitignore", "Makefile", "CODEOWNERS"}
)


@dataclass(frozen=True)
class SourceIssue:
    """Locate a fixed source-provenance diagnostic.

    Parameters
    ----------
    path : str
        Repository-relative source name, or the fixed scope name.
    code : str
        Authored diagnostic identifier.
    exit_code : int
        Refusal (2), unavailable input (3), or invalid invocation (4).
    """

    path: str
    code: str
    exit_code: int = 2


@dataclass(frozen=True)
class SourceReport:
    """Retain the complete deterministic source-attribution outcome.

    Parameters
    ----------
    reasons : tuple of SourceIssue
        All diagnoses, without supplied file contents or absolute paths.
    """

    reasons: tuple[SourceIssue, ...]

    @property
    def exit_code(self) -> int:
        """Return configuration, availability, refusal, then success precedence."""
        return max((x.exit_code for x in self.reasons), default=0)

    def as_dict(self) -> dict[str, object]:
        """Return only the named local source-provenance gate and located reasons."""
        return {
            "gate": "source_provenance",
            "scope": "local_scaffold",
            "status": {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[self.exit_code],
            "reasons": [{"path": x.path, "code": x.code} for x in self.reasons],
        }


def _source_paths(root: Path) -> tuple[set[str], list[SourceIssue]]:
    names: set[str] = set()
    reasons: list[SourceIssue] = []
    directories = [root]
    seen = 0
    while directories:
        directory = directories.pop()
        try:
            entries: list[Path] = []
            for path in directory.iterdir():
                relative = path.relative_to(root).as_posix()
                if relative in EXCLUDED or path.name == "__pycache__":
                    continue
                seen += 1
                if seen > MAX_TREE_ENTRIES:
                    return names, [*reasons, SourceIssue("source_tree", "tree_limit_exceeded")]
                entries.append(path)
            for path in sorted(entries):
                relative = path.relative_to(root).as_posix()
                try:
                    relative.encode("utf-8")
                except UnicodeError:
                    reasons.append(SourceIssue("source_tree", "invalid_source_name"))
                    continue
                if path.is_symlink():
                    reasons.append(SourceIssue(relative, "source_link_refused"))
                elif path.is_dir():
                    directories.append(path)
                else:
                    names.add(relative)
        except OSError:
            relative = directory.relative_to(root).as_posix()
            reasons.append(SourceIssue(relative, "source_directory_unavailable", 3))
    return names, reasons


def _read(root: Path, name: str) -> bytes | SourceIssue:
    path = root / name
    try:
        mode = path.stat(follow_symlinks=False).st_mode
        if not stat.S_ISREG(mode):
            return SourceIssue(name, "source_not_regular")
        with path.open("rb") as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
    except OSError:
        return SourceIssue(name, "source_unavailable", 3)
    if len(data) > MAX_SOURCE_BYTES:
        return SourceIssue(name, "source_limit_exceeded")
    return data


def _header_valid(text: str, markdown: bool, sidecar: bool) -> bool:
    lines = text.splitlines()
    if markdown:
        if not lines or lines[0] != "<!--" or len(lines) < 9 or lines[8] != "-->":
            return False
        fields = lines[1:8]
    elif sidecar:
        fields = lines[:7]
    else:
        if lines and lines[0].startswith("#!"):
            lines = lines[1:]
        if any(not line.startswith("# ") for line in lines[:7]):
            return False
        fields = [line.removeprefix("# ") for line in lines[:7]]
    return (
        len(fields) == 7
        and tuple(fields[:6]) == HEADER
        and fields[6].startswith(PROJECT_PREFIX)
        and len(fields[6]) > len(PROJECT_PREFIX)
    )


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _nonfinite(_value: str) -> NoReturn:
    raise ValueError("nonfinite JSON constant")


def _json_document(data: bytes) -> object:
    value: object = json.loads(
        data.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=_nonfinite,
        parse_int=Decimal,
        parse_float=Decimal,
    )
    pending: list[object] = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            item.encode("utf-8")
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return value


def _text_issues(name: str, text: str, *, sidecar: bool) -> list[SourceIssue]:
    reasons: list[SourceIssue] = []
    if not _header_valid(text, name.lower().endswith(".md"), sidecar):
        reasons.append(SourceIssue(name, "native_header_invalid"))
    declarations = re.findall(
        r"(?m)^\s*(?:#\s*)?" + re.escape(LICENCE_TAG) + r":\s*(.+?)\s*$", text
    )
    if declarations != ["AGPL-3.0-or-later"]:
        reasons.append(SourceIssue(name, "licence_declaration_conflict"))
    if sidecar:
        records = re.findall(r"(?m)^" + re.escape(COPYRIGHT_TAG) + r":(.*)$", text)
        records = [record.strip() for record in records]
        if (
            any(records.count(expected) != 1 for expected in COPYRIGHTS)
            or len(records) != len(set(records))
            or any(not record or COPYRIGHT_TAG in record for record in records)
        ):
            reasons.append(SourceIssue(name, "copyright_records_invalid"))
    return reasons


def validate_source_provenance(root: Path) -> SourceReport:
    """Inspect actual public source headers, JSON sidecars and selected originals.

    Parameters
    ----------
    root : pathlib.Path
        Caller-selected source tree, never changed by this check.

    Returns
    -------
    SourceReport
        All source-attribution diagnoses in deterministic relative-path order.

    Notes
    -----
    Fixed cache/build/private locations are outside this source cohort. This is
    not a Git-index, complete-tree, dependency, native REUSE or domain check.
    Every other entry is inspected; unknown formats and links refuse. There is
    a 512-entry tree limit and a four-MiB limit per regular source. Original
    licence, branding and attribution-recipe bytes are selected by source.
    Invalid UTF-8 or NUL-containing root names return an invocation diagnosis.
    """
    try:
        str(root).encode("utf-8")
        if "\0" in str(root):
            raise ValueError("invalid root")
    except ValueError:
        return SourceReport((SourceIssue("invocation", "invalid_root", 4),))
    if root.is_symlink():
        return SourceReport((SourceIssue("source_tree", "source_link_refused"),))
    names, reasons = _source_paths(root)
    for name in sorted(names | SELECTED_ORIGINALS.keys()):
        data = _read(root, name)
        if isinstance(data, SourceIssue):
            reasons.append(data)
            continue
        if name in SELECTED_ORIGINALS:
            if hashlib.sha256(data).hexdigest() != SELECTED_ORIGINALS[name]:
                reasons.append(SourceIssue(name, "selected_original_changed"))
            continue
        if name.startswith("LICENSES/"):
            reasons.append(SourceIssue(name, "original_source_not_selected"))
            continue
        path = Path(name)
        sidecar = name.lower().endswith(".json.license")
        if path.suffix.lower() == ".json":
            sibling = name + ".license"
            if sibling not in names:
                reasons.append(SourceIssue(name, "exact_sidecar_not_enrolled"))
            try:
                document = _json_document(data)
            except (UnicodeError, ValueError, RecursionError, DecimalException):
                reasons.append(SourceIssue(name, "invalid_source_json"))
            else:
                if isinstance(document, dict):
                    for key in (LICENCE_TAG, "spdx_license_identifier"):
                        if key in document and document[key] != "AGPL-3.0-or-later":
                            reasons.append(SourceIssue(name, "json_licence_conflict"))
            continue
        if sidecar and name[:-8] not in names:
            reasons.append(SourceIssue(name, "orphan_json_sidecar"))
        if not (sidecar or path.suffix.lower() in COMMENT_SUFFIXES or path.name in COMMENT_NAMES):
            reasons.append(SourceIssue(name, "source_format_not_selected"))
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            reasons.append(SourceIssue(name, "invalid_source_utf8"))
        else:
            reasons.extend(_text_issues(name, text, sidecar=sidecar))
    ordered = tuple(sorted(reasons, key=lambda x: (x.path, x.code, x.exit_code)))
    return SourceReport(ordered)


class _Arguments(argparse.Namespace):
    root: str
    json: bool


def main(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    """Run the read-only source-provenance CLI with controlled diagnostics.

    Parameters
    ----------
    argv : list of str or None, optional
        Command arguments, or the current process arguments.
    output : text stream or None, optional
        Report destination, defaulting to standard output.

    Returns
    -------
    int
        Zero for this complete named source check, 2 for refusal, 3 for
        unavailable input/output, and 4 for invalid invocation. Help is an
        informational operation and does not validate sources.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument(
        "--root", default=".", help="Source root; source files are never rewritten."
    )
    parser.add_argument("--json", action="store_true", help="Emit the scoped JSON report.")
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        report = SourceReport((SourceIssue("invocation", "invalid_arguments", 4),))
        json_output = True
    else:
        json_output = args.json
        report = (
            SourceReport((SourceIssue("invocation", "unknown_arguments", 4),))
            if unknown
            else validate_source_provenance(Path(args.root))
        )
    document = report.as_dict()
    text = (
        json.dumps(document, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        if json_output
        else "source_provenance: "
        + str(document["status"])
        + "\n"
        + "".join(f"{x.path}: {x.code}\n" for x in report.reasons)
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
