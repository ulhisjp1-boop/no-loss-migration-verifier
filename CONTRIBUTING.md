# Contributing

Thanks for helping improve No-Loss Migration Verifier.

## Scope

The v0.1 project is deliberately small: deterministic local verification of a fixed source universe against explicit dispositions and target existence. Semantic equivalence, migration execution, LLM/API integration, GUI/cloud services, and agent orchestration are out of scope for v0.1 unless the project contract changes explicitly.

## Development setup

Requires Python 3.11 or newer.

```bash
python -m unittest discover -s tests -v
python nlmv.py verify examples/basic/manifest.json --target-root examples/basic/target
```

To exercise the installed CLI:

```bash
python -m pip install .
nlmv verify examples/basic/manifest.json --target-root examples/basic/target
```

## Pull requests

Please keep changes focused and include tests for behavior changes. Preserve exit-code semantics (`0` PASS, `1` valid-but-incomplete closure, `2` invalid input/usage) unless a versioned contract change explicitly revises them.

Do not submit real private migration manifests, credentials, private repository paths, proprietary source text, or other non-public data as fixtures. Use synthetic IDs and paths.
