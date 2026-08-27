#!/usr/bin/env python3
"""Re-indent the result files pyperf writes on one line, so a person can read them.

pyperf dumps a suite as a single line; the sidecars this artifact writes itself use indent=1.
This brings the two into one style. It is lossless -- the parsed object is compared before and
after and the file is only rewritten if they match -- and it costs about 40 % more disk.

Run it after a campaign: pyperf writes compact again every time.

    python3 bench/prettify_results.py            # results/, in place
    python3 bench/prettify_results.py --check    # report what is compact, change nothing
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fingerprint(data: object) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="list the compact files without rewriting them")
    parser.add_argument("--indent", type=int, default=1,
                        help="indent width, matching the sidecars (default 1)")
    args = parser.parse_args()

    compact = []
    for path in sorted(glob.glob(os.path.join(ROOT, "results", "**", "*.json"), recursive=True)):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if text.count("\n") <= 5:
            compact.append((path, text))

    if not compact:
        print("every result file is already indented")
        return 0

    if args.check:
        total = sum(len(text) for _p, text in compact)
        for path, text in compact:
            print(f"  {len(text) / 1024:8.1f} KB  {os.path.relpath(path, ROOT)}")
        print(f"\n{len(compact)} file(s) on one line, {total / 1024 / 1024:.1f} MB")
        return len(compact)

    changed = 0
    before = after = 0
    for path, text in compact:
        data = json.loads(text)
        want = fingerprint(data)
        pretty = json.dumps(data, indent=args.indent, ensure_ascii=False) + "\n"
        if fingerprint(json.loads(pretty)) != want:
            print(f"  SKIPPED {os.path.relpath(path, ROOT)}: re-indenting would change the data")
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(pretty)
        changed += 1
        before += len(text)
        after += len(pretty)

    print(f"re-indented {changed} of {len(compact)} file(s), "
          f"{before / 1024 / 1024:.1f} MB -> {after / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
