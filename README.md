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
  bootstrap.sh              one command: bare machine -> toolchains -> builds -> campaign
                            -> figures -> both PDFs -> every gate. --check/--deps/--build/
                            --measure/--paper stop it earlier. Pins every version.
  tune_machine.sh           performance governor and turbo off, and back again afterwards
  check_paper.sh            all thirteen paper gates in one run
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
bash bench/bootstrap.sh
```

That is the whole thing: it fetches the toolchains at the versions the published numbers were
measured on, builds every interpreter and native artifact, sets the governor, runs the campaign,
draws the figures and tables, compiles both PDFs and finishes with the gates. Stop it earlier
with `--check` (inventory only, installs nothing), `--deps`, `--build` or `--measure`. Every
stage is idempotent, so a stage that dies part way can be re-run.

Two things to know before starting it. The campaign takes **hours**, and the machine must be
otherwise idle for that whole time — a background job that only touches other cores is still
visible in a parallel benchmark. And run **one** of it: two campaigns write to the same result
files and contend for the same pinned cores, so both sets of numbers are worthless.

Address-space randomisation is deliberately left on: the argument for measuring across many
processes is that layout, allocator state, hash seed and code layout differ between them, and
pinning the layout would remove exactly the variation the protocol is built to sample.

`bench/` holds every step it runs as a separate script, should you want to drive one directly;
`bash bench/bootstrap.sh --check` lists what the machine already has without installing
anything.

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
