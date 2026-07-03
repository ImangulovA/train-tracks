<script>
  // ===========================================================================
  // DAILY TRAIN TRACKS — puzzle UI.
  //
  // Connect the two border exit pieces with a single railroad track that does
  // not fork or cross itself. The numbers on the top/right count how many cells
  // hold a track piece in that column/row. Unique solution, no guessing.
  //
  // EDGE MODEL: a cell's piece is defined by which of its 4 sides carry a rail.
  // The player lays rails by dragging across adjacent cells (the piece shape —
  // straight or curve — is inferred from the connections). "Empty" marks (✖)
  // are cell-level annotations that help deduction.
  //
  // INPUT
  //   Desktop: left-drag = lay/erase rail · right-click/drag = ✖ empty
  //   Mobile : drag = lay/erase rail in current mode · long-press = quick ✖
  //            mode toggle (🚆 Rails / ✖ Empty) for bulk marking
  //
  // CONTRACT (see docs/GAME_CONTRACT.md): props puzzle/dayIdx/saved; callbacks
  // onstart() once, onprogress(state) on change, onfinish(result) once.
  // ===========================================================================
  import { onMount } from 'svelte';

  let { puzzle, dayIdx, saved = null, onstart, onprogress, onfinish } = $props();

  const R = puzzle.rows;
  const C = puzzle.cols;

  // --- edge keys ------------------------------------------------------------
  // Interior connection between adjacent cells, canonicalised:
  //   horizontal (r,c)-(r,c+1) => `H,r,c`   vertical (r,c)-(r+1,c) => `V,r,c`
  const edgeKey = (r, c, dir) => {
    if (dir === 'E') return `H,${r},${c}`;
    if (dir === 'W') return `H,${r},${c - 1}`;
    if (dir === 'S') return `V,${r},${c}`;
    if (dir === 'N') return `V,${r - 1},${c}`;
  };
  const between = (a, b) => {
    if (a.r === b.r && b.c === a.c + 1) return `H,${a.r},${a.c}`;
    if (a.r === b.r && b.c === a.c - 1) return `H,${a.r},${a.c - 1}`;
    if (a.c === b.c && b.r === a.r + 1) return `V,${a.r},${a.c}`;
    if (a.c === b.c && b.r === a.r - 1) return `V,${a.r - 1},${a.c}`;
    return null;
  };

  // --- derive locked edges, border stubs, and the solution ------------------
  const lockedEdges = new Set(); // interior edges fixed by given pieces
  const borderStubs = new Map(); // "r,c" -> Set of outward dirs (entrance/exit)
  const inGrid = (r, c) => r >= 0 && r < R && c >= 0 && c < C;

  for (const [r, c, side] of puzzle.exits) {
    const k = `${r},${c}`;
    if (!borderStubs.has(k)) borderStubs.set(k, new Set());
    borderStubs.get(k).add(side);
  }
  for (const [r, c, dirs] of puzzle.givens) {
    for (const d of dirs) {
      const dr = d === 'N' ? -1 : d === 'S' ? 1 : 0;
      const dc = d === 'W' ? -1 : d === 'E' ? 1 : 0;
      if (inGrid(r + dr, c + dc)) lockedEdges.add(edgeKey(r, c, d));
    }
  }
  const solutionEdges = new Set();
  for (const [r, c, dirs] of puzzle.solution) {
    for (const d of dirs) {
      const dr = d === 'N' ? -1 : d === 'S' ? 1 : 0;
      const dc = d === 'W' ? -1 : d === 'E' ? 1 : 0;
      if (inGrid(r + dr, c + dc)) solutionEdges.add(edgeKey(r, c, d));
    }
  }

  // --- mutable state --------------------------------------------------------
  let edges = new Set(saved?.edges ?? []); // ON interior edges
  for (const e of lockedEdges) edges.add(e); // givens always present
  let blocked = new Set(saved?.blocked ?? []); // "r,c" cells marked empty
  let mode = $state('rail'); // 'rail' | 'empty' (mobile toggle / current tool)
  let done = $state(saved?.done ?? false);
  let rowCount = $state(new Array(R).fill(0));
  let colCount = $state(new Array(C).fill(0));
  let canUndo = $state(false);
  let history = []; // stroke snapshots for undo
  let startedOnce = false;

  // --- geometry -------------------------------------------------------------
  let wrap; // container div
  let canvas;
  let ctx;
  let cell = 40;
  let originX = 0;
  let originY = 0;
  let accent = '#e5484d';

  function layout(cssW) {
    // Reserve space: top for column clues, right for row clues, small pads for
    // exit stubs on all sides.
    cell = Math.max(30, Math.min(64, Math.floor(cssW / (C + 1.8))));
    originX = Math.round(cell * 0.55);
    originY = Math.round(cell * 1.0);
    const w = originX + C * cell + Math.round(cell * 1.1);
    const h = originY + R * cell + Math.round(cell * 0.55);
    return { w, h };
  }

  function fit() {
    if (!wrap || !canvas) return;
    const cssW = Math.min(wrap.clientWidth, 560);
    const { w, h } = layout(cssW);
    const dpr = window.devicePixelRatio || 1;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    accent = getComputedStyle(canvas).getPropertyValue('--accent').trim() || '#e5484d';
    draw();
  }

  // --- helpers over current state ------------------------------------------
  function cellDirs(r, c) {
    // dirs (incl. border stubs) currently drawn at this cell
    const out = [];
    for (const d of ['N', 'E', 'S', 'W']) {
      const dr = d === 'N' ? -1 : d === 'S' ? 1 : 0;
      const dc = d === 'W' ? -1 : d === 'E' ? 1 : 0;
      if (inGrid(r + dr, c + dc)) {
        if (edges.has(edgeKey(r, c, d))) out.push(d);
      }
    }
    const stubs = borderStubs.get(`${r},${c}`);
    if (stubs) for (const d of stubs) out.push(d);
    return out;
  }

  function recount() {
    const rc = new Array(R).fill(0);
    const cc = new Array(C).fill(0);
    for (let r = 0; r < R; r++)
      for (let c = 0; c < C; c++) {
        if (cellDirs(r, c).length > 0) {
          rc[r]++;
          cc[c]++;
        }
      }
    rowCount = rc;
    colCount = cc;
  }

  function isWin() {
    if (edges.size !== solutionEdges.size) return false;
    for (const e of edges) if (!solutionEdges.has(e)) return false;
    return true;
  }

  // --- mutation -------------------------------------------------------------
  function firstTouch() {
    if (!startedOnce) {
      startedOnce = true;
      onstart?.();
    }
  }

  function pushHistory() {
    history.push({ edges: new Set(edges), blocked: new Set(blocked) });
    if (history.length > 200) history.shift();
    canUndo = true;
  }

  function commit() {
    recount();
    onprogress?.({ edges: [...edges], blocked: [...blocked], done });
    if (!done && isWin()) {
      done = true;
      const track = puzzle.solution.length;
      onfinish?.({ won: true, tier: puzzle.tier, size: `${R}×${C}`, track });
    }
    draw();
  }

  function toggleEdge(a, b, forceState) {
    const k = between(a, b);
    if (!k || lockedEdges.has(k)) return;
    const on = edges.has(k);
    const target = forceState === undefined ? !on : forceState;
    if (target === on) return;
    if (target) {
      edges.add(k);
      // laying a rail clears "empty" marks on both endpoints
      blocked.delete(`${a.r},${a.c}`);
      blocked.delete(`${b.r},${b.c}`);
    } else {
      edges.delete(k);
    }
  }

  function setBlocked(r, c, target) {
    const k = `${r},${c}`;
    // don't block a cell that carries fixed (given) rails or an exit stub
    if (borderStubs.has(k)) return;
    let hasLocked = false;
    for (const d of ['N', 'E', 'S', 'W']) {
      if (lockedEdges.has(edgeKey(r, c, d))) hasLocked = true;
    }
    if (hasLocked) return;
    const on = blocked.has(k);
    const want = target === undefined ? !on : target;
    if (want === on) return;
    if (want) {
      // clear any player rails on this cell first
      for (const d of ['N', 'E', 'S', 'W']) {
        const ek = edgeKey(r, c, d);
        if (!lockedEdges.has(ek)) edges.delete(ek);
      }
      blocked.add(k);
    } else blocked.delete(k);
  }

  // --- pointer handling -----------------------------------------------------
  let dragging = false;
  let dragTool = 'rail'; // 'rail' | 'empty'
  let strokeAdd = true; // whether this stroke adds (true) or erases (false)
  let strokeDecided = false;
  let lastCell = null;
  let downCell = null;
  let moved = false;
  let longTimer = null;

  function cellAt(evt) {
    const rect = canvas.getBoundingClientRect();
    const x = evt.clientX - rect.left - originX;
    const y = evt.clientY - rect.top - originY;
    const c = Math.floor(x / cell);
    const r = Math.floor(y / cell);
    if (!inGrid(r, c)) return null;
    return { r, c };
  }

  function onDown(evt) {
    if (done) return;
    const cellPos = cellAt(evt);
    if (!cellPos) return;
    evt.preventDefault();
    canvas.setPointerCapture?.(evt.pointerId);
    firstTouch();
    pushHistory();
    dragging = true;
    moved = false;
    strokeDecided = false;
    downCell = cellPos;
    lastCell = cellPos;
    // right mouse button => empty tool regardless of mode
    dragTool = evt.button === 2 ? 'empty' : mode;

    if (dragTool === 'empty') {
      const k = `${cellPos.r},${cellPos.c}`;
      strokeAdd = !blocked.has(k);
      strokeDecided = true;
      setBlocked(cellPos.r, cellPos.c, strokeAdd);
      commit();
    } else {
      // long-press => quick empty mark (mobile), only if no drag happens
      longTimer = setTimeout(() => {
        if (dragging && !moved) {
          setBlocked(cellPos.r, cellPos.c);
          commit();
          dragging = false; // consume; avoid drawing after long-press
        }
      }, 450);
    }
  }

  function onMove(evt) {
    if (!dragging) return;
    const cellPos = cellAt(evt);
    if (!cellPos) return;
    if (cellPos.r !== lastCell.r || cellPos.c !== lastCell.c) {
      moved = true;
      if (longTimer) {
        clearTimeout(longTimer);
        longTimer = null;
      }
    }
    if (cellPos.r === lastCell.r && cellPos.c === lastCell.c) return;

    if (dragTool === 'empty') {
      setBlocked(cellPos.r, cellPos.c, strokeAdd);
      lastCell = cellPos;
      commit();
      return;
    }

    // rail tool: connect consecutive cells if adjacent
    const dr = Math.abs(cellPos.r - lastCell.r);
    const dc = Math.abs(cellPos.c - lastCell.c);
    if (dr + dc === 1) {
      if (!strokeDecided) {
        const k = between(lastCell, cellPos);
        strokeAdd = k ? !edges.has(k) : true;
        strokeDecided = true;
      }
      toggleEdge(lastCell, cellPos, strokeAdd);
      lastCell = cellPos;
      commit();
    } else {
      // jumped (fast drag over a diagonal / gap): just resync anchor
      lastCell = cellPos;
    }
  }

  function onUp() {
    if (longTimer) {
      clearTimeout(longTimer);
      longTimer = null;
    }
    if (!dragging) return;
    dragging = false;
    // a plain tap with the rail tool and no movement: no-op (rails need a drag)
    if (!moved && dragTool === 'rail') {
      history.pop(); // nothing changed; discard snapshot
      canUndo = history.length > 0;
    }
  }

  function undo() {
    if (!history.length) return;
    const snap = history.pop();
    edges = snap.edges;
    blocked = snap.blocked;
    done = false;
    canUndo = history.length > 0;
    commit();
  }

  function clearAll() {
    pushHistory();
    edges = new Set(lockedEdges);
    blocked = new Set();
    done = false;
    commit();
  }

  // --- drawing --------------------------------------------------------------
  function cssVar(name, fallback) {
    const v = getComputedStyle(canvas).getPropertyValue(name).trim();
    return v || fallback;
  }

  function draw() {
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    ctx.clearRect(0, 0, w, h);

    const surface = cssVar('--surface-2', '#fff');
    const border = cssVar('--border', '#cbd5e1');
    const muted = cssVar('--muted', '#94a3b8');
    const ink = cssVar('--ink', '#0f172a');
    const given = '#64748b';
    const GREEN = '#16a34a';
    const RED = '#e5484d';

    // grid background
    ctx.fillStyle = surface;
    ctx.fillRect(originX, originY, C * cell, R * cell);

    // grid lines
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let c = 0; c <= C; c++) {
      ctx.moveTo(originX + c * cell + 0.5, originY);
      ctx.lineTo(originX + c * cell + 0.5, originY + R * cell);
    }
    for (let r = 0; r <= R; r++) {
      ctx.moveTo(originX, originY + r * cell + 0.5);
      ctx.lineTo(originX + C * cell, originY + r * cell + 0.5);
    }
    ctx.stroke();
    // outer frame heavier
    ctx.strokeStyle = ink;
    ctx.lineWidth = 2;
    ctx.strokeRect(originX + 0.5, originY + 0.5, C * cell, R * cell);

    // clues
    ctx.font = `600 ${Math.round(cell * 0.42)}px ui-monospace, monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let c = 0; c < C; c++) {
      const cur = colCount[c];
      const clue = puzzle.colClues[c];
      ctx.fillStyle = cur === clue ? GREEN : cur > clue ? RED : ink;
      ctx.fillText(String(clue), originX + c * cell + cell / 2, originY - cell * 0.5);
    }
    ctx.textAlign = 'left';
    for (let r = 0; r < R; r++) {
      const cur = rowCount[r];
      const clue = puzzle.rowClues[r];
      ctx.fillStyle = cur === clue ? GREEN : cur > clue ? RED : ink;
      ctx.fillText(String(clue), originX + C * cell + cell * 0.28, originY + r * cell + cell / 2);
    }

    // blocked (empty) marks
    ctx.strokeStyle = muted;
    ctx.lineWidth = Math.max(2, cell * 0.06);
    ctx.lineCap = 'round';
    for (const k of blocked) {
      const [r, c] = k.split(',').map(Number);
      const x = originX + c * cell;
      const y = originY + r * cell;
      const m = cell * 0.3;
      ctx.beginPath();
      ctx.moveTo(x + m, y + m);
      ctx.lineTo(x + cell - m, y + cell - m);
      ctx.moveTo(x + cell - m, y + m);
      ctx.lineTo(x + m, y + cell - m);
      ctx.stroke();
    }

    // track pieces
    const rw = Math.max(3, cell * 0.16);
    ctx.lineWidth = rw;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (let r = 0; r < R; r++) {
      for (let c = 0; c < C; c++) {
        const dirs = cellDirs(r, c);
        if (!dirs.length) continue;
        const cx = originX + c * cell + cell / 2;
        const cy = originY + r * cell + cell / 2;
        const fork = dirs.length > 2;
        for (const d of dirs) {
          const isStub = borderStubs.get(`${r},${c}`)?.has(d);
          const locked = isStub || lockedEdges.has(edgeKey(r, c, d));
          ctx.strokeStyle = fork ? RED : locked ? given : accent;
          let ex = cx;
          let ey = cy;
          if (d === 'N') ey = originY + r * cell - (isStub ? cell * 0.38 : 0);
          if (d === 'S') ey = originY + (r + 1) * cell + (isStub ? cell * 0.38 : 0);
          if (d === 'W') ex = originX + c * cell - (isStub ? cell * 0.38 : 0);
          if (d === 'E') ex = originX + (c + 1) * cell + (isStub ? cell * 0.38 : 0);
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(ex, ey);
          ctx.stroke();
        }
        // little hub dot so curves read cleanly
        ctx.fillStyle = fork ? RED : accent;
        ctx.beginPath();
        ctx.arc(cx, cy, rw * 0.42, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  onMount(() => {
    recount();
    fit();
    const ro = new ResizeObserver(() => fit());
    ro.observe(wrap);
    return () => ro.disconnect();
  });
</script>

<div class="tt" bind:this={wrap}>
  <p class="hint">
    Соедини входы одной ж/д линией. Числа = сколько клеток пути в столбце/строке.
    Линия не ветвится и не пересекается сама с собой.
  </p>

  <canvas
    bind:this={canvas}
    class="board"
    role="img"
    aria-label={`Train Tracks ${R}×${C}`}
    onpointerdown={onDown}
    onpointermove={onMove}
    onpointerup={onUp}
    onpointercancel={onUp}
    oncontextmenu={(e) => e.preventDefault()}
  ></canvas>

  <div class="tools">
    <div class="seg" role="group" aria-label="Инструмент">
      <button class:active={mode === 'rail'} onclick={() => (mode = 'rail')}>🚆 Рельсы</button>
      <button class:active={mode === 'empty'} onclick={() => (mode = 'empty')}>✖ Пусто</button>
    </div>
    <button class="ghost" onclick={undo} disabled={!canUndo}>↶ Отмена</button>
    <button class="ghost" onclick={clearAll}>Сброс</button>
  </div>

  <p class="legend">
    Десктоп: <b>ЛКМ + протяжка</b> — рельсы, <b>ПКМ</b> — пусто.
    Моб.: <b>протяжка</b> в выбранном режиме, <b>долгий тап</b> — пусто.
  </p>
</div>

<style>
  .tt {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
  }
  .hint {
    margin: 0;
    max-width: 34rem;
    text-align: center;
    color: var(--muted, #64748b);
    font-size: 0.9rem;
    line-height: 1.35;
  }
  .board {
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
    max-width: 100%;
    cursor: crosshair;
  }
  .tools {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    justify-content: center;
  }
  .seg {
    display: inline-flex;
    border: 1px solid var(--border, #cbd5e1);
    border-radius: 0.6rem;
    overflow: hidden;
  }
  .seg button {
    border: none;
    background: var(--surface-2, #fff);
    color: var(--ink, #0f172a);
    padding: 0.5rem 0.8rem;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .seg button.active {
    background: var(--accent, #e5484d);
    color: #fff;
  }
  .ghost {
    border: 1px solid var(--border, #cbd5e1);
    background: var(--surface-2, #fff);
    color: var(--ink, #0f172a);
    padding: 0.5rem 0.8rem;
    border-radius: 0.6rem;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .ghost:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .legend {
    margin: 0;
    max-width: 34rem;
    text-align: center;
    color: var(--muted, #64748b);
    font-size: 0.8rem;
    line-height: 1.4;
  }
</style>
