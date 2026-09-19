# NLMV manifest v0.1

A manifest has two top-level collections: the fixed `source_universe` and the explicit `dispositions` that account for those members.

## Minimal example

```json
{
  "schema_version": "0.1",
  "source_universe": [
    {"id": "SRC-001", "label": "Old guide A"},
    {"id": "SRC-002", "label": "Old guide B"},
    {"id": "SRC-003", "label": "Historical note"}
  ],
  "dispositions": [
    {
      "source_ids": ["SRC-001"],
      "status": "SUCCESSOR",
      "target_paths": ["docs/new-guide-a.md"]
    },
    {
      "source_ids": ["SRC-002"],
      "status": "PRESERVED",
      "target_paths": ["docs/old-guide-b.md"]
    },
    {
      "source_ids": ["SRC-003"],
      "status": "NOT_APPLICABLE",
      "reason": "Historical note intentionally excluded from the new guide set"
    }
  ]
}
```

## `source_universe`

`source_universe` is the closure population. NLMV never infers the population from the dispositions.

Each member requires:

- `id`: non-empty string, unique within the manifest.

Optional:

- `label`: human-readable description.
- `source_path`: source-side path metadata. v0.1 does not require that this path still exists.

## `dispositions`

Every source ID must appear across all dispositions **exactly once**.

Each disposition contains:

- `source_ids`: one or more source IDs from the fixed source universe.
- `status`: one allowed status.
- `target_paths`: required or forbidden depending on status.
- `relation`: required for non-1:1 `SUCCESSOR` mappings and for many-to-one `PRESERVED` mappings.
- `reason`: required for `NOT_APPLICABLE` and `INTENTIONAL_REMOVAL`.

### Statuses

#### `SUCCESSOR`

The source member or members have one or more declared successors. All target paths must exist under `--target-root`.

A 1-source/1-target mapping is `ONE_TO_ONE`; `relation` may be omitted or explicitly set to `ONE_TO_ONE`.

For other cardinalities, `relation` is mandatory:

```text
1 source, >1 targets -> ONE_TO_MANY
>1 sources, 1 target -> MANY_TO_ONE
>1 sources, >1 targets -> MANY_TO_MANY
```

A many-to-one or many-to-many mapping must be expressed in one disposition record. Sharing the same target path implicitly across separate disposition records is a closure failure.

#### `PRESERVED`

Requires one or more source IDs and exactly one existing target path.

- one source ID + one target path is `ONE_TO_ONE`; `relation` may be omitted or explicitly set to `ONE_TO_ONE`;
- multiple source IDs preserved within the same unchanged physical target require `relation: "MANY_TO_ONE"`.

This supports logical source members such as sections or heading units that remain intact inside one preserved document. `PRESERVED` does not support one-to-many targets; a split belongs under `SUCCESSOR`.

#### `NOT_APPLICABLE`

Requires a non-empty `reason`. `target_paths` and `relation` are forbidden.

#### `INTENTIONAL_REMOVAL`

Requires a non-empty `reason`. `target_paths` and `relation` are forbidden.

#### `UNRESOLVED`

Represents a still-open disposition. The manifest is structurally valid, but migration closure fails. `target_paths` and `relation` are forbidden.

## Governance and policy layers

NLMV's core PASS/FAIL result is intentionally narrower than repository governance.

For `NOT_APPLICABLE` and `INTENTIONAL_REMOVAL`, v0.1 requires a non-empty `reason`, but NLMV does not decide whether that reason is sufficiently justified, whether it references an approved issue, or whether the change received the right reviewer approval.

Teams that need stronger controls can layer repository policy around the manifest, for example:

- require an issue, PR, or ticket reference in `reason` for non-successor dispositions;
- use CODEOWNERS or branch-protection review rules for changes to the migration manifest;
- add non-blocking CI warnings when the proportion of non-successor dispositions is unexpectedly high.

Those controls are intentionally outside the deterministic core verifier because approval policy and acceptable thresholds vary by repository.

## Boundary examples

A successful accounting check does not prove content completeness or semantic preservation. For example, in a one-to-many split, all declared target files may exist while some source content was accidentally omitted during extraction. That remains outside v0.1's guarantee.

Likewise, target existence in v0.1 is defined against local filesystem artifacts under `--target-root`. Database records, headless CMS objects, dynamically served API routes, or targets that exist only after deployment are outside the current target model.

## Path safety

Target paths must be relative to `--target-root`.

NLMV rejects:

- POSIX absolute paths;
- Windows absolute paths, even when running on a non-Windows host;
- paths containing a parent escape (`..`);
- paths that resolve outside `--target-root`, including an existing symlink that escapes the root.

The v0.1 safety check is not a general filesystem sandbox and does not claim TOCTOU resistance against malicious concurrent filesystem mutation.

## Results and exit codes

`PASS` / exit `0` means every source member is accounted for exactly once, no member is unresolved, required targets exist, and no cross-record duplicate target mapping remains.

`FAIL` / exit `1` means the manifest is valid but closure is incomplete, such as missing disposition, duplicate disposition, unresolved member, broken target, or duplicate target mapping.

`INVALID` / exit `2` means the manifest or invocation violates the input contract, such as malformed JSON, schema errors, invalid relation/cardinality, missing required reason, or unsafe target path.

## What v0.1 does not prove

NLMV does not prove that a declared successor preserves the meaning, quality, or behavior of its source. Semantic equivalence remains a separate human or tool-assisted verification responsibility.
