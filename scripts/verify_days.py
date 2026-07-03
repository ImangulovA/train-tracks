#!/usr/bin/env python3
"""Independent check: every generated day has EXACTLY ONE solution and it equals
the stored `solution`. Also checks clue/solution consistency and piece validity."""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_days import Solver, logic_solve, str_to_mask, mask_to_str  # noqa: E402


def load_days():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "app", "src", "lib", "game", "data", "days.js"))
    txt = open(path).read()
    # Grab the DAYS object body and turn the JS literal into JSON.
    body = txt.split("export const DAYS = ", 1)[1]
    body = body.split("\n};", 1)[0] + "\n}"
    body = re.sub(r"([{,])(\w+):", r'\1"\2":', body)  # quote bare keys
    body = re.sub(r",(\s*[}\]])", r"\1", body)  # drop trailing commas
    return json.loads(body)


def main():
    days = load_days()
    bad = 0
    for key in sorted(days, key=lambda k: int(k)):
        d = days[key]
        R, C = d["rows"], d["cols"]
        exits = [(r, c, s) for (r, c, s) in d["exits"]]
        givens = {(r, c): str_to_mask(s) for (r, c, s) in d["givens"]}

        # clue vs solution
        rc = [0] * R
        cc = [0] * C
        sol_mask = {}
        deg_ok = True
        for (r, c, s) in d["solution"]:
            rc[r] += 1
            cc[c] += 1
            sol_mask[(r, c)] = str_to_mask(s)
            if len(s) != 2:
                deg_ok = False
        clue_ok = rc == d["rowClues"] and cc == d["colClues"]

        solver = Solver(R, C, d["rowClues"], d["colClues"], exits, givens)
        sols = solver.solve(limit=3)
        n = len(sols)

        # compare unique solution to stored one
        match = False
        if n == 1:
            g = sols[0]
            match = True
            for r in range(R):
                for c in range(C):
                    if (g[r][c] or 0) != sol_mask.get((r, c), 0):
                        match = False

        # NO-GUESS: logic propagation alone must fully solve from the givens.
        lstatus, ls = logic_solve(R, C, d["rowClues"], d["colClues"], exits, givens)
        lmasks = ls.as_masks()
        noguess = lstatus == "solved" and all(
            lmasks.get((r, c), 0) == sol_mask.get((r, c), 0) for (r, c) in sol_mask
        )

        good = n == 1 and match and clue_ok and deg_ok and noguess
        status = "OK" if good else "FAIL"
        if not good:
            bad += 1
        print(
            f"day {int(key):>3} {d['tier']:<8} {R}x{C}  sols={n} match={match} "
            f"clue={clue_ok} deg2={deg_ok} noguess={noguess}  -> {status}"
        )
    print(f"\n{'ALL OK' if bad == 0 else str(bad) + ' FAILED'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
