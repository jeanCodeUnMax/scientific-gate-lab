from enum import Enum
from pathlib import Path
import json
import os
import tempfile


class State(str, Enum):
    PREFLIGHT = "PREFLIGHT"
    EDIT = "EDIT"
    STATIC = "STATIC"
    TEST = "TEST"
    EVIDENCE = "EVIDENCE"
    STAGE = "STAGE"
    COMMIT = "COMMIT"
    VERIFY = "VERIFY"
    DONE = "DONE"


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    DEFERRED = "DEFERRED"
    ESCALATED = "ESCALATED"


ORDER = list(State)

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".watchdog"
STATE_FILE = STATE_DIR / "task_state.json"


# Ces étapes ne peuvent PAS être sautées pour atteindre un commit.
HARD_GATES = {
    State.PREFLIGHT,
    State.EVIDENCE,
    State.STAGE,
    State.COMMIT,
    State.VERIFY,
}


class Gate:
    def __init__(self):
        self.index = 0
        self.history = []
        self.load()

    @property
    def expected(self):
        return ORDER[self.index]

    def load(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        if not STATE_FILE.exists():
            self.reset()
            return

        try:
            data = json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )

            index = data["index"]
            history = data.get("history", [])

            if not isinstance(index, int):
                raise ValueError("invalid index")

            if not 0 <= index < len(ORDER):
                raise ValueError("index outside state machine")

            if not isinstance(history, list):
                raise ValueError("invalid history")

            self.index = index
            self.history = history

        except Exception as exc:
            raise RuntimeError(
                f"WATCHDOG_STATE_INVALID: {exc}"
            )

    def save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": 2,
            "index": self.index,
            "current": self.expected.value,
            "history": self.history,
        }

        fd, temp_name = tempfile.mkstemp(
            prefix="task_state_",
            suffix=".tmp",
            dir=STATE_DIR,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_name, STATE_FILE)

        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def reset(self):
        self.index = 0
        self.history = []
        self.save()

    def action(self, requested, outcome=Outcome.PASS, reason=None):

        if requested != self.expected:
            return False, (
                f"DENY: INVALID_TRANSITION "
                f"expected={self.expected.value} "
                f"requested={requested.value}"
            )

        # DONE n'accepte qu'un PASS.
        if requested == State.DONE:
            if outcome != Outcome.PASS:
                return False, "DENY: DONE_REQUIRES_PASS"

            self.history.append({
                "step": requested.value,
                "outcome": outcome.value,
                "reason": reason,
            })

            self.save()
            return True, "PASS: TASK_COMPLETE"

        # Les gates critiques ne peuvent pas être sautés.
        if requested in HARD_GATES and outcome in {
            Outcome.BLOCKED,
            Outcome.NOT_APPLICABLE,
            Outcome.DEFERRED,
        }:
            return False, (
                f"DENY: HARD_GATE_CANNOT_BE_SKIPPED "
                f"step={requested.value}"
            )

        if outcome == Outcome.FAIL:
            self.history.append({
                "step": requested.value,
                "outcome": outcome.value,
                "reason": reason or "UNKNOWN",
            })

            self.save()

            return False, (
                f"FAIL: {requested.value} "
                f"RECORDED reason={reason or 'UNKNOWN'}"
            )

        if outcome == Outcome.ESCALATED:
            self.history.append({
                "step": requested.value,
                "outcome": outcome.value,
                "reason": reason or "UNKNOWN",
            })

            self.save()

            return False, (
                f"ESCALATED: {requested.value} "
                f"reason={reason or 'UNKNOWN'}"
            )

        # PASS / BLOCKED / N/A / DEFERRED autorisés ici.
        self.history.append({
            "step": requested.value,
            "outcome": outcome.value,
            "reason": reason,
        })

        self.index += 1
        self.save()

        return True, (
            f"{outcome.value}: {requested.value} "
            f"NEXT={self.expected.value}"
        )
