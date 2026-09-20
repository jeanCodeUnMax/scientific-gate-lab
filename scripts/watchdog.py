from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

POLICY = ROOT / ".watchdog" / "policy.json"
TASK = ROOT / ".watchdog" / "active_task.json"
LOG_DIR = ROOT / ".watchdog" / "logs"


def run(*args: str) -> tuple[int, str]:
    """
    Execute a command from the repository root.

    Returns:
        (return_code, combined_output)
    """
    process = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    output = (process.stdout + process.stderr).strip()

    return process.returncode, output


def load(path: Path) -> dict:
    """
    Load a JSON file.
    """
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def gate(name: str, passed: bool, detail: str = "") -> dict:
    """
    Create one deterministic gate result.
    """
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def evaluate(mode: str) -> int:
    """
    Evaluate all Scientific Gate checks.

    Important:
    - normal repositories require a valid HEAD commit;
    - a missing HEAD is accepted only when the repository contains
      exactly zero commits, i.e. during the legitimate initial commit.
    """
    results: list[dict] = []

    # ------------------------------------------------------------
    # Gate: policy
    # ------------------------------------------------------------

    results.append(
        gate(
            "policy",
            POLICY.is_file(),
            str(POLICY),
        )
    )

    # ------------------------------------------------------------
    # Gate: active task
    # ------------------------------------------------------------

    results.append(
        gate(
            "active_task_file",
            TASK.is_file(),
            str(TASK),
        )
    )

    if not POLICY.is_file() or not TASK.is_file():
        return finish(mode, results)

    policy = load(POLICY)
    task = load(TASK)

    results.append(
        gate(
            "one_active_task",
            task.get("status") == "ACTIVE"
            and bool(task.get("id")),
            task.get("id", "missing"),
        )
    )

    # ------------------------------------------------------------
    # Gate: Git branch
    # ------------------------------------------------------------

    rc, branch = run(
        "git",
        "branch",
        "--show-current",
    )

    protected = set(
        policy.get(
            "protected_branches",
            [],
        )
    )

    branch_ok = (
        rc == 0
        and bool(branch)
        and branch not in protected
    )

    results.append(
        gate(
            "git_branch",
            branch_ok,
            branch or "unknown",
        )
    )

    # ------------------------------------------------------------
    # Gate: Git HEAD
    #
    # Normal repository:
    #     valid HEAD SHA required.
    #
    # Initial repository:
    #     HEAD may legitimately be unborn, but ONLY when Git proves
    #     that the repository contains zero commits.
    #
    # Any other failure remains FAIL.
    # ------------------------------------------------------------

    rc, head = run(
        "git",
        "rev-parse",
        "HEAD",
    )

    if rc == 0:
        results.append(
            gate(
                "git_head",
                True,
                head,
            )
        )

    else:
        rc_verify, _ = run(
            "git",
            "rev-parse",
            "--verify",
            "HEAD",
        )

        rc_count, commit_count = run(
            "git",
            "rev-list",
            "--count",
            "--all",
        )

        is_unborn_initial_commit = (
            rc_verify != 0
            and rc_count == 0
            and commit_count.strip() == "0"
        )

        if is_unborn_initial_commit:
            results.append(
                gate(
                    "git_head",
                    True,
                    "HEAD_UNBORN_INITIAL_COMMIT",
                )
            )

        else:
            results.append(
                gate(
                    "git_head",
                    False,
                    head or "HEAD_UNKNOWN",
                )
            )

    # ------------------------------------------------------------
    # Gate: staged files
    # ------------------------------------------------------------

    rc, staged = run(
        "git",
        "diff",
        "--cached",
        "--name-only",
    )

    if rc == 0:
        staged_files = [
            line
            for line in staged.splitlines()
            if line.strip()
        ]
    else:
        staged_files = []

    # ------------------------------------------------------------
    # Gate: forbidden staged patterns / secrets
    # ------------------------------------------------------------

    forbidden = policy.get(
        "forbidden_staged_patterns",
        [],
    )

    bad = [
        filename
        for filename in staged_files
        if any(
            pattern in filename
            for pattern in forbidden
        )
    ]

    results.append(
        gate(
            "staged_secrets",
            rc == 0 and not bad,
            ", ".join(bad)
            if bad
            else "none",
        )
    )

    # ------------------------------------------------------------
    # Gate: active-task scope
    # ------------------------------------------------------------

    allowed = task.get(
        "allowed_paths",
        [],
    )

    out_of_scope = [
        filename
        for filename in staged_files
        if not any(
            filename == allowed_path.rstrip("/")
            or filename.startswith(
                allowed_path.rstrip("/") + "/"
            )
            for allowed_path in allowed
        )
    ]

    results.append(
        gate(
            "staged_scope",
            not out_of_scope,
            ", ".join(out_of_scope)
            if out_of_scope
            else "in scope",
        )
    )

    # ------------------------------------------------------------
    # Gates: static checks + tests
    # ------------------------------------------------------------

    for label, key in (
        ("static_checks", "static_command"),
        ("tests", "test_command"),
    ):
        command = policy.get(
            key,
            [],
        )

        if not command:
            results.append(
                gate(
                    label,
                    False,
                    "command missing",
                )
            )
            continue

        process = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        detail = (
            process.stdout
            + process.stderr
        ).strip()[-3000:]

        results.append(
            gate(
                label,
                process.returncode == 0,
                detail,
            )
        )

    return finish(
        mode,
        results,
    )


def finish(
    mode: str,
    results: list[dict],
) -> int:
    """
    Persist the Watchdog decision and print the deterministic report.
    """
    decision = (
        "ALLOW"
        if all(
            result["status"] == "PASS"
            for result in results
        )
        else "DENY"
    )

    record = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "mode": mode,
        "decision": decision,
        "results": results,
    }

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        LOG_DIR
        / f"{mode}.jsonl"
    )

    with log_path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

    print()
    print("WATCHDOG")
    print("=" * 68)

    for result in results:
        print(
            f"{result['name']:<22} "
            f"{result['status']:<5} "
            f"{result['detail']}"
        )

    print("-" * 68)
    print(
        f"DECISION: {decision}"
    )

    if decision == "ALLOW":
        print(
            "Git operation ALLOWED."
        )
        return 0

    print(
        "Git operation BLOCKED."
    )
    return 1


def main() -> int:
    """
    CLI entry point.
    """
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/watchdog.py "
            "<pre-commit|pre-push>",
            file=sys.stderr,
        )
        return 2

    mode = sys.argv[1]

    if mode not in {
        "pre-commit",
        "pre-push",
    }:
        print(
            f"Unsupported watchdog mode: {mode}",
            file=sys.stderr,
        )
        return 2

    try:
        return evaluate(mode)

    except Exception as exc:
        # Fail closed:
        # an internal Watchdog failure must never silently authorize Git.
        print()
        print("WATCHDOG")
        print("=" * 68)
        print("internal_error         FAIL")
        print(
            f"{type(exc).__name__}: {exc}"
        )
        print("-" * 68)
        print("DECISION: DENY")
        print(
            "Git operation BLOCKED."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())