<script>
  // ===========================================================================
  // GAME SHELL — PLATFORM code. Loads the right day, owns the timer, persistence,
  // backend events, the end screen and the share loop. The actual puzzle is the
  // pluggable <GAME.component>. You should rarely need to touch this per fork.
  // ===========================================================================
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import { GAME } from '$lib/game/index.js';
  import { resolveDay, todayIndex, fmtDate, msUntilLocalMidnight } from '$lib/platform/days.js';
  import { loadDay as loadRecord, saveDay } from '$lib/platform/storage.js';
  import { makeTimer, fmtTime } from '$lib/platform/timer.js';
  import { submitStart, submitFinish, fetchAgg, statsEnabled } from '$lib/platform/api.js';
  import { applyUnlockFromUrl, isUnlocked } from '$lib/platform/unlock.js';

  let dayIdx = $state(0);
  let puzzle = $state(null);
  let record = $state(null);
  let view = $state('loading'); // loading | intro | play | end | empty
  let isFuture = $state(false);
  let agg = $state(null); // global cross-player numbers for this day
  let untilMidnight = $state('');

  let timer = null;
  let tick = null;

  onMount(() => {
    const unlocked = applyUnlockFromUrl();
    const requested = new URLSearchParams(location.search).get('day');
    dayIdx = resolveDay(requested, new Date(), unlocked);
    puzzle = GAME.loadDay(dayIdx);
    if (!puzzle) {
      view = 'empty';
      return;
    }
    isFuture = dayIdx > todayIndex();
    record = loadRecord(dayIdx);

    timer = makeTimer(record.elapsedMs || 0);

    if (record.finished) {
      view = 'end';
      loadAgg();
    } else if (record.started) {
      timer.start();
      view = 'play';
    } else {
      view = 'intro';
    }

    tick = setInterval(() => {
      untilMidnight = fmtTime(msUntilLocalMidnight());
    }, 30000);
    untilMidnight = fmtTime(msUntilLocalMidnight());
  });

  onDestroy(() => {
    timer?.destroy();
    if (tick) clearInterval(tick);
  });

  function persist() {
    saveDay(dayIdx, record);
  }

  function beginPlay() {
    view = 'play';
  }

  // --- callbacks handed to the game component -------------------------------
  function handleStart() {
    if (!record.started) {
      record.started = true;
      record.startedAt = Date.now();
      record.live = dayIdx === todayIndex();
      timer.start();
      persist();
      submitStart(dayIdx);
    }
  }

  function handleProgress(state) {
    record.state = state;
    record.elapsedMs = timer.elapsed();
    persist();
  }

  function handleFinish(result) {
    const ms = timer.stop();
    record.finished = true;
    record.finishedAt = Date.now();
    record.elapsedMs = ms;
    record.result = { ...result, ms };
    persist();
    submitFinish(dayIdx, ms, GAME.scoreOf ? GAME.scoreOf(record.result) : null);
    view = 'end';
    loadAgg();
  }

  // --- end screen -----------------------------------------------------------
  async function loadAgg() {
    if (!statsEnabled()) return;
    agg = await fetchAgg([dayIdx]);
  }

  function dayAgg() {
    return agg?.agg?.[dayIdx] || null;
  }

  function shareText() {
    const url = `${location.origin}${base}/`;
    return GAME.shareLine(record.result, dayIdx, url);
  }

  let shared = $state('');
  async function share() {
    const text = shareText();
    try {
      if (navigator.share) {
        await navigator.share({ text });
        shared = '';
        return;
      }
    } catch (e) {
      /* user cancelled — fall through to clipboard */
    }
    try {
      await navigator.clipboard.writeText(text);
      shared = 'Скопировано!';
      setTimeout(() => (shared = ''), 2000);
    } catch (e) {
      shared = 'Не вышло скопировать';
    }
  }

  const pct = (x) => Math.round((x || 0) * 100);
</script>

{#if view === 'loading'}
  <p class="status">Загрузка…</p>
{:else if view === 'empty'}
  <div class="card">
    <h1>Нет данных на этот день</h1>
    <p class="muted">Этого дня ещё нет. <a href="{base}/archive">Открыть архив →</a></p>
  </div>
{:else}
  <div class="daybar">
    <span class="daychip" class:future={isFuture}>
      #{dayIdx} · {fmtDate(dayIdx)}{#if isFuture} · превью{/if}
    </span>
  </div>

  {#if view === 'intro'}
    <div class="card intro">
      <h1>{GAME.title}</h1>
      <p class="muted">{GAME.tagline}</p>
      {#if isFuture}<p class="future-note">🔓 Режим автора: будущий день</p>{/if}
      <button class="primary" onclick={beginPlay}>Играть</button>
    </div>
  {/if}

  {#if view === 'play'}
    <div class="card">
      <GAME.component
        {puzzle}
        {dayIdx}
        saved={record.state}
        onstart={handleStart}
        onprogress={handleProgress}
        onfinish={handleFinish}
      />
    </div>
  {/if}

  {#if view === 'end'}
    <div class="card end">
      <h1>{record.result?.won ? '🚂 Готово!' : 'Конец'}</h1>
      <div class="bigstats">
        <div><span class="num">{record.result?.size ?? '—'}</span><span class="lbl">сетка</span></div>
        <div><span class="num">{fmtTime(record.elapsedMs)}</span><span class="lbl">время</span></div>
      </div>

      {#if dayAgg()}
        <div class="global">
          <h2>Все игроки</h2>
          <div class="grow">
            <div><span class="num">{dayAgg().started}</span><span class="lbl">начали</span></div>
            <div><span class="num">{dayAgg().finished}</span><span class="lbl">закончили</span></div>
          </div>
        </div>
      {/if}

      <div class="actions">
        <button class="primary" onclick={share}>Поделиться</button>
        <a class="ghost" href="{base}/stats">Вся статистика →</a>
      </div>
      {#if shared}<p class="copied">{shared}</p>{/if}

      <p class="nextgame">Новая игра через {untilMidnight}</p>
    </div>
  {/if}
{/if}

<style>
  .status {
    text-align: center;
    color: var(--muted);
    margin-top: 40px;
  }
  .daybar {
    display: flex;
    justify-content: center;
    margin-bottom: 12px;
  }
  .daychip {
    font-family: var(--mono);
    font-size: 13px;
    border: var(--border);
    background: var(--surface);
    box-shadow: var(--shadow);
    border-radius: 999px;
    padding: 4px 12px;
  }
  .daychip.future {
    border-style: dashed;
    color: var(--accent-2);
  }
  .card {
    background: var(--surface);
    border: var(--border);
    box-shadow: var(--shadow);
    border-radius: 14px;
    padding: 22px;
  }
  .intro,
  .end {
    text-align: center;
  }
  h1 {
    margin: 0 0 8px;
    font-size: 26px;
  }
  h2 {
    font-size: 16px;
    margin: 0 0 10px;
  }
  .muted {
    color: var(--muted);
  }
  .future-note {
    color: var(--accent-2);
    font-weight: 600;
  }
  .primary {
    border: var(--border);
    background: var(--accent);
    color: #111;
    box-shadow: var(--shadow);
    border-radius: 10px;
    padding: 10px 22px;
    font-weight: 800;
    font-size: 16px;
    cursor: pointer;
  }
  .primary:active {
    transform: translate(2px, 2px);
    box-shadow: none;
  }
  .ghost {
    color: var(--ink);
    font-weight: 600;
    text-decoration: none;
    font-size: 15px;
  }
  .ghost:hover {
    text-decoration: underline;
  }
  .bigstats,
  .grow {
    display: flex;
    justify-content: center;
    gap: 26px;
    margin: 16px 0;
  }
  .bigstats div,
  .grow div {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .num {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 700;
  }
  .grow .num {
    font-size: 22px;
  }
  .lbl {
    color: var(--muted);
    font-size: 12px;
  }
  .global {
    border-top: var(--border);
    margin-top: 16px;
    padding-top: 14px;
  }
  .actions {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 18px;
    margin-top: 18px;
  }
  .copied {
    color: var(--good);
    font-size: 14px;
    margin: 8px 0 0;
  }
  .nextgame {
    color: var(--muted);
    font-family: var(--mono);
    font-size: 13px;
    margin: 16px 0 0;
  }
</style>
