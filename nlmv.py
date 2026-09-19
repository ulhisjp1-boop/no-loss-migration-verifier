#!/usr/bin/env python3
"""No-Loss Migration Verifier v0.1 private G1 prototype.

Deterministically validates a fixed source universe against explicit migration
dispositions. This prototype is read-only: it never modifies the target tree.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

SCHEMA_VERSION = "0.1"
ALLOWED_STATUSES = {
    "SUCCESSOR",
    "PRESERVED",
    "NOT_APPLICABLE",
    "INTENTIONAL_REMOVAL",
    "UNRESOLVED",
}
ALLOWED_RELATIONS = {
    "ONE_TO_ONE",
    "ONE_TO_MANY",
    "MANY_TO_ONE",
    "MANY_TO_MANY",
}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    source_ids: tuple[str, ...] = ()
    target_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_ids"] = list(self.source_ids)
        data["target_paths"] = list(self.target_paths)
        return data


class InvalidManifest(Exception):
    def __init__(self, issues: Iterable[Issue]):
        self.issues = list(issues)
        super().__init__("Invalid manifest")


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_object(value: Any, where: str, issues: list[Issue]) -> bool:
    if not isinstance(value, dict):
        issues.append(Issue("INVALID_TYPE", f"{where} must be an object"))
        return False
    return True


def _require_list(value: Any, where: str, issues: list[Issue]) -> bool:
    if not isinstance(value, list):
        issues.append(Issue("INVALID_TYPE", f"{where} must be an array"))
        return False
    return True


def _safe_target(root: Path, raw: str) -> tuple[Path | None, Issue | None]:
    if not _is_nonempty_string(raw):
        return None, Issue("INVALID_TARGET_PATH", "target path must be a non-empty string")
    if PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute():
        return None, Issue("UNSAFE_TARGET_PATH", f"absolute target path is not allowed: {raw}", target_paths=(raw,))
    # Handle both slash conventions deterministically before touching the host Path implementation.
    posix_parts = PurePosixPath(raw.replace("\\", "/")).parts
    if ".." in posix_parts:
        return None, Issue("UNSAFE_TARGET_PATH", f"target path may not escape target root: {raw}", target_paths=(raw,))
    candidate = (root / Path(raw)).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        common = Path(os.path.commonpath([str(root_resolved), str(candidate)]))
    except ValueError:
        return None, Issue("UNSAFE_TARGET_PATH", f"target path is outside target root: {raw}", target_paths=(raw,))
    if common != root_resolved:
        return None, Issue("UNSAFE_TARGET_PATH", f"target path is outside target root: {raw}", target_paths=(raw,))
    return candidate, None


def _expected_relation(source_count: int, target_count: int) -> str:
    if source_count == 1 and target_count == 1:
        return "ONE_TO_ONE"
    if source_count == 1 and target_count > 1:
        return "ONE_TO_MANY"
    if source_count > 1 and target_count == 1:
        return "MANY_TO_ONE"
    return "MANY_TO_MANY"


def validate_manifest_shape(data: Any) -> dict[str, Any]:
    issues: list[Issue] = []
    if not _require_object(data, "manifest", issues):
        raise InvalidManifest(issues)

    if data.get("schema_version") != SCHEMA_VERSION:
        issues.append(Issue("INVALID_SCHEMA_VERSION", f"schema_version must be {SCHEMA_VERSION!r}"))

    source_universe = data.get("source_universe")
    dispositions = data.get("dispositions")
    if not _require_list(source_universe, "source_universe", issues):
        source_universe = []
    if not _require_list(dispositions, "dispositions", issues):
        dispositions = []

    if not source_universe:
        issues.append(Issue("EMPTY_SOURCE_UNIVERSE", "source_universe must not be empty"))

    source_ids: list[str] = []
    for i, member in enumerate(source_universe):
        if not _require_object(member, f"source_universe[{i}]", issues):
            continue
        sid = member.get("id")
        if not _is_nonempty_string(sid):
            issues.append(Issue("INVALID_SOURCE_ID", f"source_universe[{i}].id must be a non-empty string"))
            continue
        sid = sid.strip()
        source_ids.append(sid)

    dup_source_ids = sorted(k for k, v in Counter(source_ids).items() if v > 1)
    for sid in dup_source_ids:
        issues.append(Issue("DUPLICATE_SOURCE_ID", f"source_universe id appears more than once: {sid}", source_ids=(sid,)))

    universe = set(source_ids)

    normalized_dispositions: list[dict[str, Any]] = []
    for i, rec in enumerate(dispositions):
        if not _require_object(rec, f"dispositions[{i}]", issues):
            continue

        raw_ids = rec.get("source_ids")
        if not _require_list(raw_ids, f"dispositions[{i}].source_ids", issues):
            raw_ids = []
        ids: list[str] = []
        if not raw_ids:
            issues.append(Issue("EMPTY_SOURCE_IDS", f"dispositions[{i}].source_ids must contain at least one id"))
        for j, sid in enumerate(raw_ids):
            if not _is_nonempty_string(sid):
                issues.append(Issue("INVALID_SOURCE_REF", f"dispositions[{i}].source_ids[{j}] must be a non-empty string"))
                continue
            ids.append(sid.strip())
        if len(set(ids)) != len(ids):
            issues.append(Issue("DUPLICATE_SOURCE_IN_RECORD", f"dispositions[{i}] repeats a source id", source_ids=tuple(ids)))
        for sid in sorted(set(ids) - universe):
            issues.append(Issue("UNKNOWN_SOURCE_ID", f"dispositions[{i}] references unknown source id: {sid}", source_ids=(sid,)))

        status = rec.get("status")
        if status not in ALLOWED_STATUSES:
            issues.append(Issue("UNKNOWN_STATUS", f"dispositions[{i}].status is not allowed: {status!r}", source_ids=tuple(ids)))
            status = status if isinstance(status, str) else ""

        raw_targets = rec.get("target_paths", [])
        if not _require_list(raw_targets, f"dispositions[{i}].target_paths", issues):
            raw_targets = []
        targets: list[str] = []
        for j, target in enumerate(raw_targets):
            if not _is_nonempty_string(target):
                issues.append(Issue("INVALID_TARGET_PATH", f"dispositions[{i}].target_paths[{j}] must be a non-empty string", source_ids=tuple(ids)))
                continue
            targets.append(target.strip())
        if len(set(targets)) != len(targets):
            issues.append(Issue("DUPLICATE_TARGET_IN_RECORD", f"dispositions[{i}] repeats a target path", source_ids=tuple(ids), target_paths=tuple(targets)))

        relation = rec.get("relation")
        reason = rec.get("reason")

        if status == "SUCCESSOR":
            if not targets:
                issues.append(Issue("TARGET_REQUIRED", f"dispositions[{i}] SUCCESSOR requires target_paths", source_ids=tuple(ids)))
            if ids and targets:
                expected = _expected_relation(len(ids), len(targets))
                if expected == "ONE_TO_ONE":
                    if relation is not None and relation != "ONE_TO_ONE":
                        issues.append(Issue("RELATION_CARDINALITY_MISMATCH", f"dispositions[{i}] relation {relation!r} does not match ONE_TO_ONE cardinality", source_ids=tuple(ids), target_paths=tuple(targets)))
                else:
                    if relation is None:
                        issues.append(Issue("RELATION_REQUIRED", f"dispositions[{i}] non-1:1 SUCCESSOR requires relation={expected}", source_ids=tuple(ids), target_paths=tuple(targets)))
                    elif relation not in ALLOWED_RELATIONS:
                        issues.append(Issue("UNKNOWN_RELATION", f"dispositions[{i}].relation is not allowed: {relation!r}", source_ids=tuple(ids), target_paths=tuple(targets)))
                    elif relation != expected:
                        issues.append(Issue("RELATION_CARDINALITY_MISMATCH", f"dispositions[{i}] relation {relation!r} does not match {expected}", source_ids=tuple(ids), target_paths=tuple(targets)))
        elif status == "PRESERVED":
            if len(targets) != 1:
                issues.append(Issue("PRESERVED_CARDINALITY", f"dispositions[{i}] PRESERVED requires exactly one target_path", source_ids=tuple(ids), target_paths=tuple(targets)))
            elif ids:
                expected = _expected_relation(len(ids), 1)
                if expected == "ONE_TO_ONE":
                    if relation is not None and relation != "ONE_TO_ONE":
                        issues.append(Issue("RELATION_CARDINALITY_MISMATCH", f"dispositions[{i}] relation {relation!r} does not match ONE_TO_ONE cardinality", source_ids=tuple(ids), target_paths=tuple(targets)))
                else:
                    if relation is None:
                        issues.append(Issue("RELATION_REQUIRED", f"dispositions[{i}] many-to-one PRESERVED requires relation={expected}", source_ids=tuple(ids), target_paths=tuple(targets)))
                    elif relation not in ALLOWED_RELATIONS:
                        issues.append(Issue("UNKNOWN_RELATION", f"dispositions[{i}].relation is not allowed: {relation!r}", source_ids=tuple(ids), target_paths=tuple(targets)))
                    elif relation != expected:
                        issues.append(Issue("RELATION_CARDINALITY_MISMATCH", f"dispositions[{i}] relation {relation!r} does not match {expected}", source_ids=tuple(ids), target_paths=tuple(targets)))
        elif status in {"NOT_APPLICABLE", "INTENTIONAL_REMOVAL"}:
            if targets:
                issues.append(Issue("TARGET_FORBIDDEN", f"dispositions[{i}] {status} must not have target_paths", source_ids=tuple(ids), target_paths=tuple(targets)))
            if not _is_nonempty_string(reason):
                issues.append(Issue("REASON_REQUIRED", f"dispositions[{i}] {status} requires a non-empty reason", source_ids=tuple(ids)))
            if relation is not None:
                issues.append(Issue("RELATION_FORBIDDEN", f"dispositions[{i}] {status} must not have relation", source_ids=tuple(ids)))
        elif status == "UNRESOLVED":
            if targets:
                issues.append(Issue("TARGET_FORBIDDEN", f"dispositions[{i}] UNRESOLVED must not have target_paths", source_ids=tuple(ids), target_paths=tuple(targets)))
            if relation is not None:
                issues.append(Issue("RELATION_FORBIDDEN", f"dispositions[{i}] UNRESOLVED must not have relation", source_ids=tuple(ids)))

        normalized_dispositions.append(
            {
                "source_ids": ids,
                "status": status,
                "target_paths": targets,
                "relation": relation,
                "reason": reason,
                "index": i,
            }
        )

    if issues:
        raise InvalidManifest(issues)

    return {
        "schema_version": SCHEMA_VERSION,
        "source_ids": source_ids,
        "source_universe": source_universe,
        "dispositions": normalized_dispositions,
    }


def verify_manifest(data: Any, target_root: Path) -> dict[str, Any]:
    try:
        norm = validate_manifest_shape(data)
    except InvalidManifest as exc:
        return {
            "result": "INVALID",
            "summary": {
                "source_total": 0,
                "accounted_total": 0,
                "successor_total": 0,
                "preserved_total": 0,
                "not_applicable_total": 0,
                "intentional_removal_total": 0,
                "unresolved_total": 0,
                "missing_disposition_total": 0,
                "duplicate_source_total": 0,
                "broken_target_total": 0,
                "duplicate_target_total": 0,
            },
            "issues": [i.to_dict() for i in exc.issues],
        }

    source_ids: list[str] = norm["source_ids"]
    dispositions: list[dict[str, Any]] = norm["dispositions"]
    issues: list[Issue] = []

    occurrence: Counter[str] = Counter()
    source_status: dict[str, str] = {}
    target_records: defaultdict[str, list[int]] = defaultdict(list)

    status_source_counts = Counter()
    broken_targets: set[str] = set()
    unsafe_target_issues: list[Issue] = []

    for rec in dispositions:
        for sid in rec["source_ids"]:
            occurrence[sid] += 1
            source_status.setdefault(sid, rec["status"])
            status_source_counts[rec["status"]] += 1

        for raw in rec["target_paths"]:
            target_records[raw].append(rec["index"])
            candidate, path_issue = _safe_target(target_root, raw)
            if path_issue:
                unsafe_target_issues.append(
                    Issue(path_issue.code, path_issue.message, source_ids=tuple(rec["source_ids"]), target_paths=path_issue.target_paths)
                )
                continue
            assert candidate is not None
            if not candidate.exists():
                broken_targets.add(raw)
                issues.append(
                    Issue(
                        "BROKEN_TARGET",
                        f"target does not exist under target root: {raw}",
                        source_ids=tuple(rec["source_ids"]),
                        target_paths=(raw,),
                    )
                )

    if unsafe_target_issues:
        # Path-root violations are input/contract errors, not migration closure failures.
        return {
            "result": "INVALID",
            "summary": {
                "source_total": len(source_ids),
                "accounted_total": 0,
                "successor_total": status_source_counts["SUCCESSOR"],
                "preserved_total": status_source_counts["PRESERVED"],
                "not_applicable_total": status_source_counts["NOT_APPLICABLE"],
                "intentional_removal_total": status_source_counts["INTENTIONAL_REMOVAL"],
                "unresolved_total": status_source_counts["UNRESOLVED"],
                "missing_disposition_total": 0,
                "duplicate_source_total": 0,
                "broken_target_total": len(broken_targets),
                "duplicate_target_total": 0,
            },
            "issues": [i.to_dict() for i in unsafe_target_issues],
        }

    missing = sorted(sid for sid in source_ids if occurrence[sid] == 0)
    duplicate_sources = sorted(sid for sid in source_ids if occurrence[sid] > 1)

    for sid in missing:
        issues.append(Issue("MISSING_DISPOSITION", f"source member has no disposition: {sid}", source_ids=(sid,)))
    for sid in duplicate_sources:
        issues.append(Issue("DUPLICATE_DISPOSITION", f"source member appears in more than one disposition: {sid}", source_ids=(sid,)))

    unresolved_ids = sorted(
        sid
        for rec in dispositions
        if rec["status"] == "UNRESOLVED"
        for sid in rec["source_ids"]
    )
    for sid in unresolved_ids:
        issues.append(Issue("UNRESOLVED", f"source member is unresolved: {sid}", source_ids=(sid,)))

    duplicate_targets = sorted(
        target for target, indices in target_records.items()
        if len(set(indices)) > 1
    )
    for target in duplicate_targets:
        involved_sources = sorted({
            sid
            for rec in dispositions
            if target in rec["target_paths"]
            for sid in rec["source_ids"]
        })
        issues.append(
            Issue(
                "DUPLICATE_TARGET_MAPPING",
                f"target path is shared across separate disposition records: {target}",
                source_ids=tuple(involved_sources),
                target_paths=(target,),
            )
        )

    accounted = [
        sid
        for sid in source_ids
        if occurrence[sid] == 1 and source_status.get(sid) != "UNRESOLVED"
    ]

    summary = {
        "source_total": len(source_ids),
        "accounted_total": len(accounted),
        "successor_total": status_source_counts["SUCCESSOR"],
        "preserved_total": status_source_counts["PRESERVED"],
        "not_applicable_total": status_source_counts["NOT_APPLICABLE"],
        "intentional_removal_total": status_source_counts["INTENTIONAL_REMOVAL"],
        "unresolved_total": len(unresolved_ids),
        "missing_disposition_total": len(missing),
        "duplicate_source_total": len(duplicate_sources),
        "broken_target_total": len(broken_targets),
        "duplicate_target_total": len(duplicate_targets),
    }
    return {
        "result": "PASS" if not issues else "FAIL",
        "summary": summary,
        "issues": [i.to_dict() for i in issues],
    }


def load_manifest(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidManifest([Issue("MANIFEST_READ_ERROR", f"cannot read manifest: {exc}")]) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidManifest([Issue("JSON_PARSE_ERROR", f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")]) from exc


def render_human(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"result: {report['result']}",
        f"source_total: {s['source_total']}",
        f"accounted_total: {s['accounted_total']}",
        f"successor_total: {s['successor_total']}",
        f"preserved_total: {s['preserved_total']}",
        f"not_applicable_total: {s['not_applicable_total']}",
        f"intentional_removal_total: {s['intentional_removal_total']}",
        f"unresolved_total: {s['unresolved_total']}",
        f"missing_disposition_total: {s['missing_disposition_total']}",
        f"duplicate_source_total: {s['duplicate_source_total']}",
        f"broken_target_total: {s['broken_target_total']}",
        f"duplicate_target_total: {s['duplicate_target_total']}",
    ]
    if report["issues"]:
        lines.append("issues:")
        for issue in report["issues"]:
            refs = []
            if issue.get("source_ids"):
                refs.append("source_ids=" + ",".join(issue["source_ids"]))
            if issue.get("target_paths"):
                refs.append("target_paths=" + ",".join(issue["target_paths"]))
            suffix = f" ({'; '.join(refs)})" if refs else ""
            lines.append(f"- {issue['code']}: {issue['message']}{suffix}")
    return "\n".join(lines)


def _invalid_report(issues: Iterable[Issue]) -> dict[str, Any]:
    return {
        "result": "INVALID",
        "summary": {
            "source_total": 0,
            "accounted_total": 0,
            "successor_total": 0,
            "preserved_total": 0,
            "not_applicable_total": 0,
            "intentional_removal_total": 0,
            "unresolved_total": 0,
            "missing_disposition_total": 0,
            "duplicate_source_total": 0,
            "broken_target_total": 0,
            "duplicate_target_total": 0,
        },
        "issues": [i.to_dict() for i in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nlmv", description="Verify no-loss migration manifest closure.")
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify", help="verify a manifest")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--target-root", required=True, type=Path)
    verify.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args(argv)
    if args.command != "verify":
        return 2

    try:
        data = load_manifest(args.manifest)
    except InvalidManifest as exc:
        report = _invalid_report(exc.issues)
    else:
        report = verify_manifest(data, args.target_root)

    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_human(report))

    return {"PASS": 0, "FAIL": 1, "INVALID": 2}[report["result"]]


if __name__ == "__main__":
    sys.exit(main())
