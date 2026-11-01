"""Run the GeoChronos check suite and record exactly what happened.

For every step it stores: command, start/end time with time zone, duration,
exit code, stdout and stderr, plus the Python version. Output goes to a run
folder (default build/runs/<date>_manual/<label>/).

Usage:
  python scripts/run_suite.py --out build/runs/2026-10-01_night/baseline
  python scripts/run_suite.py --out <dir> --steps timefmt,build,validate,tests
"""
import argparse
import datetime as dt
import json
import pathlib
import platform
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STEPS = {
    "timefmt": [sys.executable, "scripts/timefmt.py"],
    "build": [sys.executable, "scripts/build_db.py", "--profile", "base"],
    "build-full": [sys.executable, "scripts/build_db.py", "--profile", "full"],
    "validate": [sys.executable, "scripts/validate.py"],
    "validate-expansion": [sys.executable, "scripts/validate_expansion.py"],
    "tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
}


def now():
    return dt.datetime.now().astimezone()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", default="timefmt,build,validate")
    args = ap.parse_args()
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
    log = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
           "cwd": str(ROOT), "steps": []}
    for name in args.steps.split(","):
        cmd = STEPS[name]
        t0 = now()
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        t1 = now()
        (out / f"{name}.stdout.txt").write_text(p.stdout, encoding="utf-8")
        (out / f"{name}.stderr.txt").write_text(p.stderr, encoding="utf-8")
        rec = {"step": name, "command": " ".join(cmd), "started": t0.isoformat(timespec="seconds"),
               "ended": t1.isoformat(timespec="seconds"), "tz": t0.tzname(),
               "seconds": round((t1 - t0).total_seconds(), 2), "exit_code": p.returncode}
        log["steps"].append(rec)
        print(f"{name:20s} exit={p.returncode} {rec['seconds']}s")
    for rel in ("build/base/build_report.md", "build/base/curation_queue_auto.csv", "build/build_report.md",
                "build/curation_queue_auto.csv", "build/validation_report.md", "build/validation_expansion_report.md"):
        src = ROOT / rel
        if src.exists():
            name = rel.replace("build/", "").replace("/", "_")
            (out / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "run_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.exit(max(s["exit_code"] for s in log["steps"]))


if __name__ == "__main__":
    main()
