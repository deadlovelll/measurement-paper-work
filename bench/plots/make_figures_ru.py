#!/usr/bin/env python
"""Russian-language rendering of the same figures, from the same result files."""

from __future__ import annotations

import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import make_figures as mf
import style
from matplotlib.axes import Axes
from matplotlib.figure import Figure

RU = {
    "Same letter = same machine code": "Одна буква — один машинный код",
    "What the flags cost": "Что дают флаги",
    "Regrouped in the source, at -O2": "Перегруппировано в исходнике, при -O2",
    "One C source: what the flags change, and where the one large effect lives":
        "Один исходник на C: что меняют флаги и где живёт единственный крупный эффект",
    "speedup over clang -O2 (log)": "ускорение относительно clang -O2 (лог.)",
    "speedup over the serial -O2 loop": "ускорение относительно последовательного цикла -O2",
    "1 accumulator": "1 аккумулятор",
    "time of -O2 / time of this variant (log)":
        "время -O2 / время этого варианта (лог.)",
    "-O3 -march=native": "-O3 -march=native",
    "  + no vectoriser": "  + без векторизации",
    "  + -ffast-math": "  + -ffast-math",
    "sum": "сумма",
    "mandel": "мандельброт",
    "Adaptive specialisation warm-up": "Разогрев адаптивной специализации",
    "time of that execution, us": "время этого исполнения, мкс",
    "What each build option is worth": "Что даёт каждая опция сборки",
    "Where the combination gains and loses": "Где комбинация выигрывает и где теряет",
    "PGO + full LTO, per operation, vs plain":
        "PGO + full LTO, по операциям, против обычной сборки",
    "CPython 3.14.6: seven build configurations, one source tree, one compiler":
        "CPython 3.14.6: семь конфигураций сборки, одно дерево исходников, один компилятор",
    "speedup of --enable-experimental-jit over the identical non-JIT build":
        "ускорение --enable-experimental-jit относительно той же сборки без JIT",
    "Build options, geometric mean over the suite":
        "Опции сборки, геометрическое среднее по набору",
    "speedup over the pure-Python loop (log)": "ускорение относительно чистого Python (лог. шкала)",
    "speedup over clang -O2": "ускорение относительно clang -O2",
    "number of calls": "число вызовов",
    "cumulative wall time, s": "суммарное время, с",
    "array length": "длина массива",
    "time per call, ms": "время на вызов, мс",
    "calls needed to break even": "вызовов до окупаемости",
    "cost of one call with an empty callee, ns": "стоимость одного вызова с пустой функцией, нс",
    "threads": "потоков",
    "speedup over 1 thread": "ускорение относительно 1 потока",
    "stage time, ms": "время стадии, мс",
    "interpreter startup, ms": "запуск интерпретатора, мс",
    "import time, ms (log)": "время импорта, мс (лог.)",
    "ms per call (log)": "мс на вызов (лог.)",
    "execution number of a freshly compiled code object":
        "номер исполнения свежескомпилированного код-объекта",
    "time per execution, us": "время одного исполнения, мкс",
    "single-thread time relative to the GIL build (>1 = slower)":
        "однопоточное время относительно сборки с GIL (>1 — медленнее)",
    "run time relative to stock CPython 3.14.6  (>1 = slower)":
        "время относительно обычного CPython 3.14.6 (>1 — медленнее)",
    "as-distributed run time / identical-flag build run time (geomean)":
        "время дистрибутивной сборки / сборки с теми же флагами (геосреднее)",
    "end-to-end pipeline time, ms (labels: speedup over the pure-Python variant)":
        "время пайплайна целиком, мс (подписи — ускорение к чистому Python)",
    "geomean vs the Apple clang 16 build": "геосреднее относительно сборки Apple clang 16",
    "PyPy speedup over CPython 3.14 (log)": "ускорение PyPy относительно CPython 3.14 (лог.)",
    "PyPy speedup over CPython 3.14, same pure-Python source":
        "ускорение PyPy относительно CPython 3.14, тот же код на чистом Python",
    "Cost per call vs input size": "Стоимость вызова и размер входа",
    "How long until the JIT has paid for itself": "Когда JIT себя окупает",
    "Codon JIT, steady state": "Codon JIT, установившийся режим",
    "Numba": "Numba",
    "The FFI boundary itself": "Сама граница FFI",
    "Where the acceleration goes: compute-bound vs branchy workloads":
        "Куда уходит ускорение: вычисления против ветвистого кода",
    "The single-thread cost of free-threading": "Однопоточная цена отказа от GIL",
    "CPython 3.14.6 built four ways": "CPython 3.14.6, собранный четырьмя способами",
    "Startup latency": "Задержка запуска",
    "Where the time sits (per stage)": "Где находится время (по стадиям)",
    "Static Python, 96x96 int matmul": "Static Python, matmul int64",
    "200-module package import": "Импорт 200 модулей",
    "Build provenance, not version: the same CPython version, two builds":
        "Дело не в версии, а в сборке: одна версия CPython, две сборки",
    "Building the interpreter yourself": "Если собирать интерпретатор самому",
    "What the distributor's options cost": "Чего стоят опции дистрибутива",
    "One configuration, three compilers": "Одна конфигурация, три компилятора",
    "Where the toolchain shows up": "Где проявляется тулчейн",
    "Interpreter-level operations": "Операции уровня интерпретатора",
    "The six kernels, unmodified": "Шесть ядер, код без изменений",
    "Effect of the adaptive flag": "Эффект адаптивного флага",
    "adaptive on / adaptive off": "адаптивный вкл / адаптивный выкл",
    "Speed relative to the default JIT configuration  (>1 = faster)":
        "Скорость относительно конфигурации JIT по умолчанию (>1 — быстрее)",
    "Nothing is faster than the default": "Быстрее умолчания нет ничего",
    "geometric mean over the six kernels": "геометрическое среднее по шести ядрам",
    "specialised opcodes off": "специализированные опкоды выкл",
    "compile at first call": "компиляция при первом вызове",
    "JIT off": "JIT выключен",
    "simplifier capped": "упрощатель ограничен",
    "stable-frame off": "stable-frame выкл",
    "attribute caches off": "кэши атрибутов выкл",
    "hot/cold code split": "разделение горячего и холодного кода",
    "hot/cold split + huge pages": "разделение + большие страницы",
    "array sum": "сумма массива",
    "mandelbrot": "мандельброт",
    "matmul": "matmul",
    "tokenize": "токенизация",
    "bin. trees": "двоичные деревья",
    "graph BFS": "обход графа",
    "What the collector can see": "Что видно сборщику",
    "gc.collect(), ms": "gc.collect(), мс",
    "serial": "последовательно",
    "6 threads": "6 потоков",
    "stock 3.14": "обычный 3.14",
    "CinderX, state visible": "CinderX, состояние видно",
    "+ gc.freeze()": "+ gc.freeze()",
    "+ immortalize_heap()": "+ immortalize_heap()",
    "adaptive off": "адаптивный выкл",
    "adaptive on": "адаптивный вкл",
    "runtime": "рантайм",
    "JIT": "JIT",
    "Composing techniques on a mixed pipeline":
        "Композиция техник на смешанном пайплайне",
    "end-to-end time, ms   (bar label = speedup vs pure Python)":
        "время пайплайна целиком, мс (подписи — ускорение к чистому Python)",
    "int arith": "целочисл. арифметика", "int_arith": "целочисл. арифметика",
    "float arith": "вещ. арифметика", "float_arith": "вещ. арифметика",
    "func call": "вызов функции", "func_call": "вызов функции",
    "method call": "вызов метода", "method_call": "вызов метода",
    "attr get": "чтение атрибута", "attr_get": "чтение атрибута",
    "attr get slots": "чтение атрибута (slots)",
    "attr_get_slots": "чтение атрибута (slots)",
    "attr set": "запись атрибута", "attr_set": "запись атрибута",
    "create plain obj": "создание объекта", "create_plain_obj": "создание объекта",
    "create slots obj": "создание объекта (slots)",
    "create_slots_obj": "создание объекта (slots)",
    "create dict": "создание словаря", "create_dict": "создание словаря",
    "create tuple": "создание кортежа", "create_tuple": "создание кортежа",
    "list append": "list.append", "list_append": "list.append",
    "dict setitem": "dict setitem", "dict_setitem": "dict setitem",
    "str format join": "формат. строк", "str_format_join": "формат. строк",
    "exception roundtrip": "исключение", "exception_roundtrip": "исключение",
    "gc collect 100k cycles": "сборка мусора 100k",
    "gc_collect_100k_cycles": "сборка мусора 100k",
    "Cinder fork and CinderX on unmodified Python code, relative to stock CPython":
        "Форк Cinder и CinderX на неизменённом Python-коде, относительно обычного CPython",
    "CPython 3.14.6 tier-2 JIT, same source and toolchain":
        "Tier-2 JIT в CPython 3.14.6, тот же исходник и тулчейн",
    "Same C source, different flags — and Numba on the same kernels":
        "Один и тот же код на C с разными флагами — и Numba на тех же ядрах",
    "compute-bound kernels": "вычислительные ядра",
    "branchy / allocating kernels": "ветвистые ядра / с аллокациями",
    "pure Python": "чистый Python",
    "Numba (compile + run)": "Numba (компиляция + счёт)",
    "Numba, steady state": "Numba, установившийся режим",
    "C (clang)": "C (clang)",
    "Numba (LLVM)": "Numba (LLVM)",
    "parse (json)": "разбор (json)",
    "classify": "классификация",
    "aggregate": "агрегация",
    "linear": "линейно",
    "CPython loop": "цикл на CPython",
    "CPython sum()": "встроенная sum()",
    "C (ctypes)": "C (ctypes)",
    "C (pybind11)": "C (pybind11)",
    "Rust (ctypes)": "Rust (ctypes)",
    "Codon AOT": "Codon AOT",
    "Codon AOT (ptr)": "Codon AOT (указатель)",
    "Codon JIT": "Codon JIT",
    "Python function": "функция Python",
    "clang -O0": "clang -O0",
    "clang -O2": "clang -O2",
    "clang -O3": "clang -O3",
    "+ no vectorise": "+ без векторизации",
    "Numba fastmath": "Numba fastmath",
    "Cinder fork": "форк Cinder",
    "+ CinderX runtime": "+ рантайм CinderX",
    "+ CinderX JIT": "+ JIT CinderX",
    "+ CinderX runtime, adaptive on": "+ рантайм CinderX, адаптивный включён",
    "+ CinderX JIT, adaptive on": "+ JIT CinderX, адаптивный включён",
    "arithmetic": "арифметика",
    "branchy": "ветвистое",
    "3.14 (GIL)": "3.14 (с GIL)",
    "3.14t, GIL on": "3.14t, GIL включён",
    "3.14t, GIL off": "3.14t, GIL выключен",
    "default": "по умолчанию",
    "PGO+LTO+native": "PGO+LTO+native",
    "array sum (1e6 f64)": "сумма массива (1e6 f64)",
    "mandelbrot 200x150": "мандельброт 200x150",
    "matmul 96x96": "matmul 96x96",
    "tokenize (2e6 bytes)": "токенизация (2e6 байт)",
    "binary trees (d=18)": "бинарные деревья (d=18)",
    "graph BFS (5e5 nodes)": "BFS (5e5 узлов)",
    "pure-Python arithmetic": "арифметика, Python",
    "pure-Python branchy": "ветвления, Python",
    "C kernel, balanced": "ядро C, ровное",
    "C kernel, imbalanced": "ядро C, неровное",
    "Python int (boxed)": "int Python, объекты",
    "Python int + JIT": "int Python + JIT",
    "Static int64, interp": "Static int64, интерп.",
    "  + adaptive": "  + специализация",
    "Static int64 + JIT": "Static int64 + JIT",
    "CPython, eager": "CPython, обычный",
    "fork, eager": "форк, обычный",
    "fork, lazy imports": "форк, ленивые",
    "all pure Python": "всё на чистом Python",
    "+ Numba (numeric)": "+ Numba (числовая стадия)",
    "+ C (classification)": "+ C (классификация)",
    "C + 4 threads (no Numba)": "C + 4 потока (без Numba)",
    "Numba + C + 4 threads": "Numba + C + 4 потока",
    "C classify": "классиф. на C",
    "Numba aggregate": "агрег. Numba",
    "--enable-framework": "--enable-framework",
    "--with-dtrace": "--with-dtrace",
    "distributor's set, rebuilt": "набор дистрибутива, пересобранный",
    "the Homebrew interpreter": "интерпретатор из Homebrew",
    "PGO": "PGO",
    "LTO (thin)": "LTO (thin)",
    "LTO (full)": "LTO (full)",
    "PGO + full LTO": "PGO + full LTO",
    "PGO + full LTO + native": "PGO + full LTO + native",
    "tier-2 JIT": "tier-2 JIT",
    "Apple clang 16": "Apple clang 16",
    "LLVM 19": "LLVM 19",
    "LLVM 22": "LLVM 22",
}

RU_RE = [
    (r"^Numba compilation: ([\d.]+) ms$", r"компиляция Numba: \1 мс"),
    (r"^Codon compilation: ([\d.]+) ms$", r"компиляция Codon: \1 мс"),
    (r"^geomean over (\d+) operations, vs plain \./configure$",
     r"геосреднее по \1 операциям, относительно простой сборки ./configure"),
    (r"^geomean over (\d+) operations, vs a plain \./configure build$",
     r"геосреднее по \1 операциям, относительно простой сборки ./configure"),
    (r"^geometric-mean speedup over pure Python \(CPython ([\d.]+)\)$",
     r"геометрическое среднее ускорения к чистому Python (CPython \1)"),
    (r"^geometric-mean speedup over the default build \((\d+) operations\)$",
     r"геометрическое среднее к сборке по умолчанию (\1 операций)"),
    (r"^speedup vs ([\d.]+) \(log2 scale, 1\.00 = same\)$",
     r"ускорение относительно \1 (шкала log2, 1.00 — так же)"),
    (r"^CPython ([\d.]+t?) → ([\d.]+t?): per-operation speedup\n"
     r"\(x-factors vs ([\d.]+t?); interpreters compiled here, one compiler, one configure line\)$",
     r"CPython \1 → \2: ускорение по операциям\n(во сколько раз относительно \3 — "
     r"интерпретаторы собраны здесь, один компилятор, одна строка configure)"),
    (r"^CPython ([\d.]+t?) → ([\d.]+t?): per-operation speedup\n"
     r"\(x-factors vs ([\d.]+t?); interpreters (.*)\)$",
     r"CPython \1 → \2: ускорение по операциям\n"
     r"(во сколько раз относительно \3 — интерпретаторы: \4)"),
    (r"^Compute-bound kernels on CPython ([\d.]+) \((.*), (\d+) cores\)$",
     r"Вычислительные ядра на CPython \1 (\2, \3 ядер)"),
    (r"^Compute-bound kernels on CPython ([\d.]+) \((.*)\)$",
     r"Вычислительные ядра на CPython \1 (\2)"),
    (r"^Thread scalability: GIL build vs free-threaded build \((.*), (\d+) cores\)$",
     r"Масштабирование по потокам: сборка с GIL против free-threaded (\1, \2 ядер)"),
    (r"^Thread scalability: GIL build vs free-threaded build \((.*)\)$",
     r"Масштабирование по потокам: сборка с GIL против free-threaded (\1)"),
    (r"^JIT compilation is not free \(array-sum kernel, CPython (.*)\)$",
     r"JIT-компиляция не бесплатна (ядро суммирования массива, CPython \1)"),
    (r"^speedup of --enable-experimental-jit over the identical non-JIT build$",
     r"ускорение --enable-experimental-jit относительно той же сборки без JIT"),
    (r"^(.*) ms\s+\((\d+) bodies\)$", r"\1 мс  (\2 тел)"),
    (r"^(.*) us\s+\((\d+) bodies\)$", r"\1 мкс  (\2 тел)"),
    (r"^(.*) ns\s+\((\d+) bodies\)$", r"\1 нс  (\2 тел)"),
    (r"^([\d.]+) ms$", r"\1 мс"),
    (r"^([\d.]+) us$", r"\1 мкс"),
    (r"^([\d.]+) ns$", r"\1 нс"),
    (r"^([\d.]+) s$", r"\1 с"),
    (r"^one-off compilation: (\d+) ms$", r"разовая компиляция: \1 мс"),
    (r"^break-even\n([\d ]+) calls$", r"окупаемость\n\1 вызовов"),
    (r"^cython -O3.*$", r"cython -O3"),
    (r"^compiled here, one compiler, one configure line$",
     r"собраны здесь, один компилятор, одна строка configure"),
]


def tr(s: Any) -> Any:
    if not isinstance(s, str):
        return s
    if s in RU:
        return RU[s]
    for pat, rep in RU_RE:
        m = re.match(pat, s)
        if m:
            return re.sub(pat, rep, s)
    return s


def patch() -> None:
    for cls, name in ((Axes, "set_xlabel"), (Axes, "set_ylabel"), (Axes, "set_title"),
                      (Figure, "suptitle")):
        orig = getattr(cls, name)

        def wrapper(self: Any, text: Any, *a: Any, _orig: Any = orig, **k: Any) -> Any:
            return _orig(self, tr(text), *a, **k)

        setattr(cls, name, wrapper)

    for name in ("barh", "bar", "plot", "axhline", "axvline"):
        orig = getattr(Axes, name)

        def wrapper(self: Any, *a: Any, _orig: Any = orig, **k: Any) -> Any:
            if "label" in k:
                k["label"] = tr(k["label"])
            return _orig(self, *a, **k)

        setattr(Axes, name, wrapper)

    orig_ann = Axes.annotate

    def ann(self: Any, text: Any, *a: Any, **k: Any) -> Any:
        return orig_ann(self, tr(text), *a, **k)

    Axes.annotate = ann

    orig_yticks = Axes.set_yticks
    orig_xticks = Axes.set_xticks

    def yticks(self: Any, ticks: Any, labels: Any = None, *a: Any, **k: Any) -> Any:
        if labels is not None:
            labels = [tr(x) for x in labels]
        return orig_yticks(self, ticks, labels, *a, **k)

    def xticks(self: Any, ticks: Any, labels: Any = None, *a: Any, **k: Any) -> Any:
        if labels is not None:
            labels = [tr(x) for x in labels]
        return orig_xticks(self, ticks, labels, *a, **k)

    Axes.set_yticks = yticks
    Axes.set_xticks = xticks

    orig_legend = Axes.legend

    def legend(self: Any, *a: Any, **k: Any) -> Any:
        if a and isinstance(a[0], (list, tuple)) and a[0] and isinstance(a[0][0], str):
            a = ([tr(x) for x in a[0]], *a[1:])
        elif len(a) > 1 and isinstance(a[1], (list, tuple)):
            a = (a[0], [tr(x) for x in a[1]], *a[2:])
        return orig_legend(self, *a, **k)

    Axes.legend = legend

    style.IMPL_LABEL = {k: tr(v) for k, v in style.IMPL_LABEL.items()}
    style.CASE_LABEL = {k: tr(v) for k, v in style.CASE_LABEL.items()}
    mf.label = style.label


def main() -> None:
    out = os.path.join(style.ROOT, "figures-ru")
    os.makedirs(out, exist_ok=True)
    style.FIGS = out
    mf.save.__globals__["FIGS"] = out
    patch()
    mf.main()
    print(f"[ru] figures written to {out}")


if __name__ == "__main__":
    main()
