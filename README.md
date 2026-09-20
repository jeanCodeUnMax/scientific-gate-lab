# Scientific Gate Lab

Disposable laboratory for testing a mechanically enforced Git watchdog before any operator is allowed near a real scientific repository.

## Bootstrap

From this directory:

```powershell
git init
git checkout -b lab/watchdog-test
python scripts/install_watchdog.py
python scripts/watchdog.py check
```

The watchdog intentionally refuses protected branches (`main`, `master`) and blocks commit/push whenever a required gate fails.

## Philosophy

The local model is not trusted to remember discipline. Git hooks enforce it mechanically. The model may attempt an invalid operation; the expected result is that Git refuses it.

## Crash tests to perform later

1. Valid commit on lab branch.
2. Deliberately failing unit test -> commit must be blocked.
3. Stage a forbidden secret-like filename -> blocked.
4. Stage an out-of-scope file -> blocked.
5. Try commit on protected branch -> blocked.
6. Try push while a gate is red -> blocked.
7. Verify failures are logged and preserved.

Do not connect this lab to the Oscilloscope repository.
