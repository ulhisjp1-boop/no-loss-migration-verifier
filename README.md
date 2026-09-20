# No-Loss Migration Verifier

A large repository, documentation, or knowledge-base reorganization can finish with every test green while one original item was never moved, preserved, or intentionally retired.

No-Loss Migration Verifier (`nlmv`) is a small, deterministic, read-only CLI that checks a **fixed source universe** before merge: every source member must be accounted for exactly once, and every declared target must exist.

> **Scope:** NLMV verifies migration accounting and target existence. It does **not** prove content completeness or semantic equivalence between a source item and its successor.

Runtime properties:

- Python 3.11+
- Python standard library only
- no network calls, telemetry, credentials, or LLM/API dependency
- no target mutation

## Why not just rely on tests?

Tests usually answer questions about the **new** state: does the reorganized repository build, render, or behave correctly?

NLMV asks a different question about the **old** population:

> What happened to every source item that existed before the migration?

Those checks are complementary. A migration can have valid targets and passing tests while a source member is still missing from the migration accounting.

## See it catch a missing item

From a fresh clone:

```bash
git clone https://github.com/ulhisjp1-boop/no-loss-migration-verifier.git
cd no-loss-migration-verifier
python -m pip install .
```

Run the intentionally incomplete example:

```bash
nlmv verify examples/failure/missing-disposition.json --target-root examples/basic/target
```

The command intentionally exits with status `1`. Key output:

```text
result: FAIL
source_total: 3
accounted_total: 2
missing_disposition_total: 1
```

Now run the complete example:

```bash
nlmv verify examples/basic/manifest.json --target-root examples/basic/target
```

Expected result:

```text
result: PASS
source_total: 3
accounted_total: 3
```

For machine-readable output:

```bash
nlmv verify examples/basic/manifest.json --target-root examples/basic/target --json
```

## Is NLMV a fit for this migration?

NLMV is useful when:

- you are reorganizing many repository files, docs, knowledge-base entries, sections, or other stable logical source members;
- files may be split, merged, preserved, intentionally removed, or declared not applicable;
- existing tests can validate the new state but do not prove that every original source member was accounted for;
- you want a deterministic pre-merge/local/CI closure check.

NLMV is intentionally **not**:

- a semantic-equivalence checker;
- an automatic migration tool;
- an automatic source-universe discovery tool;
- a database, cloud-resource, CMS-object, or post-deployment target verifier in v0.1.

## Apply it to a real migration

A practical workflow is:

1. **Freeze the source universe before migration.** Give every source member a stable ID. A member can be a file, document, section, heading, or another logical unit you need to account for.
2. **Record undecided members as `UNRESOLVED`.** The manifest remains valid, but closure fails while any unresolved members remain.
3. **Replace each unresolved disposition as decisions are made** with `SUCCESSOR`, `PRESERVED`, `NOT_APPLICABLE`, or `INTENTIONAL_REMOVAL`.
4. **Run NLMV before merge/final integration.** PASS requires exactly-once accounting, zero unresolved members, and all required local targets to exist.

See [docs/manifest-v0.1.md](docs/manifest-v0.1.md) for the complete manifest contract, relation rules, governance boundary, and examples.

## Run it in CI

Until package-registry publication is intentionally enabled, a workflow can install an exact GitHub release directly:

```yaml
- name: Install NLMV
  run: python -m pip install "git+https://github.com/ulhisjp1-boop/no-loss-migration-verifier.git@v0.1.1"

- name: Verify migration closure
  run: nlmv verify migration-manifest.json --target-root .
```

Pinning the exact release tag keeps the CI behavior explicit. If your environment requires stronger supply-chain pinning, use the exact release commit SHA instead.

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

`PRESERVED` supports one logical source to one target and explicit many-to-one preservation when multiple logical source members remain intact inside one unchanged physical target.

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
