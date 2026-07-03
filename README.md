# Daily Train Tracks 🚂

A **one-puzzle-a-day** Train Tracks game: connect the two border pieces with a
single railroad line that never forks or crosses itself. The numbers above each
column and beside each row count how many cells hold a piece of track. Every
puzzle has a **unique solution reachable by pure logic — no guessing**.

Play daily, keep a streak, share your time. Built on a small reusable daily-game
platform (routing, timer, archive, personal stats, share loop, optional global
stats). See **[docs/GAME_CONTRACT.md](docs/GAME_CONTRACT.md)** for how the puzzle
plugs into the platform.

## How to play

- **Desktop:** left-click **drag** across cells to lay rails; **right-click** (or
  drag) to mark a cell empty (✖). Dragging over an existing rail erases it.
- **Mobile:** **drag** to lay rails; toggle the **🚆 Rails / ✖ Empty** tool for
  bulk marking; **long-press** a cell for a quick ✖.
- The piece shape (straight or curve) is inferred from the connections you draw.
- Column/row numbers turn **green** when satisfied, **red** when exceeded.

## Quick start

```bash
cd app
export PATH="$HOME/.local/node/bin:$PATH"   # node is not system-wide here
npm install
npm run dev -- --port 5174                  # http://localhost:5174
```

Author mode (play unreleased days): `?unlock=railyard&day=N`.

## Puzzles: generated, verified, no-guess

Puzzles are **generated**, not scraped — see [CREDITS.md](CREDITS.md).

```bash
python3 scripts/gen_days.py -1 40   # write app/src/lib/game/data/days.js
python3 scripts/verify_days.py      # gate: unique + matches + no-guess (logic-solvable)
python3 scripts/preview_day.py 6    # render a day to /tmp for visual QA
```

- **gen_days.py** — random self-avoiding track between two border exits → row/col
  clues → reveal the minimum given pieces so a constraint-propagation solver
  (forced moves only) fully solves the board. Grid size per tier: beginner 4,
  easy 5, medium 6, hard 7, expert 8; a weekly difficulty ramp.
- **verify_days.py** — independent gate: every day must have exactly one solution,
  match the stored solution, have consistent clues, and be **solvable by logic
  alone (no guessing)**.

## Deploy

Push to `main`: `.github/workflows/deploy.yml` builds and publishes to GitHub
Pages (enable Pages → Source: **GitHub Actions** once, in repo Settings). The
Krazydad reference PDFs in `sources/` are **git-ignored** (not republished).

Optional global stats: see [backend/README.md](backend/README.md), then paste the
Worker URL into `app/src/lib/config.js`.
