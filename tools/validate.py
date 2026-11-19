#!/usr/bin/env python3
"""Offline checks for the deployment-validator skill.

Checks:
  1. Every JSON file in the repo parses.
  2. validation.schema.json is a valid Draft 2020-12 schema.
  3. SKILL.md has YAML frontmatter with name and description, and every
     file it references exists.
  4. Cross-file consistency between profiles, rules and schema.
  5. Golden examples: examples/valid/*.json must validate and match the
     reference decision engine; examples/invalid/*.json must be rejected
     for the reason listed in examples/invalid/MANIFEST.json.

Runs offline with only the standard library and jsonschema.
Exit code 0 = all checks passed, 1 = at least one failure. Pass -v to list every check.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    sys.exit("jsonschema is not installed: pip install -r requirements-dev.txt")

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
PROFILE = ROOT / "validation.profile.json"
RULES = ROOT / "validation.rules.json"
SCHEMA = ROOT / "validation.schema.json"
PROMPT = ROOT / "validation.prompt.md"
VALID_DIR = ROOT / "examples" / "valid"
INVALID_DIR = ROOT / "examples" / "invalid"
MANIFEST = INVALID_DIR / "MANIFEST.json"

OPERATIONAL_GROUPS = {"runtime", "database", "observability", "security"}
GOVERNANCE_GROUPS = {"governance", "auditability"}
ISSUE = {"FAIL", "UNVERIFIED"}

VERBOSE = "-v" in sys.argv[1:]
SUMMARY = re.compile(r"(validates against|is rejected|decision is|meta-valid|frontmatter name)")
failures: list[str] = []
passes = 0


def check(ok: bool, message: str) -> bool:
    global passes
    if ok:
        passes += 1
        if VERBOSE or SUMMARY.search(message):
            print(f"ok    {message}")
    else:
        failures.append(message)
        print(f"FAIL  {message}")
    return ok


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        check(False, f"{path.relative_to(ROOT)} does not parse: {exc}")
        return None


# ---------------------------------------------------------------- 1. parse
def check_parse() -> None:
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" in path.parts:
            continue
        check(load_json(path) is not None, f"{path.relative_to(ROOT)} parses")


# -------------------------------------------------------------- 3. SKILL.md
def check_skill_md() -> None:
    text = SKILL.read_text(encoding="utf-8") if SKILL.exists() else ""
    check(bool(text), "SKILL.md exists")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not check(m is not None, "SKILL.md starts with YAML frontmatter"):
        return
    front = m.group(1)
    name = re.search(r"^name:\s*(\S+)\s*$", front, re.M)
    check(name is not None and name.group(1) == "deployment-validator",
          "SKILL.md frontmatter name is deployment-validator")
    desc = re.search(r"^description:\s*(.+?)(?=^\w+:|\Z)", front, re.M | re.S)
    desc_text = desc.group(1) if desc else ""
    check(len(desc_text.strip()) > 40, "SKILL.md frontmatter has a description")
    check("use when" in desc_text.lower(), "SKILL.md description states when to use it")

    referenced = set(re.findall(r"`((?:validation\.[a-z]+|README)\.(?:json|md))`", text))
    for name_ in sorted(referenced):
        check((ROOT / name_).exists(), f"SKILL.md references {name_}, which exists")
    for required in (PROFILE.name, RULES.name, SCHEMA.name, PROMPT.name):
        check(required in referenced, f"SKILL.md references {required}")

    # The old singular filename must not come back anywhere.
    for path in ROOT.rglob("*"):
        if path.is_file() and ".git" not in path.parts and path.suffix in {".md", ".json", ".py", ".yml"}:
            if path.name == "validate.py":
                continue
            check("validation.rule.json" not in path.read_text(encoding="utf-8"),
                  f"{path.relative_to(ROOT)} does not reference validation.rule.json")


# ------------------------------------------------------- 4. cross-file
def check_cross_file(profile, rules, schema) -> None:
    groups = set(rules["control_groups"])
    platforms = set(rules["platforms"])
    evidence_types = set(rules["evidence_types"])
    controls = rules["controls"]

    ids = [c["id"] for c in controls]
    check(len(ids) == len(set(ids)), "control ids are unique")
    for c in controls:
        cid = c.get("id", "?")
        for key in ("id", "name", "group", "platforms", "required_evidence", "evaluation", "blocking"):
            check(key in c, f"{cid} has {key}")
        check(c.get("group") in groups, f"{cid} group {c.get('group')} is a declared control group")
        check(bool(c.get("platforms")) and set(c["platforms"]) <= platforms | {"any"},
              f"{cid} platforms are declared")
        check(bool(c.get("required_evidence")) and set(c["required_evidence"]) <= evidence_types,
              f"{cid} required_evidence types are declared")
        ev = c.get("evaluation", {})
        check(all(ev.get(k) for k in ("type", "pass_when", "fail_when")),
              f"{cid} evaluation has type, pass_when and fail_when")
        check(isinstance(c.get("blocking"), bool), f"{cid} blocking is a boolean")
        check(re.match(schema["$defs"]["control"]["properties"]["id"]["pattern"], cid) is not None,
              f"{cid} matches the schema id pattern")

    check("version" in profile and "version" in rules, "profile and rules files carry a version")
    for pname, p in profile["profiles"].items():
        for key in ("description", "requires", "optional", "decision_policy"):
            check(key in p, f"profile {pname} has {key}")
        req, opt = set(p.get("requires", [])), set(p.get("optional", []))
        check(req <= groups and opt <= groups, f"profile {pname} only names declared groups")
        check(not (req & opt), f"profile {pname} does not list a group as both required and optional")
        check("runtime" in req, f"profile {pname} requires runtime")
        dp = p.get("decision_policy", {})
        check(all(dp.get(k) is True for k in
                  ("unverified_required_blocks", "fail_required_blocks", "fail_blocking_blocks")),
              f"profile {pname} decision_policy matches the SKILL.md decision rules (all true)")
        for g in sorted(req):
            check(any(c["group"] == g and c["blocking"] and "any" in c["platforms"] for c in controls),
                  f"profile {pname}: required group {g} has a blocking control for any platform")

    props = schema["properties"]
    check(set(props["deployment_profile"]["enum"]) == set(profile["profiles"]),
          "schema deployment_profile enum matches validation.profile.json")
    check(set(schema["$defs"]["control"]["properties"]["group"]["enum"]) == groups,
          "schema control group enum matches validation.rules.json control_groups")
    check(set(props["deployment_platforms"]["items"]["enum"]) == platforms | {"unknown"},
          "schema platform enum matches validation.rules.json platforms (+ unknown)")

    no_gov = sorted(n for n, p in profile["profiles"].items()
                    if not (set(p["requires"]) | set(p["optional"])) & GOVERNANCE_GROUPS)
    schema_no_gov = []
    for rule in schema.get("allOf", []):
        then = rule.get("then", {}).get("properties", {}).get("governance_conformance", {})
        if then.get("const") == "NOT_APPLICABLE":
            schema_no_gov = sorted(rule["if"]["properties"]["deployment_profile"]["enum"])
    check(no_gov == schema_no_gov,
          "schema governance NOT_APPLICABLE profiles match profiles without governance groups")


# ------------------------------------------------- reference decision engine
def expected_controls(profile, rules, profile_name, platforms):
    p = profile["profiles"][profile_name]
    req, opt = set(p["requires"]), set(p["optional"])
    out = {}
    for c in rules["controls"]:
        applicable = (c["group"] in req | opt) and (
            "any" in c["platforms"] or bool(set(c["platforms"]) & set(platforms)))
        out[c["id"]] = {
            "group": c["group"], "name": c["name"], "blocking": c["blocking"],
            "applicable": applicable,
            "required": applicable and c["group"] in req and c["blocking"],
        }
    return out, req


def decide(controls):
    critical = [c["id"] for c in controls
                if (c["required"] and c["status"] in ISSUE) or (c["blocking"] and c["status"] == "FAIL")]
    warnings = [c["id"] for c in controls if c["status"] in ISSUE and c["id"] not in critical]
    if critical:
        decision = "NOT_READY"
    elif warnings:
        decision = "READY_WITH_WARNINGS"
    else:
        decision = "READY"
    return decision, critical, warnings


def sub_result(controls, groups):
    scoped = [c for c in controls if c["group"] in groups and c["status"] != "NOT_APPLICABLE"]
    if any(c["status"] == "FAIL" and (c["required"] or c["blocking"]) for c in scoped):
        return "FAIL"
    if any(c["status"] == "UNVERIFIED" and c["required"] for c in scoped):
        return "UNVERIFIED"
    return "PASS"


def check_semantics(doc, profile, rules, label) -> None:
    exp, req_groups = expected_controls(profile, rules, doc["deployment_profile"], doc["deployment_platforms"])
    got = doc["controls"]
    rule_ids = [c["id"] for c in rules["controls"]]
    got_rule_ids = [c["id"] for c in got if not c["id"].startswith("COV-")]
    check(got_rule_ids == rule_ids, f"{label}: one entry per rules control, in file order")
    for c in got:
        if c["id"].startswith("COV-"):
            g = c["id"][4:].lower()
            check(g in req_groups and c["group"] == g and c["required"] and c["blocking"]
                  and c["status"] == "UNVERIFIED", f"{label}: {c['id']} is a valid coverage entry")
            continue
        e = exp.get(c["id"])
        if e is None:
            continue
        check(c["group"] == e["group"] and c["blocking"] == e["blocking"],
              f"{label}: {c['id']} group/blocking copied from rules")
        if e["applicable"]:
            check(c["status"] != "NOT_APPLICABLE", f"{label}: {c['id']} is applicable, not NOT_APPLICABLE")
            check(c["required"] == e["required"], f"{label}: {c['id']} required flag")
        else:
            check(c["status"] == "NOT_APPLICABLE" and not c["required"],
                  f"{label}: {c['id']} is NOT_APPLICABLE for this profile/platform")
    for g in sorted(req_groups):
        has = any(c["group"] == g and c["required"] for c in got)
        check(has, f"{label}: required group {g} has a required control or COV entry")

    decision, critical, warnings = decide(got)
    check(doc["deployment_decision"] == decision, f"{label}: decision is {decision}")
    check(sorted(f["control"] for f in doc["critical_findings"]) == sorted(critical),
          f"{label}: critical_findings match rule 1/2 triggers")
    check(sorted(f["control"] for f in doc["non_blocking_findings"]) == sorted(warnings),
          f"{label}: non_blocking_findings match rule 3 triggers")
    check(doc["operational_readiness"] == sub_result(got, OPERATIONAL_GROUPS),
          f"{label}: operational_readiness")
    p = profile["profiles"][doc["deployment_profile"]]
    if (set(p["requires"]) | set(p["optional"])) & GOVERNANCE_GROUPS:
        check(doc["governance_conformance"] == sub_result(got, GOVERNANCE_GROUPS),
              f"{label}: governance_conformance")
    else:
        check(doc["governance_conformance"] == "NOT_APPLICABLE", f"{label}: governance_conformance")


# --------------------------------------------------------- 5. examples
def check_examples(schema, profile, rules) -> None:
    validator = jsonschema.Draft202012Validator(schema)
    valid = sorted(VALID_DIR.glob("*.json"))
    invalid = sorted(p for p in INVALID_DIR.glob("*.json") if p.name != MANIFEST.name)
    check(len(valid) >= 1, "at least one valid golden example")
    check(len(invalid) >= 1, "at least one invalid golden example")

    for path in valid:
        label = f"examples/valid/{path.name}"
        doc = load_json(path)
        if doc is None:
            continue
        errors = sorted(validator.iter_errors(doc), key=str)
        if not check(not errors, f"{label} validates against the schema"):
            for e in errors[:5]:
                print(f"      {list(e.absolute_path)}: {e.message}")
            continue
        check_semantics(doc, profile, rules, label)

    manifest = load_json(MANIFEST) or {}
    check(set(manifest) == {p.name for p in invalid},
          "examples/invalid/MANIFEST.json lists exactly the invalid examples")
    for path in invalid:
        label = f"examples/invalid/{path.name}"
        doc = load_json(path)
        if doc is None:
            continue
        errors = list(validator.iter_errors(doc))
        if not check(bool(errors), f"{label} is rejected by the schema"):
            continue
        expected = set(manifest.get(path.name, {}).get("expect_keywords", []))
        seen = set()
        stack = list(errors)
        while stack:
            e = stack.pop()
            seen.add(e.validator)
            stack.extend(e.context or [])
        check(bool(expected) and expected <= seen,
              f"{label} is rejected for the expected reason {sorted(expected)} (saw {sorted(seen)})")


def main() -> int:
    check_parse()
    schema, profile, rules = load_json(SCHEMA), load_json(PROFILE), load_json(RULES)
    if None in (schema, profile, rules):
        print(f"\n{len(failures)} failure(s); core files missing or unparsable")
        return 1
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        check(True, "schema is meta-valid")
    except jsonschema.SchemaError as exc:
        check(False, f"schema is not meta-valid: {exc.message}")
    for name, fn in (("SKILL.md checks", check_skill_md),
                     ("cross-file checks", lambda: check_cross_file(profile, rules, schema)),
                     ("example checks", lambda: check_examples(schema, profile, rules))):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - a malformed file must fail, not crash
            check(False, f"{name} could not complete: {type(exc).__name__}: {exc}")

    print(f"\n{passes} check(s) passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
