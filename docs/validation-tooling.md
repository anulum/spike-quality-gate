<!--
SPDX-License-Identifier: AGPL-3.0-or-later
Commercial license available
© Concepts 1996–2026 Miroslav Šotek. All rights reserved.
© Code 2020–2026 Miroslav Šotek. All rights reserved.
ORCID: 0009-0009-3560-0851
Contact: www.anulum.li | protoscience@anulum.li
SPIKE-QUALITY-GATE — repository foundation
-->

# Repository validation tooling

The repository-metadata command is implemented. It validates the source-selected local descriptor, exact schema bytes and actual development lock. The source-provenance command is also implemented. A selected native-file bootstrap is also implemented for development executables. Development-dependency alignment is also available. Workflow inspection, documentation inspection, inventory and preflight orchestration are implemented. Their complete integration and qualification remain in progress.

## Available commands

Run from the repository root using its selected development environment:

    make metadata
    make source-provenance
    make docs
    make licence
    make native-tools
    make native-tools-check
    make dependencies

The metadata command is also directly available:

    .venv/bin/python tools/check_repository_metadata.py --root . --json

The three fixed inputs are repository-domain.json, schemas/repository-domain.schema.json and requirements-dev.txt. Each read is bounded to one MiB. The expected project, owner, lifecycle, empty capability/claim population, planned schema names and complete toolchain/profile tuple are selected by maintained source. Supplied fields or a substituted schema cannot choose another policy. The command reads no generated capability inventory and never rewrites an input. Its finite descriptor selection is enforced by maintained source without loading a received schema or requiring a runtime schema plugin. It also checks the actual executing interpreter against the selected final Python version; a declared matching version cannot qualify a different runtime.

A planned schema name is a declaration, not registration or support. This local governance schema is not a scientific evidence format. Metadata success does not qualify the installed environment, models, drivers, current trust, Common, numerical results or downstream consumers.

## Results and failures

The JSON report contains gate, scope, status and reasons. Located reasons contain authored codes and fixed repository-relative names, without echoing input contents or private paths. The same inputs produce byte-stable diagnostics.

| Exit | Meaning |
| --- | --- |
| 0 | The named complete metadata check passed |
| 2 | Supplied metadata, its limits or the actual lock is refused |
| 3 | Required input or report output is unavailable |
| 4 | Invocation or selected schema configuration is invalid |

Multiple input failures remain visible. Configuration takes precedence over availability, which takes precedence over refusal. An unavailable report destination cannot return success; output failure retains a prior configuration failure. Help is a separate informational operation and does not validate metadata.

The metadata, source-provenance, workflow and native-bootstrap APIs reject
NUL-containing or invalid UTF-8 root names with the fixed invalid_root
invocation diagnosis and exit 4. The native bootstrap report distinguishes
refused, unavailable and invalid outcomes consistently with its exit code,
so a missing native input retains its unavailable classification through
the preflight boundary.

The make docs and make licence targets invoke actual strict documentation rendering and native REUSE checking. Their scopes do not substitute for the remaining project-owned controls or complete foundation acceptance.

## Source provenance

The source-provenance API and command inspect the actual caller-selected public source tree. They check native seven-field headers, Markdown comment wrapping, the project notice, one consistent enclosing-file licence declaration and exact JSON sidecars. JSON parsing rejects duplicate members, nonfinite constants and invalid Unicode while preserving finite large numbers and nested component licences. Each JSON sidecar needs both canonical copyright records exactly once; additional distinct publisher notices remain unchanged.

Source selects the exact original licence texts, branding and REUSE recipe. An alternative annotation cannot qualify changed original bytes. Other source formats need an explicit maintained policy; unknown formats, links, missing originals and unsupported attribution refuse. This initial source cohort has a 512-entry limit and a four-MiB limit per regular source. Fixed cache/build directories and ignored private documentation are outside this named cohort. Actual Git-index/private-publication inspection, complete required-tree checks, installed dependency provenance and native REUSE are separate gates. No metadata, inventory or domain acceptance is implied.

Run make source-provenance or:

    .venv/bin/python tools/check_source_provenance.py --root . --json

Its report uses the same gate/scope/status/reasons structure and 4>3>2>0 precedence described above, with gate source_provenance. It never writes source inputs and retains all located diagnoses in deterministic order. It has no native subprocess or network fallback.

## Rejection-test runtime

The dedicated metadata tests exercise a genuinely different Python interpreter as well as the selected tooling interpreter. Provide python3.12 with coverage, or set SPIKE_QUALITY_GATE_REJECTION_PYTHON to its actual executable. Absence or an incorrectly selected interpreter fails this test; it is never skipped. This is a test fixture for environment refusal, not a supported replacement for the selected tooling runtime. Native source-provenance tests use the complete actual maintained source cohort and public file/API/CLI boundaries.

## Local commit hooks

The local pre-commit configuration runs native Ruff and NumPy docstrings, format checking, strict mypy, the metadata and source-provenance commands, REUSE and strict API documentation. It also runs native Bandit on maintained tooling and Gitleaks on the actual staged source. These checks cover the named current source surfaces; they do not qualify absent project controls, hosted automation or domain results.

## Native metadata API

::: check_repository_metadata

## Native source-provenance API

::: check_source_provenance

## Selected native tool files

The native-tools target downloads exact official Linux x86-64 Actionlint and Gitleaks archives into the repository cache, checks their selected archive digests, then installs only their named executable and original licence files. The Python bootstrap itself makes no network requests and executes no binary. Its selected receipt and expected sizes/hashes are maintained source; a received receipt cannot select a new policy. Existing changed files and any linked path refuse instead of being overwritten. Default native-tools-check is read-only. Archive file identity is separate from reproducible-build, audit findings or hosted qualification.

The local commit hook verifies selected native file identity before the native Gitleaks hook uses the repository-local executable. The two original upstream MIT licence texts are retained next to their installed files. Exact source references and artifact digests are in native-tool-provenance.json. Run make native-tools before the first hook/test invocation in a new checkout; the tool-specific tests use the actual downloaded archives and execute the installed version commands. Missing inputs fail instead of being skipped.

The installer report uses gate native_tools and scope selected_native_files, with operation install or verify, status and all authored reasons. It follows the documented 4>3>2>0 exit precedence. Installation may create missing selected files; it preserves every existing file and reports output failures. Verification writes nothing. Neither operation asserts numerical, hardware, security-audit or hosted CI acceptance.

::: bootstrap_native_tools

## Development dependency alignment

Development installation uses requirements-dev.txt both as the runtime lock and as isolated build constraints. This selects the hash-locked poetry-core backend for REUSE source builds. An isolated build with an incorrect backend artifact hash must refuse, even if the backend version matches. Cached installation and a fresh source build remain distinct evidence; neither proves bit-for-bit reproducibility of every installed payload.

Run make dependencies or .venv/bin/python tools/check_dependency_alignment.py --root . --json. The check first selects dependency-provenance.json by a digest in maintained source. That receipt records all 24 direct development inputs, the complete 103-package reachable graph, original artifact identifiers and hashes, original installed METADATA digests, raw requirements, active extras and licence declarations. Each selected original artifact hash occurs in its package's actual lock block. The selected graph's active version requirements and extras closure were evaluated independently of the runtime checker. REUSE's selected source archive and locally built wheel metadata are recorded separately. There are no domain runtime dependencies.

The command compares selected direct/hash locks, rejection-test lock, hooks, Make configuration, Python settings, native provenance and workflow inputs with maintained digests. It checks the actual executing interpreter, requires a virtual environment, compares every installed METADATA file, refuses unselected distribution metadata and requires the selected console files to exist and be executable. It also runs the read-only native-file verifier. Each input read is bounded to two MiB; the actual site-directory scan is bounded to 4096 entries. Source and metadata links, missing inputs and unsupported changes refuse with located fixed diagnostics. Received metadata cannot choose another path, policy, executable or error message.

Its report uses gate dependency_alignment and scope selected_tooling_inputs_and_installed_metadata, with the same 4>3>2>0 precedence. It performs no installation, network request or subprocess. Matching installed metadata does not prove every installed payload byte or command behaviour. This check does not grant vulnerability, hosted workflow, numerical or whole-foundation qualification. The workflow files and remaining workflow commands are still being integrated. The dedicated tests install the actual lock offline through uv into a disposable hard-linked environment, run uv's independent graph check, and exercise real API/CLI/file/environment refusals.

::: check_dependency_alignment

## Source and rendered documentation

The documentation hook and make docs first inspect the selected renderer configuration and publication metadata, then run the actual strict native MkDocs build. Only a successful build proceeds to .venv/bin/python tools/check_documentation.py --root . --json. A renderer failure stops the Make/hook chain. The configuration-only CLI operation reports its separate selected_documentation_configuration scope and does not inspect HTML. The full inspection API itself is read-only: it checks the existing native artifact against source and reports builder_execution_attested as false. A direct inspection result cannot attest who produced an artifact or whether a build command ran.

The initial-scaffold policy selects the renderer configuration and publication metadata, inspects all root Markdown pages and public documentation, and verifies actual generated pages, visible content, source headings, API references, local links, anchors and assets. Known private identifiers, private paths, visible attribution headers, unsupported release/install commands, status badges and DOI claims refuse. Native comments retain the original source headers. Local link targets stay within their source or rendered tree; private paths and links refuse. External URLs are parsed but not fetched or qualified. Each input is bounded to two MiB, and the combined inspected Markdown/HTML cohort to sixteen MiB; source and rendered trees have explicit entry limits. No domain capability, hosted status or publication authority follows from documentation inspection.

The public API returns fixed located diagnostics with the same 4>3>2>0 precedence. It never dynamically imports an API target or runs a builder. Actual Python API rendering remains with the configured native MkDocs/mkdocstrings builder.

For every documented module, inspection parses its actual bounded Python source without importing it. Every public top-level function or class and every public method or property defined directly on those classes must have its own native HTML target. Private definitions and imported aliases are outside this definition inventory. A module heading and valid remaining links cannot qualify missing public targets. Changed public names need a fresh native build; invalid or unavailable source cannot inherit an older artifact. This verifies API presence and navigation, alongside the documented source contract and behavioural tests; it does not prove that prose is semantically correct.

::: check_documentation

::: documentation_html

::: documentation_policy

The native renderer includes the original contribution, conduct, governance,
contributor, support, security and validation policies through its fixed file
hook. These are the root source files, without generated Markdown copies. The
selected hook is checked before the build; unavailable or linked policies and
colliding routes stop the renderer. Final inspection requires the actual policy
HTML and compares its headings and visible content with the original source,
so stale or missing policy pages cannot inherit a passing source inspection.

::: documentation_hooks


## Capability inventory

Run make inventory, or invoke the read-only default:

    .venv/bin/python tools/check_repository_inventory.py --root . --mode verify --json

Generate to an exclusive new caller-chosen output:

    .venv/bin/python tools/check_repository_inventory.py --root . --mode generate --output NEW_OUTPUT_PATH --json

Generation first validates the actual selected metadata inputs. It creates exactly the repository identity, lifecycle state, empty capabilities/claims/qualified schema arrays and raw descriptor digest. It needs neither a previous inventory nor a complete required tree. A planned schema name does not become qualified. The output has no self-digest, and its attribution sidecar is authored separately. Publication uses a same-directory temporary regular file and an exclusive hard link; existing files, directories and links are preserved. This is atomic exclusive creation, without a durability or concurrent-source-snapshot guarantee.

Verification independently checks the received inventory against actual metadata and source-selected policy. It checks all 72 required paths, actual file kinds, a bounded public source cohort, forbidden actual state, links, unexpected/generated material, source-size limits and actual native Git root/branch/remotes/index/private-ignore behaviour. Exact source-selected ignore, file-attribute and update configuration complements the finite native probes; a filename-specific private exception cannot select a weaker policy. The published repository accepts main, including an unborn main, or a detached HEAD as in a hosted pull-request checkout; any other named branch is refused. It accepts no remote, or exactly one remote named origin at its canonical public remote, https://github.com/anulum/spike-quality-gate, with or without the .git suffix; any other remote, URL or second remote is refused. Cache contents and ignored private documentation are outside the source cohort, after their enclosing paths are checked for links. Git must be available at /usr/bin/git on the selected Linux tooling platform. This does not qualify Git's build, history, remote transport or hosted settings.

Each source is limited to four MiB and the inspected tree to 512 entries. Git queries have finite direct-child deadlines and a one-MiB completed-output limit. Source identity, attribution, rendered documentation, dependency alignment and domain acceptance remain separate checks. Generated diagnostics use the documented 4>3>2>0 meanings, with distinct generation and verification scopes.

::: check_repository_inventory

::: repository_policy

::: repository_tree

::: repository_git

## Preflight orchestration

The full command is intended for CI or an explicitly reserved pre-push environment:

    .venv/bin/python tools/preflight.py --root . --profile local-scaffold --json

Focused diagnosis runs only maintained named checks:

    .venv/bin/python tools/preflight.py --root . --only repository-metadata --json

Every omitted check remains not_run, so focused diagnosis refuses complete preflight acceptance even when its selected child passes. The first actual failure stops further launches and retains every required successor. No received artifact chooses a program, argument vector or more permissive policy. JSON guards must return matching gate/status/reasons and exit semantics; native tools retain their actual exit. Child output is kept in temporary cache files and never echoed to callers. Completed output has a one-MiB limit per stream; this is not a live output-volume or system-wide resource ceiling. Direct children have finite deadlines and are reaped; descendant ownership remains with each launched tool.

The maintained chain includes the seven repository controls, native file identity, lint/format/strict types, REUSE, strict native documentation, Bandit, Gitleaks, Actionlint, offline Zizmor, both hash-locked vulnerability audits, the installed-environment CycloneDX inventory and infrastructure tests. The secret scanner receives a temporary projection of the source-selected public files, excluding private docs and caches; its actual findings remain blocking. The two Python locks are audited in full without resolution or production-only filtering. The software inventories describe the actual installed tooling environment through CycloneDX and the native REUSE source cohort through SPDX, including actual source checksums and declared licences. Both source scanners consume a temporary projection containing only source-selected public inputs, so private documentation is excluded independently of native Git ignore handling. The source-spdx auxiliary command writes only its fixed cache artifact, refuses linked outputs and reports only this native source-inventory operation. The source SPDX excludes attribution sidecars, licence texts and the REUSE annotation recipe; it does not claim to inventory those ancillary bytes. Package source-artifact hashes and licence provenance are separately retained in dependency-provenance.json. No runtime distribution or empty package build is fabricated.

Make ci invokes the full preflight; make hook-check invokes the real configured hooks; make source-audit runs named source/workflow/native/static/lock checks; make sbom generates the actual environment CycloneDX inventory and source SPDX inventory. These commands do not establish hosted execution, all-file SBOM coverage, independent review or domain qualification. Hosted use additionally needs the appropriate lifecycle/profile transition: the current local-only inventory policy deliberately refuses an origin remote or detached checkout.

::: preflight

Run a single named check as its own scoped operation with .venv/bin/python tools/preflight_checks.py --root . --check repository-metadata --json. Its single_named_infrastructure_check scope can pass only that command and never clears the full preflight.

::: preflight_checks

## Workflow policy API

::: check_workflow_policy

::: workflow_rules

::: workflow_yaml
