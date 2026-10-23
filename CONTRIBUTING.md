<!--
SPDX-License-Identifier: AGPL-3.0-or-later
Commercial license available
© Concepts 1996–2026 Miroslav Šotek. All rights reserved.
© Code 2020–2026 Miroslav Šotek. All rights reserved.
ORCID: 0009-0009-3560-0851
Contact: www.anulum.li | protoscience@anulum.li
SPIKE-QUALITY-GATE — repository foundation
-->

# Contributing

Start from the actual maintained source and supported public interfaces. Preserve source, input order, complete policy-selected population, measurement, uncertainty, exposure, capture coverage, conversion ancestry and report semantics, complete input/output populations and source identity; do not substitute a reference implementation that shares the same unexamined assumption.

Each implementation includes integration through real entry points, fully annotated Python, NumPy-style public docstrings, native documentation, dedicated behavioural tests and measured statement and branch coverage. New and changed code targets full meaningful coverage without reducing existing coverage. Each actual maintained counterpart receives matching semantics, edge cases, tests, documentation and affected benchmarks.

Use the isolated project environment and the exact selected interpreter and dependency lock. Dependency changes must align hooks, local tools, CI and installed inventory. Do not add a placeholder package or a check that treats a missing tool as success.

Keep dataset inputs and evidence fixtures legally redistributable and bounded. Never include private datasets, credentials, native histories or large recordings. Original failed and partial domain observations remain distinguishable from superseded test-run output.

The foundation is still being assembled. Its current development graph is hash-locked for CPython 3.13.16 and installed through uv with hard links from the shared package cache. Use the exact selected interpreter and requirements; do not silently substitute another environment. The available make metadata, make source-provenance, make docs and make licence targets exercise the source-selected descriptor, source attribution, native documentation and source-licence checks respectively. The dependency-alignment command is also available through make dependencies. Documentation inspection follows a selected-configuration check and the real strict build in make docs. The workflow-policy and inventory controls are available through make workflows and make inventory. Full preflight and CI commands include the entire infrastructure test suite and network audits; run them in CI or an explicitly reserved pre-push environment. For focused diagnosis use the named preflight selection, which preserves all omitted checks as not_run and cannot clear overall acceptance. The initial local profile requires main and zero remotes; hosted activation needs a separate lifecycle transition. Complete foundation qualification and domain integration remain in progress. See [validation](VALIDATION.md) and [support](SUPPORT.md).

Run make native-tools before hooks and native-tool tests in a fresh checkout. Downloads are selected official Linux x86-64 archives with exact source-bound hashes; the local native file-identity hook verifies installed files and original licences. Native Gitleaks runs through the selected repository cache path. Changed existing native files refuse rather than being silently replaced.


## Development environment

The selected tooling platform is Linux x86-64 with CPython 3.13.16. Begin with the verified uv 0.13.4 tool identified in workflow-provenance.json; these instructions do not install an arbitrary latest tool. Run from this checkout on the intended working filesystem:

    mkdir -p .tool-cache/tmp .tool-cache/pre-commit
    export TMPDIR="$PWD/.tool-cache/tmp"
    export UV_CACHE_DIR="$(uv cache dir)"
    export UV_LINK_MODE=hardlink
    export UV_PYTHON_INSTALL_DIR="$PWD/.tool-cache/python"
    export PRE_COMMIT_HOME="$PWD/.tool-cache/pre-commit"
    export PYTHONDONTWRITEBYTECODE=1
    uv venv --python 3.13.16 .venv
    uv pip sync --require-hashes --build-constraints requirements-dev.txt --python .venv/bin/python requirements-dev.txt
    make native-tools
    make dependencies

The development lock also constrains isolated source-build dependencies. In particular, REUSE's Poetry backend must match the locked poetry-core version and artifact hashes. Keep the build-constraints option in local and CI bootstrap commands; a runtime lock alone does not select the isolated build environment.

Alignment must pass before the installed graph is treated as the selected environment. Its original installed metadata includes the selected source-built REUSE wheel; matching names and versions alone does not qualify a differently built installation. A metadata difference requires source review and a justified selection update, never automatic acceptance of changed bytes. The dedicated installation tests reproduce the selected graph offline from its qualified cache; that is not a claim that every fresh online build is identical.

The tests also need a real unsupported interpreter to verify refusal. Prepare its separate, hash-locked fixture without changing the supported tooling environment:

    uv venv --python 3.12.14 .tool-cache/python-rejection
    uv pip sync --require-hashes --python .tool-cache/python-rejection/bin/python requirements-rejection.txt
    export SPIKE_QUALITY_GATE_REJECTION_PYTHON="$PWD/.tool-cache/python-rejection/bin/python"

Install ordinary source hooks with .venv/bin/pre-commit install. Use focused tests and named checks for the changed surface. The full make ci and make preflight include all infrastructure tests and online vulnerability checks; reserve them for CI or an explicitly reserved pre-push environment. Do not infer full acceptance from the successful focused preflight child.
