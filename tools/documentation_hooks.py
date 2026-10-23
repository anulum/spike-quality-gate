# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — render original repository policies
"""Include maintained root policies in the native documentation file collection."""

from __future__ import annotations

from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File, Files

from documentation_policy import RENDERED_ROOT_DOCUMENTS, DocumentationIssue, _read


def on_files(files: Files, *, config: MkDocsConfig) -> Files:
    """Render selected policies from their original repository files.

    Parameters
    ----------
    files : mkdocs.structure.files.Files
        Native collection produced from the configured documentation directory.
    config : mkdocs.config.defaults.MkDocsConfig
        Loaded native configuration whose path identifies the repository root.

    Returns
    -------
    mkdocs.structure.files.Files
        The same collection with fixed root policy sources added, without
        copying their content or admitting arbitrary repository files.

    Raises
    ------
    mkdocs.exceptions.PluginError
        A policy is unavailable, linked, oversized or has a colliding route.
    """
    root = Path(config.config_file_path).parent
    for name in sorted(RENDERED_ROOT_DOCUMENTS):
        if files.get_file_from_path(name) is not None:
            raise PluginError(f"Repository policy route already exists: {name}")
        source = _read(root, name)
        if isinstance(source, DocumentationIssue):
            raise PluginError(f"Repository policy unavailable: {name} ({source.code})")
        files.append(File(name, str(root), config.site_dir, config.use_directory_urls))
    return files
