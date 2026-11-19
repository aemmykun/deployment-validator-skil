# deployment-validator

An agent skill that checks whether a deployment is ready, using only the
artifacts you give it. It returns a JSON verdict of `READY`,
`READY_WITH_WARNINGS` or `NOT_READY`, with a PASS / FAIL / UNVERIFIED /
NOT_APPLICABLE result and cited evidence for every control.

It supports Docker Compose, Cloudflare Workers, Vercel and Firebase, and four
profiles: `minimal`, `application`, `platform` and `governed-platform`.

**Agents:** start at [`SKILL.md`](SKILL.md). All rules live there and in the
files it loads. This README only explains the repo to people.

## File map

| File | Purpose |
|------|---------|
| `SKILL.md` | Entry point: frontmatter, procedure, decision rules, prompt-injection guard |
| `validation.prompt.md` | Evaluator role and evidence handling |
| `validation.profile.json` | Profiles: required and optional control groups, decision policy |
| `validation.rules.json` | Control groups, platforms, evidence types and controls |
| `validation.schema.json` | JSON Schema the output must match; it also enforces the decision rules |
| `examples/valid/` | Golden outputs that must validate |
| `examples/invalid/` | Outputs the schema must reject; `MANIFEST.json` says why |
| `examples/invalid-semantic/` | Schema-valid outputs the rule check must reject |
| `tools/validate.py` | Offline checks for all of the above |

## Run the checks

```sh
python -m pip install -r requirements-dev.txt
python tools/validate.py                    # add -v to list every check
python tools/validate.py --result out.json  # check one emitted result
```

The script checks that:

- every JSON file parses
- the schema is meta-valid
- `SKILL.md` has frontmatter and every file it names exists
- profiles, rules and schema agree (every required group has a control)
- valid examples pass and match the reference decision engine
- invalid examples fail for the stated reason, and semantic-invalid ones fail
  the rule check (applicability, `required` flags, decision)

CI runs the same script on every push to `main` and on every pull request.

## License

MIT. See [LICENSE](LICENSE).
