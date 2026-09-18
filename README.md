# No-Loss Migration Verifier

No-Loss Migration Verifier (`nlmv`) is a small, deterministic, read-only CLI for checking that every member of a fixed migration source universe is explicitly accounted for and that declared successor targets exist.

> **Scope:** NLMV verifies migration accounting and target existence. It does **not** prove semantic equivalence between a source item and its successor.

## Quick start

Requires Python 3.11 or newer.

From a fresh clone:

```bash
git clone https://github.com/ulhisjp1-boop/no-loss-migration-verifier.git
cd no-loss-migration-verifier
python -m pip install .
nlmv verify examples/basic/manifest.json --target-root examples/basic/target
```

Expected result:

```text
result: PASS
source_total: 3
accounted_total: 3
```

You can also run directly from source without installing:

```bash
python nlmv.py verify examples/basic/manifest.json --target-root examples/basic/target
```

For machine-readable output:

```bash
nlmv verify examples/basic/manifest.json --target-root examples/basic/target --json
```

## What it checks

NLMV keeps the fixed source population separate from the migration dispositions. Each source ID must be accounted for exactly once.

Supported dispositions:

- `SUCCESSOR` — replaced by one or more target paths.
- `PRESERVED` — retained as one existing target path.
- `NOT_APPLICABLE` — intentionally outside the new target set; requires a reason.
- `INTENTIONAL_REMOVAL` — intentionally removed; requires a reason.
- `UNRESOLVED` — accepted as manifest input but causes closure to fail.

Explicit non-1:1 successor relations:

- `ONE_TO_MANY`
- `MANY_TO_ONE`
- `MANY_TO_MANY`

A 1:1 `SUCCESSOR` relation may omit `relation` and is treated as `ONE_TO_ONE`.

See [docs/manifest-v0.1.md](docs/manifest-v0.1.md) for the complete v0.1 contract.

## Exit codes

```text
0 = PASS — migration accounting is closed
1 = FAIL — manifest is valid, but migration closure is incomplete
2 = INVALID — input, schema, path-safety, or usage error
```

## Why use it?

Tests can pass while a large documentation, repository, or knowledge-base reorganization still loses an item, accounts for one item twice, leaves a disposition unresolved, or points to a missing successor. NLMV makes the source population explicit and turns those closure failures into deterministic CLI output suitable for human review or CI.

## Read-only and privacy posture

NLMV does not perform migrations, modify targets, make network requests, send telemetry, or use credentials. It checks metadata from the manifest plus target-path existence under the supplied `--target-root`.

The manifest itself may contain sensitive labels or paths. NLMV does not upload them, but your own terminal logs and CI logs remain your responsibility. Use synthetic or non-sensitive identifiers in public fixtures.

## Feedback and issues

Usage questions, documentation friction, compatibility problems, suspected false PASS results, and material false FAIL results are useful feedback. Please open a GitHub issue with the exact command, exit code, and a minimal reproduction when possible.

Do **not** post private manifests, credentials, secrets, sensitive repository URLs, proprietary source content, or sensitive absolute paths. Prefer synthetic or redacted identifiers. For security-sensitive reports, follow [SECURITY.md](SECURITY.md) instead of posting details publicly.

## Development

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

The project intentionally stays small: Python standard library only at runtime, a single implementation module, and no LLM/API dependency.

## License

MIT. See [LICENSE](LICENSE).
