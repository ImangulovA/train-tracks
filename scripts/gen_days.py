#!/usr/bin/env python3
"""
Daily Train Tracks — puzzle generator + uniqueness solver.

We GENERATE our own puzzles (independent build; Krazydad PDFs are used only to
calibrate grid sizes per difficulty tier — see sources/pdf/). Each puzzle is a
single self-avoiding railroad track from one border exit to another. Row/column
clues count how many cells hold a track piece. We reveal the two exit pieces plus
the MINIMUM extra given pieces needed for a provably UNIQUE solution.

Edge model: a cell's piece is defined by which of its 4 sides carry a rail
(exactly 0 or 2). Directions bitmask: N=1, E=2, S=4, W=8.

Output: app/src/lib/game/data/days.js  (DAYS map + dayIndexes/loadDay).
"""

import os
import random
import sys

N, E, S, W = 1, 2, 4, 8
DIRS = [N, E, S, W]
DELTA = {N: (-1, 0), E: (0, 1), S: (1, 0), W: (0, -1)}
OPP = {N: S, S: N, E: W, W: E}
NAME = {N: "N", E: "E", S: "S", W: "W"}
BIT = {"N": N, "E": E, "S": S, "W": W}


def mask_to_str(m):
    return "".join(NAME[d] for d in DIRS if m & d)


def str_to_mask(s):
    m = 0
    for ch in s:
        m |= BIT[ch]
    return m


# --------------------------------------------------------------------------- #
# Random puzzle (self-avoiding path between two border exits)                  #
# --------------------------------------------------------------------------- #
def border_exits(R, C, rng):
    """Pick two distinct border cells, each with an outward side."""
    cells = []
    for c in range(C):
        cells.append((0, c, N))
        cells.append((R - 1, c, S))
    for r in range(R):
        cells.append((r, 0, W))
        cells.append((r, C - 1, E))
    rng.shuffle(cells)
    a = cells[0]
    for b in cells[1:]:
        if (b[0], b[1]) != (a[0], a[1]):
            return a, b
    return cells[0], cells[1]


def random_path(R, C, rng, min_len):
    """Randomised DFS for a self-avoiding path between two border exits.

    Uses a per-attempt step budget so large grids can't explode; on overflow we
    just resample a fresh pair of exits.
    """
    for _ in range(800):
        (sr, sc, sside), (er, ec, eside) = border_exits(R, C, rng)
        start, end = (sr, sc), (er, ec)
        visited = {start}
        path = [start]
        budget = [8000]

        def dfs(cell):
            if budget[0] <= 0:
                return False
            budget[0] -= 1
            if cell == end and len(path) >= min_len:
                return True
            r, c = cell
            nbrs = []
            for d in DIRS:
                dr, dc = DELTA[d]
                nr, nc = r + dr, c + dc
                if 0 <= nr < R and 0 <= nc < C and (nr, nc) not in visited:
                    nbrs.append((nr, nc))
            rng.shuffle(nbrs)
            for nb in nbrs:
                # Don't step onto the end early (before min_len reached).
                if nb == end and len(path) + 1 < min_len:
                    continue
                visited.add(nb)
                path.append(nb)
                if dfs(nb):
                    return True
                path.pop()
                visited.discard(nb)
            return False

        if dfs(start):
            return path, (sr, sc, sside), (er, ec, eside)
    return None


def path_to_masks(path, sexit, eexit):
    """Turn an ordered cell path + the two outward exit sides into cell masks."""
    masks = {}
    for i, (r, c) in enumerate(path):
        m = 0
        if i > 0:
            pr, pc = path[i - 1]
            for d in DIRS:
                dr, dc = DELTA[d]
                if (r + dr, c + dc) == (pr, pc):
                    m |= d
        if i < len(path) - 1:
            nr, nc = path[i + 1]
            for d in DIRS:
                dr, dc = DELTA[d]
                if (r + dr, c + dc) == (nr, nc):
                    m |= d
        masks[(r, c)] = m
    # Add outward border stubs on the two endpoints.
    masks[(sexit[0], sexit[1])] |= sexit[2]
    masks[(eexit[0], eexit[1])] |= eexit[2]
    return masks


# --------------------------------------------------------------------------- #
# Solver — backtracking with row/col clue pruning; counts up to 2 solutions.   #
# --------------------------------------------------------------------------- #
class Solver:
    def __init__(self, R, C, row_clues, col_clues, exits, givens):
        self.R, self.C = R, C
        self.row_clues = row_clues
        self.col_clues = col_clues
        # exit border edges as {(r,c): outward_dir_mask}
        self.exit_mask = {}
        for (r, c, side) in exits:
            self.exit_mask[(r, c)] = self.exit_mask.get((r, c), 0) | BIT[side] if isinstance(side, str) else self.exit_mask.get((r, c), 0) | side
        self.exit_cells = {(r, c) for (r, c, _s) in exits}
        self.givens = givens  # {(r,c): mask}
        self.node_cap = 120000
        self.nodes = 0
        self.solutions = []

    def candidates(self, r, c):
        R, C = self.R, self.C
        forced = self.givens.get((r, c))
        pieces = [0] + [DIRS[i] | DIRS[j] for i in range(4) for j in range(i + 1, 4)]
        out = []
        for m in pieces:
            if forced is not None and m != forced:
                continue
            # Border rules: outward side allowed only if it is an exit.
            if r == 0 and (m & N) and not (self.exit_mask.get((r, c), 0) & N):
                continue
            if r == R - 1 and (m & S) and not (self.exit_mask.get((r, c), 0) & S):
                continue
            if c == 0 and (m & W) and not (self.exit_mask.get((r, c), 0) & W):
                continue
            if c == C - 1 and (m & E) and not (self.exit_mask.get((r, c), 0) & E):
                continue
            # An exit cell MUST carry its outward stub.
            em = self.exit_mask.get((r, c), 0)
            if em and (m & em) != em:
                continue
            out.append(m)
        return out

    def solve(self, limit=2):
        R, C = self.R, self.C
        grid = [[None] * C for _ in range(R)]
        row_cnt = [0] * R
        col_cnt = [0] * C

        def consistent(r, c, m):
            # West / North neighbours are already assigned.
            if c > 0:
                left = grid[r][c - 1]
                if bool(m & W) != bool(left & E):
                    return False
            if r > 0:
                up = grid[r - 1][c]
                if bool(m & N) != bool(up & S):
                    return False
            return True

        def bt(idx):
            if self.nodes > self.node_cap:
                return
            if len(self.solutions) >= limit:
                return
            if idx == R * C:
                if self.valid_full(grid):
                    self.solutions.append([row[:] for row in grid])
                return
            r, c = divmod(idx, C)
            self.nodes += 1
            for m in self.candidates(r, c):
                if not consistent(r, c, m):
                    continue
                nonempty = 1 if m else 0
                nr = row_cnt[r] + nonempty
                nc = col_cnt[c] + nonempty
                if nr > self.row_clues[r] or nc > self.col_clues[c]:
                    continue
                # Row lower-bound prune: enough cells left in this row?
                if c == C - 1 and nr != self.row_clues[r]:
                    continue
                cells_left_row = C - 1 - c
                if nr + cells_left_row < self.row_clues[r]:
                    continue
                # Col lower-bound prune: enough rows left below?
                rows_left = R - 1 - r
                if nc + rows_left < self.col_clues[c]:
                    continue
                grid[r][c] = m
                row_cnt[r] = nr
                col_cnt[c] = nc
                bt(idx + 1)
                row_cnt[r] = nr - nonempty
                col_cnt[c] = nc - nonempty
                grid[r][c] = None
                if len(self.solutions) >= limit:
                    return

        bt(0)
        return self.solutions

    def valid_full(self, grid):
        R, C = self.R, self.C
        # East / South border already enforced via candidates; edges consistent
        # by construction. Now enforce single connected path, no stray loops.
        parent = {}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            parent.setdefault(a, a)
            parent.setdefault(b, b)
            parent[find(a)] = find(b)

        nonempty = []
        for r in range(R):
            for c in range(C):
                if grid[r][c]:
                    nonempty.append((r, c))
                    parent.setdefault((r, c), (r, c))
                    if grid[r][c] & E:
                        union((r, c), (r, c + 1))
                    if grid[r][c] & S:
                        union((r, c), (r + 1, c))
        if not nonempty:
            return False
        roots = {find(cell) for cell in nonempty}
        if len(roots) != 1:  # a stray loop would be a second component
            return False
        # The single component must contain both exits (it will, if it's a path).
        for cell in self.exit_cells:
            if cell not in parent or find(cell) != find(nonempty[0]):
                return False
        return True


# --------------------------------------------------------------------------- #
# Logic solver — constraint propagation ONLY (forced moves, never guesses).    #
# If it fully determines the board, the puzzle is solvable WITHOUT GUESSING.   #
# Rules are all SOUND, so a completed board is the unique solution.            #
# --------------------------------------------------------------------------- #
UNK, ON, OFF = 0, 1, 2
T_UNK, T_TRACK, T_EMPTY = 0, 1, 2


class LogicSolver:
    def __init__(self, R, C, row_clues, col_clues, exits, givens):
        self.R, self.C = R, C
        self.row_clues = row_clues
        self.col_clues = col_clues
        self.contra = False
        self.cell = [[T_UNK] * C for _ in range(R)]
        # side state per (r,c,dir); border sides included (no neighbour).
        self.es = {}
        for r in range(R):
            for c in range(C):
                for d in DIRS:
                    self.es[(r, c, d)] = UNK
        # Exits first: their outward border side is ON, cell is TRACK.
        exit_sides = set()
        for (r, c, side) in exits:
            d = BIT[side] if isinstance(side, str) else side
            self.set_side(r, c, d, ON)
            self.set_cell(r, c, T_TRACK)
            exit_sides.add((r, c, d))
        # Every OTHER border side is OFF (the track can only leave at an exit).
        for r in range(R):
            for c in range(C):
                for d, edge in ((N, r == 0), (S, r == R - 1), (W, c == 0), (E, c == C - 1)):
                    if edge and (r, c, d) not in exit_sides:
                        self.set_side(r, c, d, OFF)
        # Given pieces: every side pinned per the mask; cell is TRACK.
        for cell, mask in givens.items():
            r, c = cell
            self.set_cell(r, c, T_TRACK)
            for d in DIRS:
                self.set_side(r, c, d, ON if (mask & d) else OFF)

    def set_side(self, r, c, d, val):
        cur = self.es[(r, c, d)]
        if cur != UNK and cur != val:
            self.contra = True
            return False
        changed = cur != val
        self.es[(r, c, d)] = val
        dr, dc = DELTA[d]
        nr, nc = r + dr, c + dc
        if 0 <= nr < self.R and 0 <= nc < self.C:
            k = (nr, nc, OPP[d])
            if self.es[k] != UNK and self.es[k] != val:
                self.contra = True
            self.es[k] = val
        return changed

    def set_cell(self, r, c, val):
        cur = self.cell[r][c]
        if cur != T_UNK and cur != val:
            self.contra = True
            return False
        changed = cur != val
        self.cell[r][c] = val
        return changed

    def counts(self, r, c):
        on = off = unk = 0
        for d in DIRS:
            v = self.es[(r, c, d)]
            on += v == ON
            off += v == OFF
            unk += v == UNK
        return on, off, unk

    def propagate(self):
        R, C = self.R, self.C
        changed = True
        while changed and not self.contra:
            changed = False

            # --- per-cell degree rules ---------------------------------------
            for r in range(R):
                for c in range(C):
                    on, off, unk = self.counts(r, c)
                    cst = self.cell[r][c]
                    if on >= 1 and cst != T_TRACK:
                        changed |= self.set_cell(r, c, T_TRACK)
                        cst = T_TRACK
                    if on > 2:
                        self.contra = True
                    if on + unk < 2:  # cannot reach degree 2
                        if cst == T_TRACK:
                            self.contra = True
                        else:
                            changed |= self.set_cell(r, c, T_EMPTY)
                            cst = T_EMPTY
                    if cst == T_EMPTY:
                        for d in DIRS:
                            if self.es[(r, c, d)] == UNK:
                                changed |= self.set_side(r, c, d, OFF)
                    if cst == T_TRACK:
                        if on == 2:
                            for d in DIRS:
                                if self.es[(r, c, d)] == UNK:
                                    changed |= self.set_side(r, c, d, OFF)
                        elif on + unk == 2:
                            for d in DIRS:
                                if self.es[(r, c, d)] == UNK:
                                    changed |= self.set_side(r, c, d, ON)

            # --- row / column clue saturation --------------------------------
            for r in range(R):
                tk = sum(self.cell[r][c] == T_TRACK for c in range(C))
                unkc = [c for c in range(C) if self.cell[r][c] == T_UNK]
                if tk > self.row_clues[r]:
                    self.contra = True
                elif tk == self.row_clues[r]:
                    for c in unkc:
                        changed |= self.set_cell(r, c, T_EMPTY)
                elif tk + len(unkc) == self.row_clues[r]:
                    for c in unkc:
                        changed |= self.set_cell(r, c, T_TRACK)
            for c in range(C):
                tk = sum(self.cell[r][c] == T_TRACK for r in range(R))
                unkr = [r for r in range(R) if self.cell[r][c] == T_UNK]
                if tk > self.col_clues[c]:
                    self.contra = True
                elif tk == self.col_clues[c]:
                    for r in unkr:
                        changed |= self.set_cell(r, c, T_EMPTY)
                elif tk + len(unkr) == self.col_clues[c]:
                    for r in unkr:
                        changed |= self.set_cell(r, c, T_TRACK)

            # --- anti-cycle: an UNK edge whose two cells are already linked ---
            #     by ON edges must be OFF (a loop is illegal in Train Tracks).
            parent = {}

            def find(x):
                parent.setdefault(x, x)
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            def union(a, b):
                parent[find(a)] = find(b)

            for r in range(R):
                for c in range(C):
                    if c + 1 < C and self.es[(r, c, E)] == ON:
                        union((r, c), (r, c + 1))
                    if r + 1 < R and self.es[(r, c, S)] == ON:
                        union((r, c), (r + 1, c))
            for r in range(R):
                for c in range(C):
                    if c + 1 < C and self.es[(r, c, E)] == UNK:
                        if (r, c) in parent and (r, c + 1) in parent and find((r, c)) == find((r, c + 1)):
                            changed |= self.set_side(r, c, E, OFF)
                    if r + 1 < R and self.es[(r, c, S)] == UNK:
                        if (r, c) in parent and (r + 1, c) in parent and find((r, c)) == find((r + 1, c)):
                            changed |= self.set_side(r, c, S, OFF)

        return not self.contra

    def solved(self):
        if self.contra:
            return False
        for r in range(self.R):
            for c in range(self.C):
                if self.cell[r][c] == T_UNK:
                    return False
                for d in DIRS:
                    if self.es[(r, c, d)] == UNK:
                        return False
        return True

    def as_masks(self):
        out = {}
        for r in range(self.R):
            for c in range(self.C):
                m = 0
                for d in DIRS:
                    if self.es[(r, c, d)] == ON:
                        m |= d
                out[(r, c)] = m
        return out


def logic_solve(R, C, row_clues, col_clues, exits, givens):
    """Returns (status, LogicSolver). status in {'solved','stuck','contra'}."""
    ls = LogicSolver(R, C, row_clues, col_clues, exits, givens)
    ls.propagate()
    if ls.contra:
        return "contra", ls
    return ("solved" if ls.solved() else "stuck"), ls


# --------------------------------------------------------------------------- #
# Build one puzzle of a given size, solvable by LOGIC ALONE (no guessing).     #
# --------------------------------------------------------------------------- #
def build_puzzle(R, C, seed, tier):
    rng = random.Random(seed)
    min_len = max(R, C) + (R + C) // 2
    for attempt in range(200):
        got = random_path(R, C, rng, min_len)
        if not got:
            continue
        path, sexit, eexit = got
        masks = path_to_masks(path, sexit, eexit)
        row_clues = [0] * R
        col_clues = [0] * C
        for (r, c) in path:
            row_clues[r] += 1
            col_clues[c] += 1
        exits = [sexit, eexit]

        # NO-GUESS construction: start with the two exit cells given, then reveal
        # path cells until the LOGIC solver (forced moves only) fully determines
        # the board. The result is guaranteed solvable without guessing (and,
        # since every logic rule is sound, uniquely).
        ordered_path = [cell for cell in path]  # reveal in path order for stable puzzles
        given_cells = {(sexit[0], sexit[1]), (eexit[0], eexit[1])}

        def givens_map(cells):
            return {cell: masks[cell] for cell in cells}

        ok = False
        for _iter in range(len(path) + 2):
            status, ls = logic_solve(R, C, row_clues, col_clues, exits, givens_map(given_cells))
            if status == "contra":
                break  # inconsistent (shouldn't happen) — resample
            if status == "solved":
                ok = True
                break
            # Reveal the first path cell the logic solver hasn't pinned yet.
            revealed = False
            for cell in ordered_path:
                if cell in given_cells:
                    continue
                r, c = cell
                undet = ls.cell[r][c] == T_UNK or any(ls.es[(r, c, d)] == UNK for d in DIRS)
                if undet:
                    given_cells.add(cell)
                    revealed = True
                    break
            if not revealed:
                break
        if not ok:
            continue

        # Safety net: confirm the puzzle is also globally unique via search.
        uniq = Solver(R, C, row_clues, col_clues, exits, givens_map(given_cells))
        usols = uniq.solve(limit=2)
        if len(usols) != 1:
            continue

        solution = [(r, c, mask_to_str(masks[(r, c)])) for (r, c) in path]
        givens = [(r, c, mask_to_str(masks[(r, c)])) for (r, c) in sorted(given_cells)]
        exits_out = [[sexit[0], sexit[1], NAME[sexit[2]]], [eexit[0], eexit[1], NAME[eexit[2]]]]
        return {
            "rows": R,
            "cols": C,
            "tier": tier,
            "rowClues": row_clues,
            "colClues": col_clues,
            "exits": exits_out,
            "givens": [[r, c, s] for (r, c, s) in givens],
            "solution": [[r, c, s] for (r, c, s) in solution],
        }
    raise RuntimeError(f"could not build a unique {R}x{C} puzzle at seed {seed}")


# --------------------------------------------------------------------------- #
# Emit days.js                                                                 #
# --------------------------------------------------------------------------- #
# Grid size per difficulty tier (calibrated against Krazydad tiers).
TIER_SIZE = {"beginner": 4, "easy": 5, "medium": 6, "hard": 7, "expert": 8}
# A gentle weekly ramp (index % 7): Mon..Sun.
WEEK = ["easy", "medium", "hard", "medium", "easy", "hard", "expert"]


def tier_for(idx):
    if idx < 0:
        return "beginner"
    return WEEK[idx % 7]


def js_day(blob):
    def arr(a):
        return "[" + ",".join(str(x) for x in a) + "]"

    def cells(key):
        return "[" + ",".join(f'[{r},{c},"{s}"]' for (r, c, s) in blob[key]) + "]"

    parts = [
        f'rows:{blob["rows"]}',
        f'cols:{blob["cols"]}',
        f'tier:"{blob["tier"]}"',
        f'rowClues:{arr(blob["rowClues"])}',
        f'colClues:{arr(blob["colClues"])}',
        f"exits:{cells('exits')}",
        f"givens:{cells('givens')}",
        f"solution:{cells('solution')}",
    ]
    return "{" + ",".join(parts) + "}"


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else -1
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "app", "src", "lib", "game", "data", "days.js")
    out = os.path.normpath(out)

    entries = []
    for idx in range(lo, hi + 1):
        tier = tier_for(idx)
        size = TIER_SIZE[tier]
        blob = build_puzzle(size, size, seed=1000 + idx, tier=tier)
        entries.append((idx, blob))
        print(f"day {idx:>3}  {tier:<8} {size}x{size}  givens={len(blob['givens'])}  track={len(blob['solution'])}")

    lines = [
        "// AUTO-GENERATED by scripts/gen_days.py — do not hand-edit.",
        "// Daily Train Tracks puzzles (independent build). Each cell piece is",
        "// encoded by the rail sides it carries: N/E/S/W. See gen_days.py.",
        "export const DAYS = {",
    ]
    for idx, blob in entries:
        lines.append(f'  "{idx}": {js_day(blob)},')
    lines.append("};")
    lines.append("")
    lines.append("export function dayIndexes() { return Object.keys(DAYS).map(Number); }")
    lines.append("export function loadDay(idx) { return DAYS[idx] ?? null; }")
    lines.append("")
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"\nwrote {out}  ({len(entries)} days)")


if __name__ == "__main__":
    main()
