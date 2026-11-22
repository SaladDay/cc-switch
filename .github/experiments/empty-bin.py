"""Disposable paired benchmark, not a production CI change."""
import hashlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path.cwd()
OUT = ROOT / "experiment-results"
OUT.mkdir(exist_ok=True)
MANIFEST = ROOT / "src-tauri/Cargo.toml"
ORIGINAL = MANIFEST.read_bytes()
RESULTS = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
           "platform": platform.platform(), "cpu_count": os.cpu_count(), "steps": []}

def usage():
    if os.name == "nt":
        return None
    import resource
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return [r.ru_utime, r.ru_stime]

def save():
    (OUT / "results.json").write_text(json.dumps(RESULTS, indent=2))

def execute(name, command, *, json_output=False):
    print(f"::group::{name}: {' '.join(map(str, command))}", flush=True)
    if pathlib.Path(str(command[0])).name.lower() in ["cargo", "cargo.exe"]:
        subprocess.run(["bash", "-c", "pgrep -x cargo || true; pgrep rustc || true"], check=False)
        if os.name == "nt":
            subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process cargo,rustc -ErrorAction SilentlyContinue | Select-Object Name,Id"], check=False)
    cpu = usage()
    start = time.monotonic()
    logpath = OUT / f"{name}.log"
    if json_output:
        with logpath.open("wb") as err, (OUT / f"{name}.json").open("wb") as out:
            completed = subprocess.run(command, stdout=out, stderr=err)
    else:
        with logpath.open("wb") as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in iter(process.stdout.readline, b""):
                log.write(line)
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            completed = subprocess.CompletedProcess(command, process.wait())
    elapsed = time.monotonic() - start
    after = usage()
    record = {"name": name, "command": list(map(str, command)), "elapsed_seconds": elapsed,
              "exit_code": completed.returncode}
    if cpu is not None:
        record["child_cpu_seconds"] = [after[i] - cpu[i] for i in range(2)]
    RESULTS["steps"].append(record)
    save()
    print(f"ELAPSED {name} {elapsed:.3f}s exit={completed.returncode}", flush=True)
    print("::endgroup::", flush=True)
    completed.check_returncode()
    if json_output:
        print(logpath.read_text(errors="replace"), flush=True)
        return json.loads((OUT / f"{name}.json").read_text())

CARGO = shutil.which("cargo")
if not CARGO:
    raise RuntimeError("cargo missing")
BASE = ["--manifest-path", "src-tauri/Cargo.toml", "--locked"]

def build_list(phase):
    return execute(f"{phase}-build-list", [CARGO, "nextest", "list", *BASE,
                   "--build-jobs", "1", "--message-format", "json"], json_output=True)

def clippy(phase):
    execute(f"{phase}-clippy", [CARGO, "clippy", "-j1", *BASE, "--all-targets", "--", "-D", "warnings"])

def clean(phase):
    execute(f"{phase}-clean-package", [CARGO, "clean", "--manifest-path", "src-tauri/Cargo.toml", "-p", "cc-switch"])

def normalized(manifest):
    tests = []
    empty = []
    for identity, suite in manifest["rust-suites"].items():
        cases = suite["testcases"]
        if not cases:
            empty.append({"identity": identity, "kind": suite["kind"], "binary-name": suite["binary-name"]})
        for name, data in cases.items():
            tests.append([identity, name, data])
    return sorted(tests, key=lambda x: (x[0], x[1])), empty

try:
    execute("compiler-version", [CARGO, "--version"])
    execute("rustc-version", ["rustc", "-Vv"])
    RESULTS["source_tree_sha256"] = hashlib.sha256(subprocess.check_output(["git", "ls-tree", "-r", "HEAD", "src", "tests", "src-tauri/src", "src-tauri/tests", "src-tauri/Cargo.lock", "rust-toolchain.toml"])).hexdigest()
    # Match main's dependency-only warm cache without a cache backend or cold/warm bias.
    # The warmup is unreported; clean -p removes workspace artifacts, not dependencies.
    clippy("warmup")
    build_list("warmup")
    for phase in ["baseline", "candidate"]:
        if phase == "candidate":
            assert b"[[bin]]" not in ORIGINAL
            MANIFEST.write_bytes(ORIGINAL.replace(b"[features]", b'[[bin]]\nname = "cc-switch"\npath = "src/main.rs"\ntest = false\n\n[features]', 1))
            (OUT / "candidate.diff").write_bytes(subprocess.check_output(["git", "diff", "--", "src-tauri/Cargo.toml"]))
        clean(phase)
        clippy(phase)
        listing = build_list(phase)
        tests, empty = normalized(listing)
        RESULTS[phase] = {"test_count": len(tests), "tests_sha256": hashlib.sha256(json.dumps(tests, sort_keys=True).encode()).hexdigest(), "empty_suites": empty}
        (OUT / f"{phase}-normalized-tests.json").write_text(json.dumps(tests, indent=2))
        if phase == "baseline":
            baseline_tests = tests
            baseline_empty = empty
        else:
            assert tests == baseline_tests, "real test manifest changed"
            removed = [s for s in baseline_empty if s not in empty]
            RESULTS["removed_empty_suites"] = removed
            # No nonempty suite can disappear because the complete manifest was compared.
            assert len(removed) == 1 and removed[0]["kind"] == "bin", removed
        save()
        execute(f"{phase}-run", [CARGO, "nextest", "run", *BASE, "--build-jobs", "1", "--profile", "ci"])
    RESULTS["coverage_equivalent"] = True
    save()
    # Independent hotspot probe, excluded from paired A/B timing. Linux only.
    # Same unchanged test binary: one case versus whole module in one process.
    if sys.platform.startswith("linux"):
        library = next(s["binary-path"] for s in listing["rust-suites"].values() if s["kind"] == "lib" and s["binary-name"] == "cc_switch_lib")
        execute("privacy-single-process-one-case", [library, "--exact", "proxy::privacy_filter::tests::gitleaks_rules_loaded", "--nocapture"])
        execute("privacy-single-process-module", [library, "proxy::privacy_filter::tests::", "--test-threads", "1", "--nocapture"])
        execute("privacy-nextest-module", [CARGO, "nextest", "run", *BASE, "--build-jobs", "1", "--profile", "ci", "-E", "test(/^proxy::privacy_filter::tests::/)"])
finally:
    MANIFEST.write_bytes(ORIGINAL)
    save()
