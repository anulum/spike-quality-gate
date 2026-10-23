# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — real inventory behaviour
"""Exercise actual preflight children, scoped omissions and failure sequencing."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from preflight import main, run_preflight

ROOT = Path(__file__).resolve().parents[1]


def test_focused_real_metadata_never_becomes_complete_preflight() -> None:
    """Observe actual metadata success while every other required check stays not_run."""
    report = run_preflight(ROOT, only=("repository-metadata",))
    assert report.exit_code == 2
    assert report.checks[0].status == "pass"
    assert all(x.status == "not_run" for x in report.checks[1:])
    assert report.as_dict()["status"] == "refused"


def test_real_missing_child_stops_and_retains_successors(tmp_path: Path) -> None:
    """Refuse unavailable tooling and keep all unlaunched successors visible."""
    report = run_preflight(tmp_path)
    assert report.exit_code == 3
    assert report.checks[0].status == "unavailable"
    assert all(x.status == "not_run" for x in report.checks[1:])


@pytest.mark.parametrize("selection", [(), ("unknown",), ("ruff", "ruff")])
def test_invalid_check_selection_never_launches(selection: tuple[str, ...]) -> None:
    """Reject empty, unknown or duplicated focused selectors."""
    assert run_preflight(ROOT, only=selection).exit_code == 4


def test_actual_cli_scoped_json_text_help_and_invocation_errors(tmp_path: Path) -> None:
    """Run actual finite CLI paths without triggering a full workstation suite."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--parallel-mode",
            "--source=tools",
            str(ROOT / "tools/preflight.py"),
            "--root",
            str(ROOT),
            "--only",
            "repository-metadata",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["checks"][0]["status"] == "pass"
    for arguments in (["--profile", "bad"], ["--unknown"], ["--profile"]):
        stream = io.StringIO()
        assert main([*arguments, "--json"], output=stream) == 4
        assert json.loads(stream.getvalue())["status"] == "invalid"
    stream = io.StringIO()
    assert main(["--root", str(tmp_path)], output=stream) == 3
    assert "not_run" in stream.getvalue()
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    closed = io.StringIO()
    closed.close()
    assert main(["--root", str(tmp_path)], output=closed) == 3
    assert main(["--unknown"], output=closed) == 4
