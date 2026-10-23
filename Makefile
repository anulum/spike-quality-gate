# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SPIKE-QUALITY-GATE — repository identity and validation foundation

.PHONY: docs licence metadata source-provenance
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

docs: .venv/bin/mkdocs
	.venv/bin/python tools/check_documentation.py --root . --configuration-only --json
	.venv/bin/mkdocs build --strict --clean --config-file mkdocs.yml
	.venv/bin/python tools/check_documentation.py --root . --json

licence: .venv/bin/reuse
	.venv/bin/reuse --no-multiprocessing lint

metadata: .venv/bin/python
	.venv/bin/python tools/check_repository_metadata.py --root . --json

source-provenance: .venv/bin/python
	.venv/bin/python tools/check_source_provenance.py --root . --json

.PHONY: native-tools native-tools-check

native-tools-check: .venv/bin/python
	.venv/bin/python tools/bootstrap_native_tools.py --root . --json

native-tools: .venv/bin/python .tool-cache/native-downloads/actionlint_1.7.12_linux_amd64.tar.gz .tool-cache/native-downloads/gitleaks_8.30.1_linux_x64.tar.gz
	.venv/bin/python tools/bootstrap_native_tools.py --root . --install --json

.tool-cache/native-downloads/actionlint_1.7.12_linux_amd64.tar.gz:
	mkdir -p .tool-cache/native-downloads
	curl --fail --location --proto '=https' --tlsv1.2 --max-time 90 --max-filesize 2353908 --output $@.part https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz || { rm -f -- $@.part; exit 1; }
	printf '%s  %s\n' '8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8' '$@.part' | sha256sum --check --strict || { rm -f -- $@.part; exit 1; }
	mv $@.part $@

.tool-cache/native-downloads/gitleaks_8.30.1_linux_x64.tar.gz:
	mkdir -p .tool-cache/native-downloads
	curl --fail --location --proto '=https' --tlsv1.2 --max-time 90 --max-filesize 8230402 --output $@.part https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz || { rm -f -- $@.part; exit 1; }
	printf '%s  %s\n' '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb' '$@.part' | sha256sum --check --strict || { rm -f -- $@.part; exit 1; }
	mv $@.part $@

.PHONY: dependencies

dependencies: .venv/bin/python
	.venv/bin/python tools/check_dependency_alignment.py --root . --json

.PHONY: workflows inventory preflight ci hook-check source-audit dependency-audits sbom test-ci

workflows: .venv/bin/python
	.venv/bin/python tools/check_workflow_policy.py --root . --json

inventory: .venv/bin/python
	.venv/bin/python tools/check_repository_inventory.py --root . --mode verify --json

preflight: .venv/bin/python
	.venv/bin/python tools/preflight.py --root . --profile local-scaffold --json

ci: preflight

hook-check: .venv/bin/pre-commit
	.venv/bin/pre-commit run --all-files --show-diff-on-failure

dependency-audits: .venv/bin/pip-audit
	.venv/bin/pip-audit --strict --require-hashes --no-deps --disable-pip --cache-dir .tool-cache/pip-audit --progress-spinner off --timeout 15 -r requirements-dev.txt
	.venv/bin/pip-audit --strict --require-hashes --no-deps --disable-pip --cache-dir .tool-cache/pip-audit --progress-spinner off --timeout 15 -r requirements-rejection.txt

source-audit: dependencies source-provenance workflows native-tools-check .venv/bin/bandit .venv/bin/zizmor
	.venv/bin/python tools/preflight_checks.py --root . --check gitleaks --json
	.venv/bin/bandit -r tools -q
	.tool-cache/native/bin/actionlint -color -shellcheck=
	.venv/bin/zizmor --offline --no-config --no-ignores --strict-collection .github/workflows
	$(MAKE) dependency-audits

sbom: dependencies .venv/bin/cyclonedx-py .venv/bin/reuse
	mkdir -p .tool-cache/reports
	.venv/bin/cyclonedx-py environment .venv/bin/python --output-reproducible --output-format JSON --output-file .tool-cache/reports/tooling.cdx.json
	.venv/bin/python tools/preflight_checks.py --root . --check source-spdx --json

test-ci: .venv/bin/python
	mkdir -p .tool-cache/ci-coverage .tool-cache/reports
	COVERAGE_FILE=$(CURDIR)/.tool-cache/ci-coverage/data .venv/bin/python -m coverage erase
	COVERAGE_FILE=$(CURDIR)/.tool-cache/ci-coverage/data .venv/bin/python -m coverage run --branch --parallel-mode -m pytest -q --basetemp=.tool-cache/ci-tests
	COVERAGE_FILE=$(CURDIR)/.tool-cache/ci-coverage/data .venv/bin/python -m coverage combine .tool-cache/ci-coverage
	COVERAGE_FILE=$(CURDIR)/.tool-cache/ci-coverage/data .venv/bin/python -m coverage report --fail-under=100
	COVERAGE_FILE=$(CURDIR)/.tool-cache/ci-coverage/data .venv/bin/python -m coverage json -o .tool-cache/reports/coverage.json
