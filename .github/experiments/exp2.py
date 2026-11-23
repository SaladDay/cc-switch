"""Disposable interleaved A/B benchmark for fork CI only. Arms:
A = unchanged; B = main WITHOUT the [profile.dev.package] opt-level=2 block that #9872 merged (reverse A/B);
C = A + rust-lld linker (Windows only). Each arm has its own target dir; order X Y Y X."""
import json, os, pathlib, re, shutil, subprocess, sys, time

ARMS = os.environ["ARMS"].split(",")           # e.g. "A,B"
ORDER = [ARMS[0], ARMS[1], ARMS[1], ARMS[0]]
ROOT = pathlib.Path.cwd(); OUT = ROOT / "experiment-results"; OUT.mkdir(exist_ok=True)
MANIFEST = ROOT / "src-tauri/Cargo.toml"; ORIGINAL = MANIFEST.read_text(encoding="utf-8")
START = ORIGINAL.index("[profile.dev.package]"); END = ORIGINAL.index("[profile.release]")
NO_OPT = ORIGINAL[:START] + ORIGINAL[END:]
assert "{ opt-level = 2 }" in ORIGINAL and "{ opt-level = 2 }" not in NO_OPT
CARGO = shutil.which("cargo"); BASE = ["--manifest-path", "src-tauri/Cargo.toml", "--locked"]
R = {"arms": ARMS, "order": ORDER, "cpu_count": os.cpu_count(), "platform": sys.platform, "steps": []}
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

def save(): (OUT / "results.json").write_text(json.dumps(R, indent=2))

def env_for(arm):
    e = dict(os.environ, CARGO_TARGET_DIR=str(ROOT / f"target-{arm}"))
    if arm == "C":
        e["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER"] = "rust-lld.exe"
    return e

def use_manifest(arm):
    MANIFEST.write_text(NO_OPT if arm == "B" else ORIGINAL, encoding="utf-8", newline="")

def run(name, arm, cmd):
    use_manifest(arm)
    subprocess.run(["bash", "-c", "pgrep -x cargo || true; pgrep rustc || true; df -h . | tail -1"])
    print(f"::group::{name} [{arm}] {' '.join(map(str, cmd))}", flush=True)
    t = time.monotonic(); log = OUT / f"{name}.log"
    with log.open("wb") as f:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env_for(arm))
        for line in iter(p.stdout.readline, b""):
            f.write(line); sys.stdout.buffer.write(line); sys.stdout.buffer.flush()
        code = p.wait()
    el = time.monotonic() - t
    text = ANSI.sub("", log.read_text(encoding="utf-8", errors="replace"))
    rec = {"name": name, "arm": arm, "elapsed": el, "exit": code,
           "compiled": re.findall(r"^\s+Compiling (\S+)", text, re.M)}
    m = re.findall(r"Finished `test` profile.* in (?:(\d+)m )?([\d.]+)s", text)
    if m: rec["compile_s"] = float(m[-1][0] or 0) * 60 + float(m[-1][1])
    m = re.search(r"Summary\s+\[\s*([\d.]+)s\]\s+(\d+) tests run: (\d+) passed", text)
    if m: rec.update(exec_s=float(m[1]), run=int(m[2]), passed=int(m[3]))
    tests = {}
    for d, n in re.findall(r"PASS \[\s*([\d.]+)s\]\s+\(\d+/\d+\)\s+(.+)$", text, re.M):
        tests[n.strip()] = float(d)
    if tests:
        rec["passed_names_sha"] = __import__("hashlib").sha256("\n".join(sorted(tests)).encode()).hexdigest()
        priv = {k: v for k, v in tests.items() if "privacy_filter" in k}
        rec.update(privacy_n=len(priv), privacy_proc_s=sum(priv.values()), all_proc_s=sum(tests.values()))
        (OUT / f"{name}-names.txt").write_text("\n".join(sorted(tests)), encoding="utf-8")
    R["steps"].append(rec); save()
    print(f"ELAPSED {name} {el:.1f}s exit={code}", flush=True); print("::endgroup::", flush=True)
    if code: raise SystemExit(code)
    return rec

try:
    run("version", "A", [CARGO, "--version"])
    # Untimed-for-A/B cold builds (also reported as cold-cache cost per arm).
    for arm in ARMS:
        run(f"cold-{arm}", arm, [CARGO, "nextest", "list", *BASE])
    for i, arm in enumerate(ORDER, 1):
        subprocess.run([CARGO, "clean", *BASE[:2], "-p", "cc-switch"], env=env_for(arm), check=True)
        rec = run(f"p{i}-{arm}", arm, [CARGO, "nextest", "run", *BASE, "--profile", "ci"])
        bad = [c for c in rec["compiled"] if c != "cc-switch"]
        assert not bad, f"timed phase rebuilt deps: {bad}"
    shas = {s["passed_names_sha"] for s in R["steps"] if s["name"].startswith("p")}
    R["coverage_equal"] = len(shas) == 1; save()
    assert R["coverage_equal"], "passed test set differs between arms"
    if sys.platform.startswith("linux"):
        for arm in ARMS:
            lib = max((x for x in (ROOT / f"target-{arm}/debug/deps").glob("cc_switch_lib-*") if x.suffix == "" and os.access(x, os.X_OK)), key=lambda x: x.stat().st_mtime)
            for k in range(2):
                run(f"init-{arm}-{k}", arm, [str(lib), "--exact", "proxy::privacy_filter::tests::pii_and_secrets_detection_rules"])
finally:
    MANIFEST.write_text(ORIGINAL, encoding="utf-8", newline=""); save()
