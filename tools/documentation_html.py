# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — HTML documentation inspection
"""Read HTML links, anchors and visible text without evaluating embedded content."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(frozen=True)
class HtmlDocument:
    """Retain inspected HTML links, anchors, headings and visible text.

    Parameters
    ----------
    links : tuple of str
        Received href/src values in document order.
    anchors : frozenset of str
        Element ids and named anchor targets.
    headings : frozenset of str
        Ids declared by heading elements.
    text : tuple of tuple of str and bool
        Nonempty text fragments and whether each occurs in a preformatted block.
        Comments, script and style bodies are excluded.
    """

    links: tuple[str, ...]
    anchors: frozenset[str]
    headings: frozenset[str]
    text: tuple[tuple[str, bool], ...]

    @property
    def visible_text(self) -> str:
        """Return decoded visible text with normalised whitespace."""
        return " ".join(" ".join(value for value, _ in self.text).split())


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.anchors: set[str] = set()
        self.headings: set[str] = set()
        self.text: list[tuple[str, bool]] = []
        self._ignored = False
        self._pre = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignored = True
        if tag == "pre":
            self._pre += 1
        for key, value in attrs:
            if not value:
                continue
            if key in {"href", "src"}:
                self.links.append(value)
            if key == "id" or (tag == "a" and key == "name"):
                self.anchors.add(value)
                if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    self.headings.add(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._ignored = False
        if tag == "pre":
            self._pre = max(0, self._pre - 1)

    def handle_data(self, data: str) -> None:
        if not self._ignored and data.strip():
            self.text.append((data, self._pre > 0))


def inspect_html(text: str) -> HtmlDocument:
    """Inspect decoded HTML using the standard parser without executing content.

    Parameters
    ----------
    text : str
        Already bounded and decoded HTML document.

    Returns
    -------
    HtmlDocument
        Source-order links and visible fragments, plus anchor and heading sets.

    Notes
    -----
    This is structural inspection, not a browser, CSS visibility engine or
    producer-authenticity check. Scripts/styles are never evaluated. Native
    Markdown and MkDocs builds remain separate actual operations.
    """
    parser = _Parser()
    parser.feed(text)
    parser.close()
    return HtmlDocument(
        tuple(parser.links),
        frozenset(parser.anchors),
        frozenset(parser.headings),
        tuple(parser.text),
    )
