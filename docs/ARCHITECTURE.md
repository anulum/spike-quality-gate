<!--
SPDX-License-Identifier: AGPL-3.0-or-later
Commercial license available
© Concepts 1996–2026 Miroslav Šotek. All rights reserved.
© Code 2020–2026 Miroslav Šotek. All rights reserved.
ORCID: 0009-0009-3560-0851
Contact: www.anulum.li | protoscience@anulum.li
SPIKE-QUALITY-GATE — repository foundation
-->

# Repository architecture

## Current executable tooling

Metadata, source-provenance, workflow, dependency-alignment, documentation, inventory and preflight controls inspect declared local scopes. Native bootstrap checks selected executable and licence files. Received metadata cannot select policy or grant quality acceptance. Foundation qualification is in progress.

## Intended quality boundaries

| Component | Responsibility | Required evidence |
| --- | --- | --- |
| Admission | Interpret the whole selected input and ancestry | Actual container, conversion, source, policy, stream/channel/window, geometry and clock |
| Measurements | Retain every required located fact | Original ordinals, exposure, coverage, full numerator/denominator and uncertainty |
| Policy | Apply immutable typed limits | Complete methods, exact units/scopes, inclusive or strict bounds and severity |
| Report | Preserve all rows, unknowns and adverse facts | Full details, policy content and complete original source identity |
| Verification | Independently replay domain and current gates | Separate actual consumer, qualified roles and shared evidence |
| Consumers | Render or consume exact scoped findings | Studio, generator, benchmark and ledger contracts |

The prospective event_data_quality.report.v1 has nine required fields: schema_id, claims, source_ref, environment_ref, input_ref, conversion_context_refs, policy, checks and overall. This declaration is not registered or qualified support.

Four prospective operations are check, inspect, compare and verify. One library powers them; none is installed. Inspect resolves exact referenced bytes without recomputing a verdict. Compare requires matched policy content, methods, applicability and normalisation scope while permitting distinct dataset identities. Unknown or mismatched rows have no invented zero delta.

Retain all fourteen checks: monotonicity, resolution, overflow, wraparound, dead_pixels, hot_pixels, noise_floor, polarity_balance, duration, event_count, duplicates, spatial_bounds, rate_saturation and stream_gaps. Each complete stream/channel/half-open window retains the full planned row inventory, including empty observations and explicit earlier applicability exclusions.

Monotonicity preserves source order and the predecessor across chunk and window boundaries. Resolution uses the declared quantum, not the smallest observed gap. Its selected minimum-quantum comparator remains a lower bound on the numerical quantum; do not silently reinterpret it as a finer-resolution requirement. Container tick validity is distinct from an upstream device overflow or rollover assertion.

Dead-pixel interpretation needs actual adequate exposure and response expectations; absent events alone are insufficient. Hot classification uses strict rate greater-than, with equality separate. Background intervals are unioned before counting and represent a declared background event rate, not an unqualified signal/noise separation. Empty polarity denominators remain unavailable.

Duration is the observation window, including an empty but observed positive window. Event count includes duplicates. Duplicate excess spans nonadjacent occurrences and chunk boundaries under the complete declared event identity, without mutating source order. Spatial defects refused upstream remain input failures rather than fictitious report rows.

Peak rate uses complete prespecified bins and does not alone prove hardware saturation. Capture gaps come from actual coverage, including leading and trailing gaps; natural sensor silence does not establish a missing interval. Missing planned raw data is not zero count.

Policy parameters are canonical, typed and selected before observation. Compare exact reduced rationals through checked arithmetic and use the full admitted uncertainty interval. A straddling interval is unknown. Required unknowns make overall unknown while retaining every known failure; otherwise fail dominates warn and warn dominates pass. Wholly excluded populations supply no passing observation. A weaker need requires a different versioned policy, not a bypass flag.

Conversion attribution retains full source/target ancestry and located losses without subtracting adverse measurements. Unknown semantic roles cannot be registered by adding a schema label. Actual shared evidence and current verification remain separate from local report consistency.

Closed live and offline evaluation must agree for identical bytes and policy. Actual capture closure resolves sequence, watermark, reset, coverage and late events; wall time and provisional counters cannot close a window. A late event creates a new immutable source/report revision.

Exact duplicate detection may need proportional retained storage. Bound working RAM, geometry, bins, arithmetic, detail outputs and spill explicitly; no cropping, truncation or float fallback. No measured throughput, physical clock or durability guarantee is claimed.

Studio renders the actual policy, unknowns and located evidence without recomputing checks. A separately authorised benchmark exception cannot change the quality result or satisfy a failed quality precondition. Other evidence owners retain their own domains.
