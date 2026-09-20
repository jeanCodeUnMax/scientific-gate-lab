import sys
import subprocess
import shlex
from state_gate import Gate, State, Outcome

DENIED_TOKENS = {
    "--no-verify", "--force", "--force-with-lease",
    "-f", "--hard", "-fd", "-fdx", "--amend",
}

DENIED_GIT_COMMANDS = {"init", "clean", "rebase"}

READ_ONLY_GIT = {
    "status", "diff", "rev-parse", "branch", "log", "show",
}

ACTION_TO_STATE = {
    "preflight": State.PREFLIGHT,
    "edit": State.EDIT,
    "static": State.STATIC,
    "test": State.TEST,
    "evidence": State.EVIDENCE,
    "stage": State.STAGE,
    "commit": State.COMMIT,
    "verify": State.VERIFY,
    "done": State.DONE,
}


def gate():
    return Gate()


def deny(reason, g=None):
    print("\n=== SCIENTIFIC GATE ===")
    print("MODE   : ASSISTANT")
    print("STATE  : DENY")
    print(f"REASON : {reason}")
    print("ACTION : NOT EXECUTED")
    if g:
        print(f"NEXT   : {g.expected.value}")
    raise SystemExit(77)


def run_git(args):
    g = gate()

    for arg in args[1:]:
        if arg.lower() in DENIED_TOKENS:
            deny(f"Forbidden argument: {arg}", g)

    if len(args) < 2:
        deny("Missing git subcommand", g)

    cmd = args[1].lower()

    if cmd in DENIED_GIT_COMMANDS:
        deny(f"Forbidden git command: {cmd}", g)

    if cmd not in READ_ONLY_GIT:
        deny(f"Direct git command not allowlisted: {cmd}", g)

    print("STATE  : ALLOW")
    print("COMMAND:", shlex.join(args))
    raise SystemExit(subprocess.run(args).returncode)


def run_step(args):
    if len(args) < 2:
        deny("Missing step")

    g = gate()

    name = args[1].lower()

    if name not in ACTION_TO_STATE:
        deny(f"Unknown step: {name}", g)

    try:
        outcome = Outcome(args[2].upper()) if len(args) >= 3 else Outcome.PASS
    except ValueError:
        deny(f"Unknown outcome: {args[2]}", g)

    reason = " ".join(args[3:]) if len(args) >= 4 else None

    ok, message = g.action(
        ACTION_TO_STATE[name],
        outcome,
        reason,
    )

    print("\n=== SCIENTIFIC GATE ===")
    print("MODE    : ASSISTANT")
    print(f"RESULT  : {message}")
    print(f"NEXT    : {g.expected.value}")

    raise SystemExit(0 if ok else 77)


def main():
    if len(sys.argv) < 2:
        deny("No command supplied")

    args = sys.argv[1:]

    if args[0].lower() == "git":
        run_git(args)

    if args[0].lower() == "step":
        run_step(args)

    deny("Direct command not allowlisted")


if __name__ == "__main__":
    main()
