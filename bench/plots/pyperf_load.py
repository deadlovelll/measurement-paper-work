"""Read pyperf result files and hand the figures the shape they expect."""

from __future__ import annotations

import glob
import json
import os
import statistics
from collections.abc import Sequence
from typing import Any, Literal, TypedDict, cast

import pyperf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYPERF_DIR = os.path.join(ROOT, "results", "pyperf")

Status = Literal["ok", "facts", "problem", "unavailable", "wrong_result", "unsupported"]


class Machine(TypedDict, total=False):
    platform: str | None
    cpu_brand: str | None
    cpu_count: int | None
    cpu_config: str | None
    hostname: str | None
    boot_time: str | None
    load_avg_1min: float | None


class Interp(TypedDict, total=False):
    executable: str | None
    version: str
    implementation: str | None
    compiler: str | None
    config_args: str | None
    cflags: str | None
    unicode: str | None
    gc: str | None
    gil_enabled: bool | None
    free_threaded: bool
    core_cflags: str | None


class Stats(TypedDict):
    median_s: float
    min_s: float
    max_s: float
    mean_s: float
    stdev_s: float
    mad_rel: float
    samples: int
    processes: int
    loops: int | None
    inner_loops: int
    raw_per_op_s: list[float]


class _RecordRequired(TypedDict):
    suite: str
    case: str
    impl: str
    label: str
    status: Status
    note: str
    params: dict[str, Any]
    stats: Stats | None
    interp: Interp
    machine: Machine


class Record(_RecordRequired, total=False):
    benchmark: str
    extra: dict[str, Any]


class Comparison(TypedDict):
    significant: bool
    t_score: float
    ratio: float
    median_a: float
    median_b: float


def _machine(md: dict[str, Any]) -> Machine:
    return {
        "platform": md.get("platform"),
        "cpu_brand": md.get("cpu_model_name"),
        "cpu_count": md.get("cpu_count"),
        "cpu_config": md.get("cpu_config"),
        "hostname": md.get("hostname"),
        "boot_time": md.get("boot_time"),
        "load_avg_1min": md.get("load_avg_1min"),
    }


def _interp(md: dict[str, Any]) -> Interp:
    return {
        "executable": md.get("python_executable"),
        "version": ((md.get("python_version") or "").split() or [""])[0],
        "implementation": md.get("python_implementation"),
        "compiler": md.get("python_compiler"),
        "config_args": md.get("python_config_args"),
        "cflags": md.get("python_cflags"),
        "unicode": md.get("python_unicode"),
        "gc": md.get("python_gc"),
    }


def _stats(bench: pyperf.Benchmark) -> Stats:
    values = bench.get_values()
    med = bench.median()
    mad = bench.median_abs_dev() if len(values) > 1 else 0.0
    return {
        "median_s": med,
        "min_s": min(values),
        "max_s": max(values),
        "mean_s": bench.mean(),
        "stdev_s": bench.stdev() if len(values) > 2 else 0.0,
        "mad_rel": (mad / med) if med else 0.0,
        "samples": bench.get_nvalue(),
        "processes": bench.get_nrun(),
        "loops": bench.get_metadata().get("loops"),
        "inner_loops": bench.get_metadata().get("inner_loops", 1),
        "raw_per_op_s": list(values),
    }


def load_file(path: str) -> list[Record]:
    """Records from one pyperf result file, plus its sidecar if there is one."""
    out: list[Record] = []
    suite_json = pyperf.BenchmarkSuite.load(path)
    for bench in suite_json.get_benchmarks():
        if not bench.get_values():
            print(f"[pyperf_load] {os.path.basename(path)}: {bench.get_name()} has no values,"
                  " skipped")
            continue
        md = bench.get_metadata()
        if "mp_case" not in md and "/" in bench.get_name():
            case_, impl_ = bench.get_name().split("/", 1)
            md = dict(md, mp_case=case_, mp_impl=impl_)
        params: dict[str, Any] = {}
        if md.get("mp_params"):
            try:
                params = json.loads(md["mp_params"])
            except ValueError:
                params = {"raw": md["mp_params"]}
        out.append({
            "suite": md.get("mp_suite", ""),
            "case": md.get("mp_case", bench.get_name()),
            "impl": md.get("mp_impl", ""),
            "label": md.get("mp_label", ""),
            "status": "ok",
            "note": md.get("mp_note", ""),
            "params": params,
            "stats": _stats(bench),
            "interp": _interp(md),
            "machine": _machine(md),
            "benchmark": bench.get_name(),
        })

    side = path[:-5] + ".facts.json"
    if os.path.exists(side):
        with open(side) as fh:
            sc = json.load(fh)
        out.extend(
            {
                "suite": sc.get("suite", ""), "case": prob.get("case", ""),
                "impl": prob.get("impl", ""), "label": sc.get("label", ""),
                "status": prob.get("status", "problem"), "note": prob.get("note", ""),
                "params": {}, "stats": None,
                "interp": sc.get("interp", {}), "machine": {},
                "extra": {k: v for k, v in prob.items()
                          if k not in ("case", "impl", "status", "note")},
            }
            for prob in sc.get("gate_failures", []))
        if sc.get("facts"):
            out.append({
                "suite": sc.get("suite", ""), "case": "runtime_facts",
                "impl": sc.get("label", ""), "label": sc.get("label", ""),
                "status": "facts", "note": "structural properties, not a timing",
                "params": {}, "stats": None, "interp": sc.get("interp", {}),
                "machine": sc.get("machine", {}), "extra": sc["facts"],
            })
        if sc.get("machine"):
            for rec in out:
                if rec["status"] == "ok":
                    known = {k: v for k, v in sc["machine"].items() if v is not None}
                    rec["machine"].update(cast("Machine", known))
    return out


def load(prefix: str) -> list[Record]:
    """All records from results/pyperf/<prefix>*.json (plan and sidecar files excluded)."""
    out: list[Record] = []
    for path in sorted(glob.glob(os.path.join(PYPERF_DIR, f"{prefix}*.json"))):
        if path.endswith((".plan.json", ".facts.json")):
            continue
        out.extend(load_file(path))
    return out


def compare(a_values: Sequence[float], b_values: Sequence[float]) -> Comparison:
    """pyperf's own significance test, so "no difference" is a statement and not a shrug."""
    from pyperf._utils import is_significant

    significant, tscore = is_significant(a_values, b_values)
    ma, mb = statistics.median(a_values), statistics.median(b_values)
    return {"significant": bool(significant), "t_score": tscore,
            "ratio": (mb / ma) if ma else float("nan"),
            "median_a": ma, "median_b": mb}
