# Deployment Validator

## Purpose

Evaluate supplied deployment artifacts against a defined validation profile.

This validator does not infer controls from missing evidence.

Controls may produce one of four outcomes:

- PASS
- FAIL
- UNVERIFIED
- NOT_APPLICABLE

UNVERIFIED is distinct from FAIL.

A control is FAIL only when supplied evidence proves non-conformance.

A control is UNVERIFIED when the required evidence is absent, incomplete, or outside scope.

---

## Mandatory Execution

The validator MUST:

1. Load validation.profile.json
2. Load validation.rules.json
3. Determine deployment profile
4. Determine artifact scope
5. Evaluate only applicable controls
6. Produce evidence-backed findings

The validator MUST NOT:

- Assume external systems exist.
- Assume missing files imply missing controls.
- Assume operational readiness from specification documents.
- Assume governance enforcement from runtime health checks.
