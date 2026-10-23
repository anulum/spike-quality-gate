# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — bounded workflow YAML decoding
"""Decode workflow YAML with explicit GitHub scalar and failure semantics."""

from __future__ import annotations

import math
import re

from workflow_rules import MAX_BYTES, WorkflowIssue


def load_workflow_yaml(data: bytes, name: str) -> object:
    """Decode bounded source-selected workflow YAML without executing constructors.

    Parameters
    ----------
    data : bytes
        Bounded UTF-8 workflow bytes.
    name : str
        Trusted repository-relative diagnostic location.

    Returns
    -------
    object
        Parsed value, or a WorkflowIssue for unavailable/invalid YAML.
    """
    if len(data) > MAX_BYTES:
        return WorkflowIssue(name, "input_limit_exceeded")
    try:
        import yaml
    except ImportError:
        return WorkflowIssue(name, "required_yaml_parser_unavailable", 3)

    class Loader(yaml.SafeLoader):
        """Keep GitHub-compatible boolean resolution local to this loader."""

        yaml_implicit_resolvers = {
            key: [pair for pair in values if pair[0] != "tag:yaml.org,2002:bool"]
            for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
        }

    Loader.add_implicit_resolver(
        "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False)$"), list("tTfF")
    )

    def mapping(loader: yaml.SafeLoader, node: yaml.Node) -> dict[str, object]:
        result: dict[str, object] = {}
        pairs: list[tuple[object, object]] = loader.construct_pairs(node, deep=True)
        for key, value in pairs:
            if not isinstance(key, str) or key in result:
                raise ValueError("unsupported or duplicate mapping key")
            result[key] = value
        return result

    Loader.add_constructor("tag:yaml.org,2002:map", mapping)
    try:
        text = data.decode("utf-8")
        tokens = list(yaml.scan(text))
        if len(tokens) > 10_000 or any(
            isinstance(token, (yaml.AliasToken, yaml.AnchorToken, yaml.TagToken))
            for token in tokens
        ):
            return WorkflowIssue(name, "yaml_construct_not_selected")
        loader = Loader(text)
        try:
            value: object = loader.get_single_data()
        finally:
            loader.dispose()
        pending: list[object] = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, float) and not math.isfinite(item):
                raise ValueError("nonfinite YAML scalar")
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
    except (UnicodeError, ValueError, RecursionError, yaml.YAMLError):
        return WorkflowIssue(name, "invalid_workflow_yaml")
    return value
