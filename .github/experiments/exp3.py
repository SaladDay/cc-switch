"""Disposable interleaved A/B for fork CI only.
A = unchanged main; D = A + [profile.dev.package."*"] debug = false (dependencies only;
the cc-switch crate keeps its own debug = "line-tables-only"). Order A D D A, own target dir per arm."""
import json, os, pathlib, re, shutil, subprocess, sys, time

ARMS = os.environ["ARMS"].split(","); ORDER = [ARMS[0], ARMS[1], ARMS[1], ARMS[0]]
ROOT = pathlib.Path.cwd(); OUT = ROOT / "experiment-results"; OUT.mkdir(exist_ok=True)
MANIFEST = ROOT / "src-tauri/Cargo.toml"; ORIGINAL = MANIFEST.read_text(encoding="utf-8")
DEPS_NO_DEBUG = ORIGINAL + '\n[profile.dev.package."*"]\ndebug = false\n'
CARGO = shutil.which("cargo"); BASE = ["--manifest-path", "src-tauri/Cargo.toml", "--locked"]
R = {"arms": ARMS, "order": ORDER, "cpu_count": os.cpu_count(), "platform": sys.platform, "steps": []}
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
NAME = re.compile(r"^\s+(PASS|FAIL) \[\s*([\d.]+)s\]\s+\(\s*\d+/\d+\)\s+(.+?)\s*$", re.M)

def save(): (OUT / "results.json").write_text(json.dumps(R, indent=2), encoding="utf-8")
def target(arm): return ROOT / f"target-{arm}"
def use_manifest(arm): MANIFEST.write_text(DEPS_NO_DEBUG if arm == "D" else ORIGINAL, encoding="utf-8", newline="")

def reset_leaked_state():
    # Windows: services::provider tests write %LOCALAPPDATA%\hermes (not isolated); a fresh CI
    # runner never has it, so remove it before each phase to keep phases equivalent.
    la = os.environ.get("LOCALAPPDATA")
    if la and (pathlib.Path(la) / "hermes").exists():
        shutil.rmtree(pathlib.Path(la) / "hermes"); print("removed leaked LOCALAPPDATA/hermes", flush=True)

def parse(text):
    d = {}
    m = re.findall(r"Finished `test` profile.* in (?:(\d+)m )?([\d.]+)s", text)
    if m: d["compile_s"] = float(m[-1][0] or 0) * 60 + float(m[-1][1])
    m = re.search(r"Summary\s+\[\s*([\d.]+)s\]\s+(\d+) tests run: (\d+) passed", text)
    if m: d.update(exec_s=float(m[1]), run=int(m[2]), passed=int(m[3]))
    tests = [(st, float(t), n) for st, t, n in NAME.findall(text)]
    d["failed"] = sorted({n for st, _, n in tests if st == "FAIL"})
    d["names"] = sorted({n for _, _, n in tests})
    first = {}
    for st, t, n in tests: first.setdefault(n, t)
    d["all_proc_s"] = sum(first.values())
    d["privacy_proc_s"] = sum(t for n, t in first.items() if "privacy_filter" in n)
    return d

def du(p): return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0

def run(name, arm, cmd, check=True):
    use_manifest(arm)
    subprocess.run(["bash", "-c", "pgrep -x cargo || true; pgrep rustc || true; df -h . | tail -1"])
    print(f"::group::{name} [{arm}] {' '.join(map(str, cmd))}", flush=True)
    t = time.monotonic(); log = OUT / f"{name}.log"
    env = dict(os.environ, CARGO_TARGET_DIR=str(target(arm)))
    with log.open("wb") as f:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        for line in iter(p.stdout.readline, b""):
            f.write(line); sys.stdout.buffer.write(line); sys.stdout.buffer.flush()
        code = p.wait()
    el = time.monotonic() - t
    text = ANSI.sub("", log.read_text(encoding="utf-8", errors="replace"))
    d = parse(text); names = d.pop("names")
    if names: (OUT / f"{name}-names.txt").write_text("\n".join(names), encoding="utf-8")
    rec = {"name": name, "arm": arm, "elapsed": el, "exit": code, "n_names": len(names),
           "compiled": re.findall(r"^\s+Compiling (\S+)", text, re.M), **d}
    R["steps"].append(rec); save()
    print(f"ELAPSED {name} {el:.1f}s exit={code}", flush=True); print("::endgroup::", flush=True)
    if check and code: raise SystemExit(code)
    return rec

try:
    run("version", "A", [CARGO, "--version"])
    for arm in ARMS:
        run(f"cold-{arm}", arm, [CARGO, "nextest", "list", *BASE])
        R[f"deps_bytes_{arm}"] = du(target(arm) / "debug" / "deps"); save()
    for i, arm in enumerate(ORDER, 1):
        reset_leaked_state()
        subprocess.run([CARGO, "clean", *BASE[:2], "-p", "cc-switch"], env=dict(os.environ, CARGO_TARGET_DIR=str(target(arm))), check=True)
        rec = run(f"p{i}-{arm}", arm, [CARGO, "nextest", "run", *BASE, "--profile", "ci", "--timings"], check=False)
        for html in (target(arm) / "cargo-timings").glob("cargo-timing.html"):
            shutil.copy(html, OUT / f"p{i}-{arm}-cargo-timing.html")
        assert [c for c in rec["compiled"] if c != "cc-switch"] == [], rec["compiled"]
    sets = {(OUT / f"p{i}-{a}-names.txt").read_text(encoding="utf-8") for i, a in enumerate(ORDER, 1)}
    R["coverage_equal"] = len(sets) == 1; save()
    R["bin_bytes"] = {a: du(target(a) / "debug") for a in ARMS}; save()
finally:
    MANIFEST.write_text(ORIGINAL, encoding="utf-8", newline=""); save()
