# Security policy

## Supported version

Security fixes are currently targeted at the latest `0.1.x` release line while the project is in early development.

## Security posture

No-Loss Migration Verifier v0.1 is intentionally local and read-only:

- no network access;
- no telemetry;
- no credential or API-key use;
- no migration execution;
- no target-file writes;
- no target-file content inspection required by the current contract;
- target paths must remain under `--target-root` after path resolution.

Absolute paths, parent traversal, and resolved symlink escapes are rejected. This is a boundary check, not a general filesystem sandbox, and v0.1 does not claim TOCTOU resistance against malicious concurrent filesystem changes.

The manifest may itself contain sensitive labels or paths. NLMV does not transmit them, but terminal output and CI logs may expose values that you put in a manifest. Avoid secrets and use synthetic identifiers in public logs and fixtures.

## Reporting a vulnerability

When the public repository supports private vulnerability reporting, use its GitHub Security Advisory / private vulnerability reporting channel. Otherwise, open a minimal public issue that does not include exploit details or sensitive data and ask for a private contact route.
