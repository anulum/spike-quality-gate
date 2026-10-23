# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — source and rendered documentation
"""Inspect actual source and native-rendered documentation without running a builder."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import TextIO
from urllib.parse import unquote, urlsplit

from documentation_html import HtmlDocument, inspect_html
from documentation_policy import (
    API_MODULES,
    FORBIDDEN_TEXT,
    PRIVATE_PARTS,
    RENDERED_ROOT_DOCUMENTS,
    ROOT_DOCUMENTS,
    UNSUPPORTED_CLAIM,
    DocumentationIssue,
    DocumentationReport,
    _linked,
    _read,
    validate_documentation_configuration,
)


def _tree(root: Path, relative: str, limit: int) -> tuple[list[str], list[DocumentationIssue]]:
    pending = [root / relative]
    files: list[str] = []
    issues: list[DocumentationIssue] = []
    count = 0
    while pending:
        directory = pending.pop()
        name = directory.relative_to(root).as_posix()
        if _linked(root, directory):
            issues.append(DocumentationIssue(name, "documentation_link_refused"))
            continue
        try:
            for path in directory.iterdir():
                count += 1
                if count > limit:
                    return files, [*issues, DocumentationIssue(relative, "document_tree_limit")]
                child = path.relative_to(root).as_posix()
                if relative == "docs" and "internal" in path.relative_to(root / "docs").parts:
                    continue
                if path.is_symlink():
                    issues.append(DocumentationIssue(child, "documentation_link_refused"))
                elif path.is_dir():
                    pending.append(path)
                else:
                    files.append(child)
        except OSError:
            issues.append(DocumentationIssue(name, "document_directory_unavailable", 3))
    return sorted(files), issues


def _root_documents(root: Path) -> tuple[list[str], list[DocumentationIssue]]:
    names = set(ROOT_DOCUMENTS)
    try:
        for count, path in enumerate(root.iterdir(), start=1):
            if count > 512:
                return sorted(names), [DocumentationIssue("source_root", "document_tree_limit")]
            if path.suffix == ".md":
                names.add(path.name)
    except OSError:
        return sorted(names), [
            DocumentationIssue("source_root", "document_directory_unavailable", 3)
        ]
    return sorted(names), []


def _without_header(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 9 and lines[0] == "<!--" and lines[8] == "-->":
        return "\n".join(lines[9:])
    return text


def _decode(root: Path, name: str) -> str | DocumentationIssue:
    raw = _read(root, name)
    if isinstance(raw, DocumentationIssue):
        return raw
    try:
        return raw.decode("utf-8")
    except UnicodeError:
        return DocumentationIssue(name, "invalid_document_utf8")


def _api_anchors(root: Path, module: str) -> frozenset[str] | DocumentationIssue:
    name = "tools/" + module + ".py"
    source = _decode(root, name)
    if isinstance(source, DocumentationIssue):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return DocumentationIssue(name, "invalid_api_source")
    symbols: set[str] = set()
    definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in tree.body:
        if isinstance(node, definitions) and not node.name.startswith("_"):
            qualified = module + "." + node.name
            symbols.add(qualified)
            if isinstance(node, ast.ClassDef):
                symbols.update(
                    qualified + "." + method.name
                    for method in node.body
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not method.name.startswith("_")
                )
    return frozenset(symbols)


def _link_issues(
    root: Path, name: str, document: HtmlDocument, anchors: dict[Path, frozenset[str]]
) -> list[DocumentationIssue]:
    reasons: list[DocumentationIssue] = []
    for index, value in enumerate(document.links):
        location = name + ":link[" + str(index) + "]"
        if UNSUPPORTED_CLAIM.search(value):
            reasons.append(DocumentationIssue(location, "unsupported_publication_claim"))
        try:
            link = urlsplit(value)
        except ValueError:
            reasons.append(DocumentationIssue(location, "invalid_document_link"))
            continue
        if (link.scheme in {"https", "http"} and not link.netloc) or (
            link.scheme == "mailto" and not link.path
        ):
            reasons.append(DocumentationIssue(location, "invalid_document_link"))
            continue
        if link.scheme in {"https", "http", "mailto"} or (not link.scheme and link.netloc):
            continue
        if link.scheme:
            reasons.append(DocumentationIssue(location, "unsupported_link_scheme"))
            continue
        decoded = unquote(link.path)
        if "\0" in decoded:
            reasons.append(DocumentationIssue(location, "invalid_document_link"))
            continue
        target = Path(os.path.abspath(root / name)).parent / decoded
        if not link.path:
            target = root / name
        elif link.path.startswith("/"):
            target = root / unquote(link.path).lstrip("/")
        target = Path(os.path.abspath(target))
        try:
            relative = target.relative_to(root)
        except ValueError:
            reasons.append(DocumentationIssue(location, "local_link_outside_scope"))
            continue
        if any(part in PRIVATE_PARTS for part in relative.parts):
            reasons.append(DocumentationIssue(location, "private_document_link"))
            continue
        if _linked(root, target):
            reasons.append(DocumentationIssue(location, "documentation_link_refused"))
            continue
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            reasons.append(DocumentationIssue(location, "local_link_unavailable"))
        elif link.fragment and unquote(link.fragment) not in anchors.get(target, frozenset()):
            reasons.append(DocumentationIssue(location, "local_anchor_unavailable"))
    return reasons


def validate_documentation(root: Path) -> DocumentationReport:
    """Inspect source pages, publication metadata and actual rendered HTML.

    Parameters
    ----------
    root : pathlib.Path
        Read-only caller-selected checkout. Native output must already exist at
        .tool-cache/site from the separate strict build.

    Returns
    -------
    DocumentationReport
        Actual content/link/projection results, with every failure preserved.

    Notes
    -----
    This function never invokes or certifies a builder. The Make/docs hook first
    runs the actual strict MkDocs command and only then calls this inspection.
    Direct inspection checks the existing artifact against source; it does not
    attest its producer, external URL availability or domain capabilities.
    """
    configuration = validate_documentation_configuration(root)
    if configuration.exit_code:
        return DocumentationReport(configuration.reasons)
    root = Path(os.path.abspath(root))
    reasons: list[DocumentationIssue] = []
    try:
        import markdown
    except ImportError:
        return DocumentationReport(
            tuple([*reasons, DocumentationIssue("markdown", "renderer_library_unavailable", 3)])
        )
    sources, issues = _tree(root, "docs", 512)
    reasons.extend(issues)
    sources = [name for name in sources if name.endswith(".md")]
    roots, issues = _root_documents(root)
    reasons.extend(issues)
    sources.extend(roots)
    site = root / ".tool-cache/site"
    rendered, issues = _tree(root, ".tool-cache/site", 1024)
    reasons.extend(issues)
    remaining_bytes = 16_777_216
    documents: dict[str, HtmlDocument] = {}
    html: dict[str, HtmlDocument] = {}
    for name in sources:
        text = _decode(root, name)
        if isinstance(text, DocumentationIssue):
            reasons.append(text)
            continue
        remaining_bytes -= len(text.encode("utf-8"))
        if remaining_bytes < 0:
            return DocumentationReport(
                tuple(
                    [*reasons, DocumentationIssue("documentation_cohort", "document_cohort_limit")]
                )
            )
        doc = inspect_html(markdown.markdown(text, extensions=["fenced_code", "tables", "toc"]))
        documents[name] = doc
        if not doc.headings:
            reasons.append(DocumentationIssue(name, "document_content_empty"))
        if FORBIDDEN_TEXT.search(doc.visible_text) or FORBIDDEN_TEXT.search(_without_header(text)):
            reasons.append(DocumentationIssue(name, "private_or_provenance_text_visible"))
        if UNSUPPORTED_CLAIM.search(doc.visible_text):
            reasons.append(DocumentationIssue(name, "unsupported_publication_claim"))
        if name == "CHANGELOG.md" and (
            "## [Unreleased]" not in text or re.search(r"(?m)^##\s+\[(?!Unreleased\])", text)
        ):
            reasons.append(DocumentationIssue(name, "release_not_selected"))
    for name in rendered:
        relative = Path(name).relative_to(".tool-cache/site")
        if any(part in PRIVATE_PARTS for part in relative.parts):
            reasons.append(DocumentationIssue(name, "private_rendered_path"))
        if name.endswith(".html"):
            text = _decode(root, name)
            if isinstance(text, DocumentationIssue):
                reasons.append(text)
            else:
                remaining_bytes -= len(text.encode("utf-8"))
                if remaining_bytes < 0:
                    return DocumentationReport(
                        tuple(
                            [
                                *reasons,
                                DocumentationIssue("documentation_cohort", "document_cohort_limit"),
                            ]
                        )
                    )
                html[name] = inspect_html(text)
                if FORBIDDEN_TEXT.search(html[name].visible_text):
                    reasons.append(DocumentationIssue(name, "private_or_provenance_text_visible"))
                if UNSUPPORTED_CLAIM.search(html[name].visible_text):
                    reasons.append(DocumentationIssue(name, "unsupported_publication_claim"))
    if not html:
        reasons.append(DocumentationIssue(".tool-cache/site", "rendered_html_unavailable", 3))
    source_anchors = {root / name: doc.anchors for name, doc in documents.items()}
    site_anchors = {root / name: doc.anchors for name, doc in html.items()}
    for name, doc in documents.items():
        reasons.extend(_link_issues(root, name, doc, source_anchors))
        directives = [
            fragment.removeprefix(":::").strip()
            for fragment, pre in doc.text
            if not pre and fragment.strip().startswith(":::")
        ]
        for module in directives:
            path = root / "tools" / (module + ".py")
            if module not in API_MODULES or not path.is_file() or _linked(root, path):
                reasons.append(DocumentationIssue(name, "api_reference_unavailable"))
        if not name.startswith("docs/"):
            if directives:
                reasons.append(DocumentationIssue(name, "api_reference_outside_renderer"))
            if name not in RENDERED_ROOT_DOCUMENTS:
                continue
            relative = Path(name).with_suffix("")
        else:
            relative = Path(name).relative_to("docs").with_suffix("")
        output = (
            relative.parent / "index.html" if relative.name == "index" else relative / "index.html"
        )
        built = html.get(".tool-cache/site/" + output.as_posix())
        if built is None:
            reasons.append(DocumentationIssue(name, "rendered_page_unavailable", 3))
            continue
        if not doc.headings <= built.anchors:
            reasons.append(DocumentationIssue(name, "rendered_headings_differ"))
        for fragment, preformatted in doc.text:
            fragment = " ".join(fragment.split())
            if not preformatted and fragment.startswith(":::"):
                module = fragment.removeprefix(":::").strip()
                if module not in built.anchors:
                    reasons.append(DocumentationIssue(name, "rendered_api_unavailable"))
                elif module in API_MODULES:
                    expected = _api_anchors(root, module)
                    if isinstance(expected, DocumentationIssue):
                        reasons.append(expected)
                    elif not expected <= built.anchors:
                        reasons.append(DocumentationIssue(name, "rendered_api_symbol_unavailable"))
            elif fragment not in built.visible_text:
                reasons.append(DocumentationIssue(name, "rendered_text_differs"))
    for name, doc in html.items():
        reasons.extend(
            _link_issues(site, str(Path(name).relative_to(".tool-cache/site")), doc, site_anchors)
        )
    required_text = {
        "README.md": "There is no installed event-quality package, quality-check runner, public quality command or qualified quality report.",
        "docs/index.md": "It has no installed event-quality package, public quality-check runner or qualified quality report.",
    }
    for name, text in required_text.items():
        if name in documents and text not in documents[name].visible_text:
            reasons.append(DocumentationIssue(name, "initial_nonclaim_missing"))
    return DocumentationReport(
        tuple(sorted(set(reasons), key=lambda x: (x.path, x.code, x.exit_code)))
    )


class _Arguments(argparse.Namespace):
    root: str
    json: bool
    configuration_only: bool


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    """Run read-only documentation inspection with fixed caller diagnostics.

    Parameters
    ----------
    argv : list of str or None
        Explicit arguments, or process arguments when None.
    stdout : text stream or None
        Report destination, defaulting to standard output.

    Returns
    -------
    int
        Zero for the named inspection, 2 for refusal, 3 for unavailable input or
        output, and 4 for invalid invocation. Help does not inspect a build.
    """
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument("--root", default=".", help="Read-only source and native output root.")
    parser.add_argument("--json", action="store_true", help="Emit a JSON report.")
    parser.add_argument(
        "--configuration-only",
        action="store_true",
        help="Check selected inputs before a build; do not inspect HTML.",
    )
    try:
        args, unknown = parser.parse_known_args(argv, namespace=_Arguments())
    except argparse.ArgumentError:
        report = DocumentationReport((DocumentationIssue("invocation", "invalid_arguments", 4),))
        json_output = True
    else:
        json_output = args.json
        report = (
            DocumentationReport((DocumentationIssue("invocation", "unknown_arguments", 4),))
            if unknown
            else (
                validate_documentation_configuration(Path(args.root))
                if args.configuration_only
                else validate_documentation(Path(args.root))
            )
        )
    document = report.as_dict()
    text = (
        json.dumps(document, sort_keys=True, indent=2) + "\n"
        if json_output
        else "documentation: "
        + str(document["status"])
        + "\n"
        + "".join(f"{x.path}: {x.code}\n" for x in report.reasons)
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
