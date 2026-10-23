# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — original-policy renderer integration tests
"""Exercise native file routing and the actual registered MkDocs callback."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from mkdocs.config import load_config
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import get_files

from documentation_hooks import on_files
from documentation_html import inspect_html
from documentation_policy import RENDERED_ROOT_DOCUMENTS
from repository_policy import PUBLIC_PATHS

SOURCE = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy_checkout(tmp_path: Path) -> Path:
    """Supply actual public build inputs, without any generated policy copies."""
    root = tmp_path / "checkout"
    root.mkdir()
    for name in sorted(PUBLIC_PATHS):
        source = SOURCE / name
        if source.is_file() and (name.startswith(("docs/", "tools/")) or name == "mkdocs.yml"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for source in SOURCE.glob("*.md"):
        shutil.copyfile(source, root / source.name)
    return root


def test_native_file_collection_reads_original_policy_sources(policy_checkout: Path) -> None:
    """Bind each rendered route to its original file and retain normal docs."""
    config = load_config(config_file=str(policy_checkout / "mkdocs.yml"))
    files = on_files(get_files(config), config=config)
    assert files.get_file_from_path("index.md") is not None
    for name in RENDERED_ROOT_DOCUMENTS:
        page = files.get_file_from_path(name)
        assert page is not None
        assert page.abs_src_path is not None
        assert Path(page.abs_src_path) == policy_checkout / name
        assert not (policy_checkout / "docs" / name).exists()


@pytest.mark.parametrize("problem", ["missing", "linked", "collision"])
def test_real_policy_source_and_route_failures_stop_the_builder(
    policy_checkout: Path, problem: str
) -> None:
    """Reject missing/linked original policies and duplicate native routes."""
    source = policy_checkout / "GOVERNANCE.md"
    if problem == "collision":
        shutil.copyfile(source, policy_checkout / "docs/GOVERNANCE.md")
    else:
        source.unlink()
        if problem == "linked":
            source.symlink_to(SOURCE / "GOVERNANCE.md")
    config = load_config(config_file=str(policy_checkout / "mkdocs.yml"))
    expected = "route already exists" if problem == "collision" else "policy unavailable"
    with pytest.raises(PluginError, match=expected):
        on_files(get_files(config), config=config)
    actual = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "-f",
            str(policy_checkout / "mkdocs.yml"),
        ],
        cwd=policy_checkout,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert actual.returncode != 0
    assert expected in actual.stdout + actual.stderr


def test_real_registered_hook_builds_all_policy_routes(policy_checkout: Path) -> None:
    """Exercise native event registration, policy rendering and local cross-links."""
    actual = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "-f",
            str(policy_checkout / "mkdocs.yml"),
        ],
        cwd=policy_checkout,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert actual.returncode == 0, actual.stdout + actual.stderr
    for name in RENDERED_ROOT_DOCUMENTS:
        rendered = policy_checkout / ".tool-cache/site" / Path(name).stem / "index.html"
        assert rendered.is_file()
        assert ("SPDX" + "-License-Identifier:") not in inspect_html(
            rendered.read_text()
        ).visible_text
