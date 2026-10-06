from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

PATH_RE = re.compile(
    r"(?<![\w.-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:py|js|ts|tsx|jsx|java|cpp|cc|c|h|hpp|go|rs|rb|php|cs|kt|scala|md|json|yaml|yml|toml|xml)"
)
TEST_RE = re.compile(
    r"\b(pytest|unittest|nosetests|npm\s+test|yarn\s+test|pnpm\s+test|mvn\s+test|gradle\s+test|go\s+test|cargo\s+test|ctest|make\s+test)\b",
    re.IGNORECASE,
)
FAIL_RE = re.compile(r"\b(fail(?:ed|ure|ures)?|error|exception|traceback)\b", re.IGNORECASE)
PASS_RE = re.compile(r"\b(pass(?:ed|es)?|success(?:ful|fully)?|all tests)\b", re.IGNORECASE)
EDIT_RE = re.compile(
    r"\b(apply_patch|patch|edit|write|replace|sed\s+-i|cat\s+>|tee\s+|save)\b",
    re.IGNORECASE,
)


def _walk_strings(obj: Any) -> list[str]:
    """Collect textual leaves from the heterogeneous trajectory structure."""
    out: list[str] = []
    if obj is None:
        return out
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_walk_strings(k))
            out.extend(_walk_strings(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_walk_strings(v))
    else:
        out.append(str(obj))
    return out


def trajectory_text(trajectory: Any) -> str:
    return "\n".join(_walk_strings(trajectory))


def extract_signals(case: dict[str, Any]) -> dict[str, Any]:
    trajectory = case.get("trajectory") or []
    text_parts = _walk_strings(trajectory)
    text = "\n".join(text_parts)

    paths = PATH_RE.findall(text)
    path_counts = Counter(paths)
    top_paths = [p for p, _ in path_counts.most_common(12)]

    test_mentions = [s.strip()[:300] for s in text_parts if TEST_RE.search(s)]
    fail_mentions = sum(1 for s in text_parts if FAIL_RE.search(s))
    pass_mentions = sum(1 for s in text_parts if PASS_RE.search(s))

    edit_mentions = [s.strip()[:300] for s in text_parts if EDIT_RE.search(s)]
    repeated_paths = [p for p, count in path_counts.items() if count >= 3][:8]

    problem = (case.get("problem_statement") or "").strip()
    intent = problem[:900] + ("…" if len(problem) > 900 else "")

    return {
        "rationale": {
            "task_intent": intent,
            # Conservative: do not claim access to a true rationale.
            "observable_process_note": (
                "Use task intent plus observable action changes; this starter does not "
                "treat model reasoning text as ground-truth rationale."
            ),
        },
        "context": {
            "observed_paths": top_paths,
            "unique_path_count": len(set(paths)),
        },
        "validation": {
            "test_activity_examples": test_mentions[:8],
            "failure_like_observations": fail_mentions,
            "success_like_observations": pass_mentions,
        },
        "alternatives": {
            "repeated_or_revisited_paths": repeated_paths,
            "edit_activity_examples": edit_mentions[:8],
            "note": (
                "Repeated edits are only a proxy for rework/alternative attempts; "
                "manually inspect before claiming an alternative solution was tried."
            ),
        },
    }


def render_signal_block(signals: dict[str, Any], condition: str) -> str:
    def bullet(items: list[str]) -> str:
        if not items:
            return "- None observed in the extracted trace summary."
        return "\n".join(f"- {x}" for x in items)

    parts: list[str] = []

    if condition in ("rationale", "full"):
        r = signals["rationale"]
        parts.append(
            "### Task intent / rationale-related context\n"
            f"{r['task_intent']}\n\n"
            f"_Note: {r['observable_process_note']}_"
        )

    if condition in ("context", "full"):
        c = signals["context"]
        parts.append(
            "### Context explored by the coding agent\n"
            f"{bullet(c['observed_paths'])}\n\n"
            f"Unique path-like references observed: {c['unique_path_count']}"
        )

    if condition in ("validation", "full"):
        v = signals["validation"]
        parts.append(
            "### Validation activity observed\n"
            f"{bullet(v['test_activity_examples'])}\n\n"
            f"Failure-like observations in trace: {v['failure_like_observations']}\n"
            f"Success-like observations in trace: {v['success_like_observations']}"
        )

    if condition in ("alternatives", "full"):
        a = signals["alternatives"]
        parts.append(
            "### Rework / alternative-attempt signals\n"
            "Repeated/revisited paths:\n"
            f"{bullet(a['repeated_or_revisited_paths'])}\n\n"
            "Edit activity examples:\n"
            f"{bullet(a['edit_activity_examples'])}\n\n"
            f"_Note: {a['note']}_"
        )

    return "\n\n".join(parts).strip()
