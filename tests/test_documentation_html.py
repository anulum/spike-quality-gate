# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — HTML documentation inspection tests
"""Exercise the real structural parser and genuine native output."""

from pathlib import Path

from documentation_html import inspect_html


def test_links_anchors_headings_entities_comments_and_preformatted_text() -> None:
    """Retain structural facts while excluding comments and unevaluated script/style bodies."""
    document = inspect_html(
        '<!-- hidden note --><h1 id="heading">Hello &amp; world</h1>'
        '<a name="legacy" href="#heading">jump</a><img src="image.png" disabled>'
        '<span id="plain">ordinary</span><a href>empty</a>'
        "<pre>first<pre>nested</pre>last</pre></pre>"
        '<script src="bundle.js">ignored script</script><style>ignored style</style>'
        "<p>ending</p><br/>"
    )
    assert document.links == ("#heading", "image.png", "bundle.js")
    assert document.anchors == frozenset({"heading", "legacy", "plain"})
    assert document.headings == frozenset({"heading"})
    assert document.visible_text == "Hello & world jump ordinary empty first nested last ending"
    assert [text for text, pre in document.text if pre] == ["first", "nested", "last"]


def test_actual_native_page_exposes_real_api_anchors_and_no_source_header() -> None:
    """Inspect the genuine current MkDocs page instead of a fabricated successful renderer."""
    source = Path(__file__).resolve().parents[1]
    text = (source / ".tool-cache/site/validation-tooling/index.html").read_text()
    actual = inspect_html(text)
    assert "check_documentation" in actual.anchors
    assert "documentation_policy.validate_documentation_configuration" in actual.anchors
    assert "builder_execution_attested" in actual.visible_text
    assert "SPDX" + "-License-Identifier:" not in actual.visible_text


def test_empty_and_whitespace_documents_have_no_invented_content() -> None:
    """Keep an empty artifact distinguishable from a populated native page."""
    empty = inspect_html(" \n\t<!-- only a comment -->")
    assert empty.links == ()
    assert empty.anchors == empty.headings == frozenset()
    assert empty.text == () and empty.visible_text == ""
