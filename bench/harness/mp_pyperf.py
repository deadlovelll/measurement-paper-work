"""Measurement harness: a thin layer over pyperf, which does all the timing."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
import sys
import sysconfig
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pyperf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.environ.get("BENCH_RESULTS_DIR") or os.path.join(ROOT, "results", "pyperf")


def bench_tag() -> str:
    """Short tag identifying the running interpreter, used in result filenames."""
    v = sys.version_info
    ft = "t" if sysconfig.get_config_var("Py_GIL_DISABLED") else ""
    impl = platform.python_implementation().lower()
    prefix = "" if impl == "cpython" else f"{impl}-"
    return f"{prefix}{v.major}{v.minor}{ft}"


def native_flag() -> str:
    """The CPU-tuning flag the native artefacts were actually compiled with."""
    path = os.path.join(ROOT, "bench", "build", "native", "native_flag.txt")
    try:
        with open(path) as fh:
            flag = fh.read().strip()
        if flag:
            return flag
    except OSError:
        pass
    return "-march=native" if platform.machine() in ("x86_64", "AMD64") else "-mcpu=native"


def machine_facts() -> dict[str, Any]:
    """Host description. pyperf's own metadata does not carry the CPU model on macOS."""

    def sysctl(name: str) -> str | None:
        try:
            out = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True,
                                 timeout=5)
            return out.stdout.strip() or None
        except Exception:
            return None

    info: dict[str, Any] = {"platform": platform.platform(), "machine": platform.machine(),
            "system": platform.system(), "cpu_count": os.cpu_count()}
    if platform.system() == "Darwin":
        info["cpu_brand"] = sysctl("machdep.cpu.brand_string")
        info["cores_physical"] = sysctl("hw.physicalcpu")
        info["cores_perf"] = sysctl("hw.perflevel0.physicalcpu")
        info["cores_eff"] = sysctl("hw.perflevel1.physicalcpu")
        mem = sysctl("hw.memsize")
        info["mem_gb"] = round(int(mem) / 2**30, 1) if mem else None
        info["os_version"] = sysctl("kern.osproductversion")
    else:
        try:
            with open("/proc/cpuinfo") as fh:
                for line in fh:
                    if line.lower().startswith(("model name", "cpu model")):
                        info["cpu_brand"] = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    return info


def interp_facts() -> dict[str, Any]:
    """Interpreter properties that are observations rather than timings."""
    gil = None
    if hasattr(sys, "_is_gil_enabled"):
        try:
            gil = bool(sys._is_gil_enabled())
        except Exception:
            gil = None
    return {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "gil_enabled": gil,
        "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "config_args": sysconfig.get_config_var("CONFIG_ARGS"),
        "core_cflags": sysconfig.get_config_var("PY_CORE_CFLAGS"),
    }


class Suite:
    """A pyperf runner plus the bookkeeping the figures and the gate need."""

    name: str
    label: str
    runner: pyperf.Runner
    gate_failures: list[dict[str, Any]]
    facts: dict[str, Any]

    def __init__(self, name: str, *, forward: Sequence[str] = (),
                 label_arg: bool = True) -> None:
        self.name = name
        self._forward = tuple(forward)

        def add_cmdline_args(cmd: list[str], args: Any) -> None:
            for opt in self._forward:
                val = getattr(args, opt.replace("-", "_"), None)
                if val is None or val is False:
                    continue
                if val is True:
                    cmd.append(f"--{opt}")
                else:
                    cmd.extend([f"--{opt}", str(val)])

        self.runner = pyperf.Runner(add_cmdline_args=add_cmdline_args)
        if label_arg:
            self.runner.argparser.add_argument(
                "--label", default=bench_tag(),
                help="tag written into the result filename and the metadata")
            self._forward = (*self._forward, "label")
        self.gate_failures = []
        self.facts = {}
        self._registered: list[str] = []
        self._checked: set[object] = set()
        self._parsed = False

    def parse(self) -> Any:
        args = self.runner.parse_args()
        self.label = getattr(args, "label", bench_tag())
        if not args.worker:
            os.makedirs(RESULTS, exist_ok=True)
            if not args.output and not getattr(args, "append", None):
                args.output = os.path.join(RESULTS, f"{self.name}-{self.label}.json")
                if os.path.exists(args.output):
                    os.remove(args.output)
        self.runner.metadata["mp_suite"] = self.name
        self.runner.metadata["mp_label"] = self.label
        self._parsed = True
        return args

    @property
    def is_master(self) -> bool:
        args = self.runner.args
        assert args is not None, "call parse() first"
        return not args.worker

    def log(self, msg: str) -> None:
        if self.is_master:
            print(msg, flush=True)

    def gate(self, *, case: str, impl: str, got: object, expected: object,
             tol: float = 0.0, note: str = "") -> bool:
        """True if `impl` may be timed. Cheap, deterministic, run in master and workers."""
        ok, dev = _close(got, expected, tol)
        if not ok:
            self.gate_failures.append({
                "case": case, "impl": impl, "status": "wrong_result",
                "got": _brief(got), "expected": _brief(expected),
                "deviation": dev, "tol": tol, "note": note,
            })
            self.log(f"  GATE FAIL {case:<24} {impl:<22} got={_brief(got)} "
                     f"expected={_brief(expected)} dev={dev:.2e}")
        return ok

    def unavailable(self, *, case: str, impl: str, note: str) -> None:
        self.gate_failures.append({"case": case, "impl": impl,
                                   "status": "unavailable", "note": note[:300]})
        self.log(f"  UNAVAILABLE {case:<22} {impl:<22} {note[:80]}")

    def bench(self, *, case: str, impl: str, fn: Callable[[], object],
              params: Mapping[str, Any] | None = None, note: str = "",
              inner_loops: int | None = None) -> pyperf.Benchmark:
        """Register one timed benchmark with pyperf."""
        assert self._parsed, "call parse() first"
        name = f"{case}/{impl}"
        assert name not in self._registered, f"duplicate benchmark {name}"
        self._registered.append(name)
        md: dict[str, str] = {"mp_case": case, "mp_impl": impl}
        if params:
            md["mp_params"] = json.dumps(params, sort_keys=True, separators=(",", ":"))
        if note:
            md["mp_note"] = note[:200]
        return self.runner.bench_func(name, fn, metadata=md, inner_loops=inner_loops)

    def bench_time(self, *, case: str, impl: str, time_fn: Callable[[int], float],
                   params: Mapping[str, Any] | None = None, note: str = "",
                   inner_loops: int | None = None) -> pyperf.Benchmark:
        """Register a benchmark that does its own loop (pyperf passes it `loops`)."""
        assert self._parsed, "call parse() first"
        name = f"{case}/{impl}"
        assert name not in self._registered, f"duplicate benchmark {name}"
        self._registered.append(name)
        md: dict[str, str] = {"mp_case": case, "mp_impl": impl}
        if params:
            md["mp_params"] = json.dumps(params, sort_keys=True, separators=(",", ":"))
        if note:
            md["mp_note"] = note[:200]
        return self.runner.bench_time_func(name, time_fn, metadata=md,
                                           inner_loops=inner_loops)

    def bench_command(self, *, case: str, impl: str, command: Sequence[str],
                      params: Mapping[str, Any] | None = None,
                      note: str = "") -> pyperf.Benchmark:
        """Register a whole-process timing (start-up, import latency)."""
        assert self._parsed, "call parse() first"
        name = f"{case}/{impl}"
        self._registered.append(name)
        self.facts.setdefault("commands", {})[name] = {
            "command": list(command), "params": params or {}, "note": note}
        return self.runner.bench_command(name, command)

    def machine_probe(self, iters: int = 2_000_000) -> None:
        """A fixed native loop, timed like everything else."""
        so = "dylib" if sys.platform == "darwin" else "so"
        path = os.path.join(ROOT, "bench", "build", "native", f"libkernels_c_O3native.{so}")
        if not os.path.exists(path):
            self.unavailable(case="machine_probe", impl="c_busy", note=f"missing {path}")
            return
        try:
            lib = ctypes.CDLL(path)
            lib.c_busy.restype = ctypes.c_double
            lib.c_busy.argtypes = [ctypes.c_longlong, ctypes.c_double]
        except Exception as exc:
            self.unavailable(case="machine_probe", impl="c_busy", note=repr(exc))
            return
        self.bench(case="machine_probe", impl="c_busy",
                   fn=lambda: lib.c_busy(iters, 1.0), params={"iters": iters},
                   note="fixed native loop; interpreter-independent")

    def check_once(self, key: object, verify: Callable[[], object], expected: object,
                   tol: float = 0.0) -> None:
        """Verify a timed callable once per worker process, before it is timed."""
        if key in self._checked:
            return
        self._checked.add(key)
        got = verify()
        ok, dev = _close(got, expected, tol)
        if not ok:
            raise RuntimeError(
                f"correctness check failed in this process for {key}: got {_brief(got)}, "
                f"expected {_brief(expected)}, relative deviation {dev:.3e} > tol {tol:.3e}")

    def write_sidecar(self) -> None:
        """Facts and gate failures, written by the master only."""
        if not self.is_master:
            return
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, f"{self.name}-{self.label}.facts.json")
        payload = {
            "suite": self.name,
            "label": self.label,
            "interp": interp_facts(),
            "machine": machine_facts(),
            "registered": self._registered,
            "gate_failures": self.gate_failures,
            "facts": self.facts,
        }
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print(f"[{self.name}] sidecar -> {path}", flush=True)


def _brief(x: object, n: int = 60) -> str:
    s = repr(x)
    return s if len(s) <= n else s[:n] + "..."


def _close(got: object, expected: object, tol: float) -> tuple[bool, float]:
    """Relative comparison; `tol` > 0 permits reassociated floating point."""
    if got == expected:
        return True, 0.0
    if isinstance(got, (int, float)) and isinstance(expected, (int, float)):
        dev = abs(got - expected) / max(1.0, abs(expected))
        return dev <= tol, dev
    if isinstance(got, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(got) != len(expected):
            return False, float("inf")
        worst = 0.0
        for a, b in zip(got, expected, strict=True):
            ok, dev = _close(a, b, tol)
            worst = max(worst, dev)
            if not ok:
                return False, worst
        return True, worst
    return False, float("inf")
