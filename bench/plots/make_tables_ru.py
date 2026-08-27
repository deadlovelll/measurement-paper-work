#!/usr/bin/env python
"""Russian-language rendering of the generated LaTeX tables, from the same result files."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import make_figures_ru as fru
import make_tables as mt
import style

SUBS = [
    (r"implementation & ms & $\times$ & ms & $\times$ & ms & $\times$",
     r"реализация & мс & $\times$ & мс & $\times$ & мс & $\times$"),
    (r"array sum ($10^6$ f64)", r"сумма массива ($10^6$ f64)"),
    (r"mandelbrot $200{\times}150$", r"мандельброт $200{\times}150$"),
    (r"matmul $96{\times}96$", r"matmul $96{\times}96$"),
    (r"tokenize ($2{\cdot}10^6$ B)", r"токенизация ($2{\cdot}10^6$ Б)"),
    (r"binary trees (d{=}18)", r"бинарные деревья (d{=}18)"),
    (r"BFS ($5{\cdot}10^5$ nodes)", r"BFS ($5{\cdot}10^5$ узлов)"),
    (r"platform & hardware & operating system", r"платформа & оборудование & ОС"),
    (r"component & version", r"компонент & версия"),
    (r"C compiler", r"компилятор C"),
    (r"LLVM, for the tier-2 JIT build", r"LLVM, для сборки с tier-2 JIT"),
    (r"capability & verdict & measurement", r"возможность & итог & измерение"),
    (r"tokenize kernel & instructions & cond.\ branches & cond.\ selects & ms",
     r"ядро токенизации & инструкций & условных переходов & условных пересылок & мс"),
    (r"Disassembled on ", r"Дизассемблировано на "),
    (r"; the branch and select mnemonics counted are recorded in",
     r". Подсчитываемые мнемоники переходов и пересылок записаны в"),
    (r"; no effect under the JIT", r", под JIT эффекта нет"),
    (r"all 8 kernel functions, compiled at the JIT's own threshold and verified to be what runs",
     r"все 8 функций ядер, скомпилированы по собственному порогу JIT, с проверкой, что "
     r"исполняются именно они"),
    (r"small cost", r"малая цена"),
    (r"small gain", r"малый выигрыш"),
    (r"no effect here", r"нет эффекта здесь"),
    (r"no effect", r"нет эффекта"),
    (r"not measured", r"не измерялось"),
    (r"& no ", r"& нет "),
    (r"& no\\", r"& нет\\"),
    (r"property & ", r"свойство & "),
    (r"None is immortal", r"None бессмертен"),
    (r"alloc.\ blocks / instance (dict)", r"блоков аллокатора / объект (dict)"),
    (r"alloc.\ blocks / instance (slots)", r"блоков аллокатора / объект (slots)"),
    (r"max RSS after suite, MB", r"макс. RSS после набора, МБ"),
    (r"bare startup, ms", r"чистый запуск, мс"),
    (r"max RSS after suite\, MB", r"макс. RSS после набора\, МБ"),
    (r"bare startup\, ms", r"чистый запуск\, мс"),
    (r"property & value", r"свойство & значение"),
    (r"свойство & value", r"свойство & значение"),
    (r"performance + ", r"производительных + "),
    (r" efficiency cores", r" энергоэффективных ядер"),
    (r" GB", r"\,ГБ"),
    (r"CPUs 0", r"процессоры 0"),
    (r"0 errors in both configurations, with the patches carried in the vendored tree",
     r"0 ошибок в обеих конфигурациях, с патчами, которые несёт приложенное дерево"),
    (r"all 8 kernel functions force-compiled",
     r"все 8 функций ядер скомпилированы принудительно"),
    (r"operating system", r"операционная система"),
    (r"frequency scaling", r"управление частотой"),
    (r"address randomisation", r"рандомизация адресов"),
    (r"benchmark affinity", r"привязка бенчмарков к ядрам"),
    (r"Full randomization", r"полная"),
    (r"governor performance, turbo off", r"governor performance, турбо выключено"),
    (r"(the performance class)", r"(класс производительных ядер)"),
    (r"memory", r"память"),
    (r"cores &", r"ядра &"),
    (r"builds on Linux x86\_64", r"собирается на Linux x86\_64"),
    (r"builds on Linux aarch64", r"собирается на Linux aarch64"),
    (r"JIT compiles \& is correct", r"JIT компилирует и даёт верный результат"),
    (r"JIT on unmodified Python", r"JIT на неизменённом Python"),
    (r"CinderX runtime, no JIT", r"рантайм CinderX без JIT"),
    (r"Static Python + JIT", r"Static Python + JIT"),
    (r"Static Python, interpreter", r"Static Python, интерпретатор"),
    (r"lazy imports", r"ленивые импорты"),
    (r"parallel GC", r"параллельный GC"),
    (r"lightweight frames", r"облегчённые фреймы"),
    (r"all 8 kernel functions force-compiled",
     r"все 8 функций ядер скомпилированы принудительно"),
    (r"runtime / JIT, adaptive off", r"рантайм / JIT, адаптивный выключен"),
    (r"runtime / JIT, adaptive on", r"рантайм / JIT, адаптивный включён"),
    (r"adaptive specialisation, once completed",
     r"адаптивная специализация, после доработки"),
    (r"static interpreter", r"статический интерпретатор"),
    (r"; no effect under the JIT", r", под JIT эффекта нет"),
    (r"$\times$ serial at ", r"$\times$ от последовательного при "),
    (r"k objects, ", r"\,тыс. объектов, "),
    (r"$\times$ at ", r"$\times$ при "),
    (r" the stock time", r" времени обычной сборки"),
    (r" the stock run time", r" времени обычной сборки"),
    (r"faster than the same kernel boxed under the same JIT",
     r"быстрее того же ядра с объектами под тем же JIT"),
    (r"on the slow layout mode", r"на медленном режиме раскладки"),
    (r"compiled at the JIT's own threshold and verified to be what runs",
     r"скомпилированы по собственному порогу JIT, с проверкой, что исполняются именно они"),
    (r"CinderX runtime, no JIT", r"рантайм CinderX без JIT"),
    (r"CinderX JIT on untyped code", r"JIT CinderX на нетипизированном коде"),
    (r"same, adaptive configuration", r"то же, адаптивная конфигурация"),
    (r" over the six", r" по шести ядрам"),
    (r"faster than boxed Python", r"быстрее Python с объектами"),
    (r"slower than boxed Python", r"медленнее Python с объектами"),
    (r"$\mu$s; 0/200 module bodies run; first use",
     r"$\mu$s, 0/200 тел модулей исполнено, первое обращение"),
    (r"200-deep call chain", r"цепочка вызовов глубиной 200"),
    (r"no effect here", r"нет эффекта здесь"),
    (r"not measured", r"не измерено"),
    (r"not built", r"не собрано"),
    (r"composition-dependent", r"зависит от состава кучи"),
    (r"gain when heap hidden", r"выигрыш, когда куча скрыта"),
    (r"$\times$ serial with the state visible",
     r"$\times$ от последовательного при видимом состоянии"),
    (r"$\times$ after immortalising it", r"$\times$ после её иммортализации"),
    (r"ms serial)", r"мс последовательно)"),
    (r"& cost &", r"& цена &"),
    (r" stock", r" обычной сборки"),
    (r"regression", r"регрессия"),
    (r"no effect", r"нет эффекта"),
    (r"win", r"выигрыш"),
    (r"yes", r"да"),
    (r"C, clang -O3 -mcpu=native", r"C, clang -O3 -mcpu=native"),
    (r"Rust, rustc -O3 target-cpu=native", r"Rust, rustc -O3 target-cpu=native"),
]


UNITS = [(r"\,ms", r"\,мс"), (r"\,$\mu$s", r"\,мкс"), (r"\,GB", r"\,ГБ"),
         (r"\,MB", r"\,МБ"), (r"\,ns", r"\,нс"), (r"$\mu$s", r"мкс")]


def translate(body: str) -> str:
    for a, b in SUBS:
        body = body.replace(a, b)
    for a, b in UNITS:
        body = body.replace(a, b)
    return body


def main() -> None:
    out = os.path.join(style.ROOT, "paper", "tables-ru")
    os.makedirs(out, exist_ok=True)
    mt.TABLES = out
    style.IMPL_LABEL = {k: fru.tr(v) for k, v in style.IMPL_LABEL.items()}
    style.CASE_LABEL = {k: fru.tr(v) for k, v in style.CASE_LABEL.items()}
    mt.label = style.label

    def w(name: str, body: str) -> None:
        path = os.path.join(out, name)
        with open(path, "w") as fh:
            fh.write(translate(body).rstrip() + "\n")
        print(f"[tab-ru] {name}")

    mt.w = w  # ty: ignore[invalid-assignment]
    mt.main()
    print(f"[ru] tables written to {out}")


if __name__ == "__main__":
    main()
