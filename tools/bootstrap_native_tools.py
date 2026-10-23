# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — selected native executable bootstrap
"""Install and verify source-selected native tool files without executing them."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TextIO, cast

PROVENANCE_SHA256 = "f67e72f329cc7cab151af6230d6916000b231e4c62eb4e2c04593ed30ea5d184"
TOOL_FILES: tuple[tuple[str, str, int, str, str, int, str], ...] = (
    (
        "actionlint",
        "actionlint_1.7.12_linux_amd64.tar.gz",
        2353908,
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
        "LICENSE.txt",
        6074530,
        "c872d6db8c6bf83a8eaa704fc93999f027d55dffbc63b8a6abdccb47df5f4cd4",
    ),
    (
        "gitleaks",
        "gitleaks_8.30.1_linux_x64.tar.gz",
        8230402,
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        "LICENSE",
        21958840,
        "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509",
    ),
)


@dataclass(frozen=True)
class NativeToolIssue:
    """Describe a selected native file failure without received text.

    Parameters
    ----------
    path : str
        Fixed repository-relative file or tool name.
    code : str
        Authored diagnostic identifier.
    exit_code : int
        Refusal (2), unavailable input/output (3), or invalid invocation (4).
    """

    path: str
    code: str
    exit_code: int = 2


@dataclass(frozen=True)
class NativeToolReport:
    """Report native file installation or verification, without execution claims.

    Parameters
    ----------
    reasons : tuple of NativeToolIssue
        All controlled input and output diagnoses.
    installed : bool
        Whether the caller requested installation of missing selected files.
    """

    reasons: tuple[NativeToolIssue, ...]
    installed: bool = False

    @property
    def exit_code(self) -> int:
        """Return configuration, availability, refusal, then success precedence."""
        return max((issue.exit_code for issue in self.reasons), default=0)

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic report describing only selected file identity."""
        return {
            "gate": "native_tools",
            "scope": "selected_native_files",
            "operation": "install" if self.installed else "verify",
            "status": {0: "pass", 2: "refused", 3: "unavailable", 4: "invalid"}[self.exit_code],
            "reasons": [{"path": issue.path, "code": issue.code} for issue in self.reasons],
        }


def _linked(root: Path, path: Path) -> bool:
    current = path
    while current != root:
        if current.is_symlink():
            return True
        current = current.parent
    return root.is_symlink()


def _read(root: Path, name: str, size: int) -> bytes | NativeToolIssue:
    path = root / name
    if _linked(root, path):
        return NativeToolIssue(name, "native_path_link_refused")
    try:
        with path.open("rb") as stream:
            data = stream.read(size + 1)
    except OSError:
        return NativeToolIssue(name, "native_file_unavailable", 3)
    if len(data) != size:
        return NativeToolIssue(name, "native_file_size_not_selected")
    return data


def bootstrap_native_tools(root: Path, *, install: bool = False) -> NativeToolReport:
    """Verify selected files or install missing ones from exact local archives.

    Parameters
    ----------
    root : pathlib.Path
        Source checkout containing the selected provenance receipt. The fixed
        archive and installation locations are under its own .tool-cache.
    install : bool, default False
        Permit writing missing binary/licence files after complete archive
        verification. Existing files are checked and never overwritten.

    Returns
    -------
    NativeToolReport
        File-identity results only. No network request, archive-wide extraction,
        subprocess, host-tool fallback or native audit is performed.
        Invalid UTF-8 or NUL-containing roots refuse before any installation.
    """
    try:
        str(root).encode("utf-8")
        if "\0" in str(root):
            raise ValueError("invalid root")
    except ValueError:
        return NativeToolReport((NativeToolIssue("invocation", "invalid_root", 4),), install)
    reasons: list[NativeToolIssue] = []
    receipt = _read(root, "native-tool-provenance.json", 2862)
    if isinstance(receipt, NativeToolIssue):
        return NativeToolReport((receipt,), install)
    if hashlib.sha256(receipt).hexdigest() != PROVENANCE_SHA256:
        return NativeToolReport(
            (NativeToolIssue("native-tool-provenance.json", "native_receipt_not_selected"),),
            install,
        )
    licences = {
        "actionlint": (1067, "03a26b06d224380a02bf100e05fff3b2dfc71b14d4e2fa685ec9963a87563c22"),
        "gitleaks": (1069, "e3884b252b3bfc045e55be43a34d1e80da070bc6f804ac95bf4660e97d62ebc6"),
    }
    for tool, archive, archive_size, archive_sha, licence, binary_size, binary_sha in TOOL_FILES:
        targets = (
            (".tool-cache/native/bin/" + tool, tool, binary_size, binary_sha, 0o755),
            (
                ".tool-cache/native/licences/" + tool + "/" + licence,
                licence,
                *licences[tool],
                0o644,
            ),
        )
        archive_data = b""
        if install:
            received = _read(root, ".tool-cache/native-downloads/" + archive, archive_size)
            if isinstance(received, NativeToolIssue):
                reasons.append(received)
                continue
            if hashlib.sha256(received).hexdigest() != archive_sha:
                reasons.append(NativeToolIssue(tool, "native_archive_not_selected"))
                continue
            archive_data = received
        for name, member, size, digest, mode in targets:
            path = root / name
            if _linked(root, path):
                reasons.append(NativeToolIssue(name, "native_path_link_refused"))
                continue
            if install and not path.exists():
                with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as archive_file:
                    stream = cast(BinaryIO, archive_file.extractfile(member))
                    data = stream.read(size + 1)
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as output:
                        output.write(data)
                    path.chmod(mode)
                except OSError:
                    reasons.append(NativeToolIssue(name, "native_output_unavailable", 3))
                    continue
            current = _read(root, name, size)
            if isinstance(current, NativeToolIssue):
                reasons.append(current)
            elif hashlib.sha256(current).hexdigest() != digest:
                reasons.append(NativeToolIssue(name, "native_file_not_selected"))
            elif mode == 0o755 and not os.access(path, os.X_OK):
                reasons.append(NativeToolIssue(name, "native_file_not_executable"))
    return NativeToolReport(tuple(reasons), install)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    """Run the native file bootstrap using bounded, fixed-text diagnostics.

    Parameters
    ----------
    argv : list of str or None
        Explicit command arguments; None reads process arguments.
    stdout : typing.TextIO or None
        Caller report stream; None uses the process standard output.

    Returns
    -------
    int
        Zero only for successful named file verification or installation;
        2 for refused files, 3 for unavailable files/output, 4 for invocation.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 4
    report = bootstrap_native_tools(args.root.absolute(), install=args.install)
    document = report.as_dict()
    text = (
        json.dumps(document, indent=2, ensure_ascii=True)
        if args.json
        else "Native file identity: " + str(document["status"])
    )
    try:
        output = sys.stdout if stdout is None else stdout
        output.write(text + "\n")
        output.flush()
    except (OSError, ValueError):
        return max(report.exit_code, 3)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
