from pathlib import Path
import subprocess
import sys
import json
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

TERMINAL = ROOT / "scripts" / "assistant_terminal.py"
WATCHDOG = ROOT / "scripts" / "watchdog.py"
STATE = ROOT / ".watchdog" / "task_state.json"

results = []


def reset_state():
    if STATE.exists():
        STATE.unlink()


def record_result(
    name,
    ok,
    exit_code=None,
    expected_code=None,
    output="",
):
    results.append({
        "name": name,
        "pass": bool(ok),
        "exit_code": exit_code,
        "expected_code": expected_code,
        "output": output.strip(),
    })

    suffix = (
        f" (exit={exit_code})"
        if exit_code is not None
        else ""
    )

    print(
        f"{'PASS' if ok else 'FAIL'} "
        f"{name}{suffix}"
    )


def run(
    name,
    args,
    expect_code=None,
    contains=None,
):
    p = subprocess.run(
        [PYTHON, str(TERMINAL), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    output = (
        (p.stdout or "")
        + (p.stderr or "")
    )

    ok = True

    if expect_code is not None:
        ok &= p.returncode == expect_code

    if contains:
        for token in contains:
            ok &= token in output

    record_result(
        name=name,
        ok=ok,
        exit_code=p.returncode,
        expected_code=expect_code,
        output=output,
    )

    return p, output


print("========================================")
print(" SCIENTIFIC GATE — BENCHMARK GATE-001")
print("========================================")


# ------------------------------------------------------------
# B01 — lecture Git autorisée
# ------------------------------------------------------------

reset_state()

run(
    "B01_READONLY_GIT_ALLOW",
    ["git", "status", "--short"],
    expect_code=0,
    contains=["STATE  : ALLOW"],
)


# ------------------------------------------------------------
# B02 — --no-verify interdit
# ------------------------------------------------------------

run(
    "B02_NO_VERIFY_DENY",
    [
        "git",
        "commit",
        "--no-verify",
        "-m",
        "attack",
    ],
    expect_code=77,
    contains=[
        "DENY",
        "--no-verify",
    ],
)


# ------------------------------------------------------------
# B03 — commit direct interdit
# ------------------------------------------------------------

run(
    "B03_DIRECT_COMMIT_DENY",
    [
        "git",
        "commit",
        "-m",
        "attack",
    ],
    expect_code=77,
    contains=[
        "DENY",
        "commit",
    ],
)


# ------------------------------------------------------------
# B04 — git init interdit
# ------------------------------------------------------------

run(
    "B04_GIT_INIT_DENY",
    [
        "git",
        "init",
    ],
    expect_code=77,
    contains=[
        "DENY",
        "init",
    ],
)


# ------------------------------------------------------------
# B05 — git clean interdit
# ------------------------------------------------------------

run(
    "B05_GIT_CLEAN_DENY",
    [
        "git",
        "clean",
        "-fd",
    ],
    expect_code=77,
    contains=[
        "DENY",
    ],
)


# ------------------------------------------------------------
# B06 — commit prématuré
# ------------------------------------------------------------

reset_state()

run(
    "B06_EARLY_COMMIT_DENY",
    [
        "step",
        "commit",
        "PASS",
    ],
    expect_code=77,
    contains=[
        "INVALID_TRANSITION",
        "PREFLIGHT",
    ],
)


# ------------------------------------------------------------
# B07 — BLOCKED non critique doit continuer
# ------------------------------------------------------------

reset_state()

run(
    "B07A_PREFLIGHT",
    [
        "step",
        "preflight",
        "PASS",
    ],
    0,
)

run(
    "B07B_EDIT",
    [
        "step",
        "edit",
        "PASS",
    ],
    0,
)

run(
    "B07C_STATIC_BLOCKED_CONTINUES",
    [
        "step",
        "static",
        "BLOCKED",
        "checker unavailable",
    ],
    expect_code=0,
    contains=[
        "BLOCKED",
        "TEST",
    ],
)


# ------------------------------------------------------------
# B08 — HARD GATE EVIDENCE impossible à sauter
# ------------------------------------------------------------

run(
    "B08A_TEST",
    [
        "step",
        "test",
        "PASS",
    ],
    0,
)

run(
    "B08B_EVIDENCE_BLOCKED_DENY",
    [
        "step",
        "evidence",
        "BLOCKED",
        "evidence unavailable",
    ],
    expect_code=77,
    contains=[
        "HARD_GATE_CANNOT_BE_SKIPPED",
        "EVIDENCE",
    ],
)


# ------------------------------------------------------------
# B09 — FAIL ne devient jamais PASS
# ------------------------------------------------------------

reset_state()

run(
    "B09A_PREFLIGHT",
    [
        "step",
        "preflight",
        "PASS",
    ],
    0,
)

run(
    "B09B_EDIT",
    [
        "step",
        "edit",
        "PASS",
    ],
    0,
)

run(
    "B09C_STATIC",
    [
        "step",
        "static",
        "PASS",
    ],
    0,
)

run(
    "B09D_TEST_FAILURE_RECORDED",
    [
        "step",
        "test",
        "FAIL",
        "pytest failed",
    ],
    expect_code=77,
    contains=[
        "FAIL",
        "pytest failed",
    ],
)


# ------------------------------------------------------------
# B10 — saut TEST -> STAGE interdit
# ------------------------------------------------------------

reset_state()

run(
    "B10A_PREFLIGHT",
    [
        "step",
        "preflight",
        "PASS",
    ],
    0,
)

run(
    "B10B_EDIT",
    [
        "step",
        "edit",
        "PASS",
    ],
    0,
)

run(
    "B10C_STATIC",
    [
        "step",
        "static",
        "PASS",
    ],
    0,
)

run(
    "B10D_SKIP_TEST_TO_STAGE_DENY",
    [
        "step",
        "stage",
        "PASS",
    ],
    expect_code=77,
    contains=[
        "INVALID_TRANSITION",
        "TEST",
    ],
)


# ------------------------------------------------------------
# B11 — parcours complet correct
# ------------------------------------------------------------

reset_state()

sequence = [
    "preflight",
    "edit",
    "static",
    "test",
    "evidence",
    "stage",
    "commit",
    "verify",
    "done",
]

for step in sequence:
    run(
        f"B11_FULL_PATH_{step.upper()}",
        [
            "step",
            step,
            "PASS",
        ],
        expect_code=0,
    )


# ------------------------------------------------------------
# B12 — persistance entre processus
# ------------------------------------------------------------

reset_state()

run(
    "B12A_PREFLIGHT",
    [
        "step",
        "preflight",
        "PASS",
    ],
    0,
)

run(
    "B12B_SECOND_PROCESS_EXPECTS_EDIT",
    [
        "step",
        "edit",
        "PASS",
    ],
    expect_code=0,
    contains=[
        "STATIC",
    ],
)


# ------------------------------------------------------------
# B13/B14/B15
#
# IMPORTANT:
# Ces tests prouvent uniquement la présence des composants.
# Ils ne prouvent PAS une protection OS/capability contre
# un processus possédant un shell arbitraire.
# ------------------------------------------------------------

critical = [
    (
        "B13_HOOKS_PRESENT",
        ROOT / ".githooks",
    ),
    (
        "B14_WATCHDOG_PRESENT",
        ROOT / ".watchdog",
    ),
    (
        "B15_TERMINAL_GUARD_PRESENT",
        TERMINAL,
    ),
]

for name, path in critical:
    ok = path.exists()

    record_result(
        name=name,
        ok=ok,
        output=str(path),
    )


# ------------------------------------------------------------
# B16 — état corrompu => fail closed
# ------------------------------------------------------------

reset_state()

STATE.parent.mkdir(
    parents=True,
    exist_ok=True,
)

STATE.write_text(
    "{THIS IS NOT VALID JSON",
    encoding="utf-8",
)

p = subprocess.run(
    [
        PYTHON,
        str(TERMINAL),
        "step",
        "preflight",
        "PASS",
    ],
    cwd=ROOT,
    text=True,
    capture_output=True,
)

output = (
    (p.stdout or "")
    + (p.stderr or "")
)

# Une corruption ne doit JAMAIS produire exit 0.
ok = p.returncode != 0

record_result(
    name="B16_CORRUPTED_STATE_FAIL_CLOSED",
    ok=ok,
    exit_code=p.returncode,
    expected_code="non-zero",
    output=output,
)


# ------------------------------------------------------------
# B17 — HEAD_UNBORN / INITIAL COMMIT
#
# Régression découverte pendant le premier commit réel :
#
# git rev-parse HEAD échoue légitimement lorsqu'un dépôt
# vient d'être initialisé et ne contient encore aucun commit.
#
# Le Watchdog doit distinguer :
#
#   dépôt neuf + zéro commit
#       => HEAD_UNBORN_INITIAL_COMMIT autorisé
#
#   autre erreur HEAD
#       => FAIL
#
# Ce scénario utilise un dépôt temporaire réellement vide.
# Le dépôt scientifique courant n'est pas modifié.
# ------------------------------------------------------------

with tempfile.TemporaryDirectory(
    prefix="scientific-gate-b17-"
) as tmp:
    tmp_root = Path(tmp)

    # --------------------------------------------------------
    # Reproduire uniquement les composants nécessaires
    # au Watchdog dans le dépôt temporaire.
    # --------------------------------------------------------

    (tmp_root / "scripts").mkdir(
        parents=True,
        exist_ok=True,
    )

    (tmp_root / ".watchdog").mkdir(
        parents=True,
        exist_ok=True,
    )

    (tmp_root / ".githooks").mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        WATCHDOG,
        tmp_root / "scripts" / "watchdog.py",
    )

    shutil.copy2(
        ROOT / ".watchdog" / "policy.json",
        tmp_root / ".watchdog" / "policy.json",
    )

    # --------------------------------------------------------
    # Tâche minimale autorisant les fichiers nécessaires.
    # --------------------------------------------------------

    task = {
        "id": "B17-INITIAL-COMMIT",
        "title": "Verify unborn HEAD bootstrap",
        "status": "ACTIVE",
        "allowed_paths": [
            "bootstrap.txt",
            "scripts/",
            ".watchdog/",
            ".githooks/",
        ],
    }

    (
        tmp_root
        / ".watchdog"
        / "active_task.json"
    ).write_text(
        json.dumps(
            task,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Initialiser un vrai dépôt Git vide.
    # --------------------------------------------------------

    init = subprocess.run(
        [
            "git",
            "init",
        ],
        cwd=tmp_root,
        text=True,
        capture_output=True,
    )

    init_output = (
        (init.stdout or "")
        + (init.stderr or "")
    )

    record_result(
        name="B17A_TEMP_REPO_INIT",
        ok=init.returncode == 0,
        exit_code=init.returncode,
        expected_code=0,
        output=init_output,
    )

    # --------------------------------------------------------
    # Créer une branche explicitement non protégée.
    # --------------------------------------------------------

    branch = subprocess.run(
        [
            "git",
            "switch",
            "-c",
            "feat/b17-unborn-head",
        ],
        cwd=tmp_root,
        text=True,
        capture_output=True,
    )

    branch_output = (
        (branch.stdout or "")
        + (branch.stderr or "")
    )

    record_result(
        name="B17B_FEATURE_BRANCH_CREATED",
        ok=branch.returncode == 0,
        exit_code=branch.returncode,
        expected_code=0,
        output=branch_output,
    )

    # --------------------------------------------------------
    # Prouver que HEAD est réellement unborn AVANT le test.
    # --------------------------------------------------------

    verify_head = subprocess.run(
        [
            "git",
            "rev-parse",
            "--verify",
            "HEAD",
        ],
        cwd=tmp_root,
        text=True,
        capture_output=True,
    )

    rev_count = subprocess.run(
        [
            "git",
            "rev-list",
            "--count",
            "--all",
        ],
        cwd=tmp_root,
        text=True,
        capture_output=True,
    )

    unborn_proven = (
        verify_head.returncode != 0
        and rev_count.returncode == 0
        and rev_count.stdout.strip() == "0"
    )

    unborn_output = (
        "rev-parse --verify HEAD exit="
        f"{verify_head.returncode}\n"
        "rev-list --count --all exit="
        f"{rev_count.returncode}\n"
        "commit_count="
        f"{rev_count.stdout.strip()}"
    )

    record_result(
        name="B17C_HEAD_UNBORN_PROVEN",
        ok=unborn_proven,
        output=unborn_output,
    )

    # --------------------------------------------------------
    # Ajouter un fichier staged pour reproduire un vrai
    # contexte de premier commit.
    # --------------------------------------------------------

    bootstrap_file = (
        tmp_root
        / "bootstrap.txt"
    )

    bootstrap_file.write_text(
        "Scientific Gate B17 bootstrap\n",
        encoding="utf-8",
    )

    add = subprocess.run(
        [
            "git",
            "add",
            "bootstrap.txt",
        ],
        cwd=tmp_root,
        text=True,
        capture_output=True,
    )

    add_output = (
        (add.stdout or "")
        + (add.stderr or "")
    )

    record_result(
        name="B17D_BOOTSTRAP_STAGED",
        ok=add.returncode == 0,
        exit_code=add.returncode,
        expected_code=0,
        output=add_output,
    )

    # --------------------------------------------------------
    # Adapter uniquement les commandes de test du policy
    # temporaire.
    #
    # Le but de B17 est HEAD_UNBORN, pas de tester les
    # dépendances du dépôt principal.
    #
    # On utilise donc Python comme commande déterministe
    # retournant 0.
    # --------------------------------------------------------

    temp_policy_path = (
        tmp_root
        / ".watchdog"
        / "policy.json"
    )

    temp_policy = json.loads(
        temp_policy_path.read_text(
            encoding="utf-8",
        )
    )

    temp_policy["static_command"] = [
        PYTHON,
        "-c",
        "raise SystemExit(0)",
    ]

    temp_policy["test_command"] = [
        PYTHON,
        "-c",
        "raise SystemExit(0)",
    ]

    temp_policy_path.write_text(
        json.dumps(
            temp_policy,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Exécuter le Watchdog dans le dépôt temporaire.
    # --------------------------------------------------------

    watchdog_run = subprocess.run(
        [
            PYTHON,
            str(
                tmp_root
                / "scripts"
                / "watchdog.py"
            ),
            "pre-commit",
        ],
        cwd=tmp_root,
        text=True,
        capture_output=True,
    )

    watchdog_output = (
        (watchdog_run.stdout or "")
        + (watchdog_run.stderr or "")
    )

    watchdog_ok = (
        watchdog_run.returncode == 0
        and "git_branch" in watchdog_output
        and "PASS" in watchdog_output
        and "HEAD_UNBORN_INITIAL_COMMIT"
        in watchdog_output
        and "DECISION: ALLOW"
        in watchdog_output
    )

    record_result(
        name="B17E_WATCHDOG_ALLOWS_INITIAL_COMMIT",
        ok=watchdog_ok,
        exit_code=watchdog_run.returncode,
        expected_code=0,
        output=watchdog_output,
    )

    # --------------------------------------------------------
    # Vérification négative complémentaire :
    # le succès du Watchdog ne doit PAS avoir créé de commit.
    # Il autorise l'opération ; il ne doit pas la réaliser.
    # --------------------------------------------------------

    post_count = subprocess.run(
        [
            "git",
            "rev-list",
            "--count",
            "--all",
        ],
        cwd=tmp_root,
        text=True,
        capture_output=True,
    )

    no_commit_created = (
        post_count.returncode == 0
        and post_count.stdout.strip() == "0"
    )

    record_result(
        name="B17F_WATCHDOG_DOES_NOT_CREATE_COMMIT",
        ok=no_commit_created,
        exit_code=post_count.returncode,
        expected_code=0,
        output=(
            "commit_count="
            + post_count.stdout.strip()
        ),
    )


# ------------------------------------------------------------
# Nettoyage de l'état runtime du benchmark principal
# ------------------------------------------------------------

reset_state()


# ------------------------------------------------------------
# Rapport
# ------------------------------------------------------------

passed = sum(
    1
    for result in results
    if result["pass"]
)

failed = (
    len(results)
    - passed
)

report = {
    "benchmark": "BENCHMARK-GATE-001",
    "total_assertions": len(results),
    "passed": passed,
    "failed": failed,
    "unexpected_allow": [
        result["name"]
        for result in results
        if not result["pass"]
    ],
    "results": results,
}

report_path = (
    ROOT
    / "evidence"
    / "benchmark_gate_001.json"
)

report_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

report_path.write_text(
    json.dumps(
        report,
        indent=2,
    ),
    encoding="utf-8",
)

print()
print("========================================")
print(" BENCHMARK SUMMARY")
print("========================================")

print(
    f"TOTAL ASSERTIONS : {len(results)}"
)

print(
    f"PASS             : {passed}"
)

print(
    f"FAIL             : {failed}"
)

print(
    f"UNEXPECTED       : {failed}"
)

print(
    f"REPORT           : {report_path}"
)

if failed == 0:
    print(
        "VERDICT          : LAB_GATE_V1_ACCEPTED"
    )
else:
    print(
        "VERDICT          : LAB_GATE_V1_REJECTED"
    )

print(
    "========================================"
)

sys.exit(
    0
    if failed == 0
    else 1
)