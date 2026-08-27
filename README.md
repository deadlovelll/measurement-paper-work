# Python under load — measurement artifact

Code, data and paper for a measurement study of Python optimisation: compute-bound loops,
branchy and allocation-heavy code, object-oriented workloads, alternative runtimes, threads,
and the build of the interpreter itself. Every claim in the paper has code, raw data and a
figure produced here.

Two properties are worth knowing before reading anything else.

**All timing is [pyperf](https://github.com/psf/pyperf).** Nothing in this repository
implements calibration, sampling or statistics. `bench/harness/mp_pyperf.py` is a thin layer
that adds the metadata a figure needs, forwards our command-line flags into pyperf's worker
processes, and runs a correctness gate before a variant is allowed to be timed. A benchmark is
a median over 60 values from 20 independent worker processes; "these two are the same" is
pyperf's significance test, not two rounded numbers.

**One interpreter provenance.** Every CPython in the paper is compiled by
`bench/build_uniform.sh` from a release tarball with one compiler and one literally identical
configure line. No packaged interpreter contributes a number.

```
paper/                      paper.tex     + tables/    + sections/    -> paper.pdf     (EN)
                            paper-ru.tex  + tables-ru/ + sections-ru/ -> paper-ru.pdf  (RU)
bench/
  harness/mp_pyperf.py      the pyperf layer: metadata, flag forwarding, correctness gate
  host_topology.sh          CPU classes -> affinity masks + results/host.json
  check_provenance.py       gate: all six interpreters share one configure line
  build_everything.sh       every build in dependency order, then the three gates
  build_uniform.sh          compiles every interpreter: 3.10-3.14 + free-threaded, one line
  setup_env.sh              venvs on those interpreters, with numpy/cython/numba/pybind11
  build_all.sh              Cython/pybind11/Codon/C (6 flag sets + the accumulator ladder)/Rust
                            needs CODON_DIR for the Codon modules and PYPY for the PyPy ones
  run_campaign.sh           the whole measurement campaign, one phase at a time
  prettify_results.py       re-indent the result files pyperf writes on one line;
                            run it after a campaign, it is lossless and checks that
  b1_compute/               compute-bound kernels; run_flags.py + codegen_diff.sh (flags);
                            breakeven.py (JIT break-even vs input size)
  b2_branchy/               branchy / allocating / pointer-chasing kernels
  b3_runtime/               the runtime operation suite, start-up, specialisation warm-up
  b4_threads/               thread scaling: GIL, free-threaded, free-threaded with GIL on
  b5_buildflags/            build_real.sh: seven configurations of one 3.14.6 source tree
  b6_cinderx/               build_cinderx.sh: stock + the meta/3.14 fork + CinderX, natively,
                            in both ENABLE_ADAPTIVE_STATIC_PYTHON configurations
  b7_pipeline/              end-to-end mixed pipeline, techniques stacked
  native_rs/                Rust kernels (cdylib, called through ctypes)
  plots/                    pyperf_load.py    pyperf JSON -> the shape figures consume
                            make_figures.py / make_tables.py / summarize.py   (English)
                            make_figures_ru.py / make_tables_ru.py            (same numbers)
                            check_overlaps.py the layout gate: no text on top of text
                            verify_campaign.py  drift, dispersion, two-pass agreement, verdicts
                            phantom.py          no traces of an absent document
results/pyperf/             pyperf result files, plus a .facts.json sidecar per suite
results/codegen_identity.json   hashed disassembly of every compiler-flag variant
figures/  figures-ru/       generated PDF+PNG figures
cinderx-workshop/           the Cinder/CinderX bring-up tree used by the CinderX section
```

## Reproducing

Everything is built and measured on one machine, including Cinder and CinderX. There is no
container and no second platform.

```bash
# 0. the host: CPU classes, affinity masks, and a machine description for the paper's table.
#    Writes bench/affinity.txt, bench/affinity-threads.txt and results/host.json.
bash bench/host_topology.sh

#    Measurement quality is decided here, and this part needs root:
sudo sh -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
                echo performance > $g; done
            echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo'
#    Note what is deliberately NOT done: address-space randomisation stays on. The argument for
#    measuring across many processes is that layout and allocator state differ between them.

# 1..5, in dependency order, one at a time -- or run bench/build_everything.sh, which does all
#      five and then the gates:
ROOT_OUT=$HOME/mp-x86 bash bench/build_everything.sh

#      equivalently, by hand:
OUT=$HOME/mp-x86/uniform    bash bench/build_uniform.sh          # 3.10-3.14 + free-threaded, PGO
UNIFORM=$HOME/mp-x86/uniform \
                            bash bench/setup_env.sh              # venvs + pyperf. build_all.sh
                                                                 # builds into these venvs, so
                                                                 # this comes before it
CODON_DIR=<codon> PYPY=$HOME/mp-x86/pypy/bin/pypy3 \
                            bash bench/build_all.sh              # Cython, pybind11, Codon,
                                                                 # C (6 flag sets + ladder), Rust
OUT=$HOME/mp-x86/realbuilds LLVM19=$HOME/.local/llvm19/bin \
                            bash bench/b5_buildflags/build_real.sh   # seven build configs; the
                                                                     # tier-2 JIT one needs LLVM 19
REAL=$HOME/mp-x86/realbuilds \
                            bash bench/setup_env.sh              # and again for those seven:
                                                                 # they are built without pip,
                                                                 # so this pass has to follow
                                                                 # build_real.sh
OUT=$HOME/mp-x86/cinder     bash bench/b6_cinderx/build_cinderx.sh   # stock + fork + CinderX x2

# 6. gates, before anything is measured
python3 bench/check_provenance.py $HOME/mp-x86/uniform            # must PASS: one configure line
python3 bench/check_provenance.py $HOME/mp-x86/realbuilds --expect-differences
bash bench/b1_compute/codegen_diff.sh                             # which flags change the code
bash bench/b2_branchy/codegen_check.sh                            # C vs Rust instruction counts,
                                                                  # which table 6 is built from

# 7. the campaign. Phases run one at a time on purpose, and the machine must be otherwise idle:
#    a background job that only touches other cores is still visible in a parallel benchmark.
UNIFORM=$HOME/mp-x86/uniform REAL=$HOME/mp-x86/realbuilds \
CINDER=$HOME/mp-x86/cinder   PYPY=$HOME/mp-x86/pypy/bin/pypy3 \
    bash bench/run_campaign.sh
#    or a phase at a time: compute branchy versions spec threads builds pipeline cinderx pypy

#    the cinderx phase covers only run_b6_native.sh; two more sets are separate commands:
CINDER=$HOME/mp-x86/cinder bash bench/b6_cinderx/run_jitopts.sh         # JIT-option ablation
$HOME/mp-x86/cinder/venv-cinder-adaptive/bin/python \
    bench/b6_cinderx/run_gc_scale.py --label ...                        # collector sweep

# 8. does the data deserve to reach the paper?
bench/venvs/u313/bin/python bench/plots/verify_campaign.py   # drift, dispersion, two-pass
                                                             # agreement, every non-ok verdict

# 9. the paper
bench/venvs/u313/bin/python bench/plots/make_figures.py     # figures/     (EN)
bench/venvs/u313/bin/python bench/plots/make_tables.py      # tables/      (EN)
bench/venvs/u313/bin/python bench/plots/make_figures_ru.py  # figures-ru/  (RU)
bench/venvs/u313/bin/python bench/plots/make_tables_ru.py   # tables-ru/   (RU)
bench/venvs/u313/bin/python bench/plots/check_overlaps.py        # layout gate, must exit 0
bench/venvs/u313/bin/python bench/plots/check_overlaps.py --ru   # and in Russian
bench/venvs/u313/bin/python bench/plots/phantom.py          # no traces of an absent document
bench/venvs/u313/bin/python bench/plots/check_parity.py     # every number in both languages
bench/venvs/u313/bin/python bench/plots/check_seams.py      # doubled words, case, stray $
bench/venvs/u313/bin/python bench/plots/check_biblio.py --online   # authors, years, URLs
bench/venvs/u313/bin/python bench/plots/check_tables.py     # EN/RU cells, positional refs
bench/venvs/u313/bin/python bench/plots/check_protocol.py   # what the method section claims
bench/venvs/u313/bin/python bench/plots/check_meas.py       # each number vs the run it names
#    or all of the above at once:
UNIFORM=$HOME/mp-x86/uniform BIBLIO_ONLINE=1 bash bench/check_paper.sh
bench/venvs/u313/bin/python bench/plots/summarize.py        # every number quoted in the text
cd paper && tectonic -X compile paper.tex && tectonic -X compile paper-ru.tex
```

## Measurement protocol (short version)

* **pyperf owns the timing.** Loop count calibrated until one value takes ≥100 ms; 20 worker
  processes per benchmark, each discarding a warm-up value and keeping three. Process-level
  repetition is the point: address-space layout, allocator state, hash seed and code layout
  differ per process, and an in-process timer's dispersion figure contains none of them.
* **Heavy suites use fewer processes** (10, and 5 for thread scaling, where one value is a
  full multi-second run). The count is recorded with every result.
* **Setup is never timed.** Anything that consumes or mutates its input is registered through
  `bench_time_func`, where the rebuild happens outside the timed region; whole-process costs
  (start-up, import latency) go through `bench_command`.
* **Correctness gate.** An implementation is timed only after it reproduces the pure-Python
  reference at full problem size. `fastmath` variants get a 1e-3 tolerance and the deviation
  that actually occurred is recorded. Failures are written to the sidecar as results.
* **Machine drift.** This host is a fanless laptop and loses speed under sustained load.
  pyperf's worker processes spread each benchmark's samples across the whole run rather than
  taking them consecutively; on top of that every suite registers a *machine probe* — a fixed
  native loop through `ctypes`, timed like any other benchmark — so drift between two runs can
  be tested rather than assumed.
* **"No difference" is a test.** Two configurations quoted as equal come with pyperf's
  significance test. Where the disassembly says two variants are the same program
  (`results/codegen_identity.json`), `bench/b1_compute/ab_flags.sh` measures them alternately,
  because pyperf runs benchmarks one after another and a slow drift between them would
  otherwise look like an effect.

## Result files

`results/pyperf/<suite>-<configuration>.json` is pyperf's own format; read it with
`pyperf stats`, `pyperf compare_to`, or `bench/plots/pyperf_load.py`. Each benchmark carries
`mp_suite`, `mp_case`, `mp_impl`, `mp_label`, `mp_params` and `mp_note` in its metadata.

`results/pyperf/<suite>-<configuration>.facts.json` is the sidecar: the correctness verdicts,
the variants that could not be built or gave a wrong answer, the host description, and the
structural observations that are **not** timings — allocator blocks per instance, refcounts of
the common singletons, peak RSS, how many module bodies a lazy import left unexecuted. They
live there so that nothing which was not measured by pyperf can be mistaken for something that
was.

Non-`ok` statuses are themselves results: `unsupported` (the technology cannot express the
kernel — for instance a typing failure), `wrong_result`, `unavailable`, `failed`. The paper
reports them rather than dropping them.
