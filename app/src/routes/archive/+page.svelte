<script>
  // Archive: every available day with its play status. PLATFORM code.
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { availableDays, fmtDate, todayIndex } from '$lib/platform/days.js';
  import { loadDay } from '$lib/platform/storage.js';
  import { isUnlocked } from '$lib/platform/unlock.js';
  import { fmtTime } from '$lib/platform/timer.js';

  let rows = $state([]);

  onMount(() => {
    const unlocked = isUnlocked();
    const today = todayIndex();
    rows = availableDays(new Date(), unlocked)
      .sort((a, b) => b - a) // newest first
      .map((idx) => {
        const r = loadDay(idx);
        return {
          idx,
          date: fmtDate(idx),
          future: idx > today,
          status: r.finished ? 'done' : r.started ? 'progress' : 'new',
          ms: r.elapsedMs
        };
      });
  });
</script>

<h1>Архив</h1>
{#if rows.length === 0}
  <p class="muted">Пока нет доступных дней.</p>
{:else}
  <ul class="days">
    {#each rows as row}
      <li>
        <a href="{base}/?day={row.idx}" class="row" class:future={row.future}>
          <span class="idx">#{row.idx}</span>
          <span class="date">{row.date}</span>
          <span class="status status-{row.status}">
            {#if row.status === 'done'}✓ {fmtTime(row.ms)}
            {:else if row.status === 'progress'}…идёт
            {:else}играть{/if}
          </span>
        </a>
      </li>
    {/each}
  </ul>
{/if}

<style>
  h1 {
    font-size: 24px;
  }
  .muted {
    color: var(--muted);
  }
  .days {
    list-style: none;
    padding: 0;
    margin: 16px 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 14px;
    text-decoration: none;
    color: var(--ink);
    background: var(--surface);
    border: var(--border);
    box-shadow: var(--shadow);
    border-radius: 10px;
    padding: 12px 14px;
  }
  .row:active {
    transform: translate(2px, 2px);
    box-shadow: none;
  }
  .row.future {
    border-style: dashed;
  }
  .idx {
    font-family: var(--mono);
    color: var(--muted);
    min-width: 44px;
  }
  .date {
    flex: 1;
    font-weight: 600;
  }
  .status {
    font-family: var(--mono);
    font-size: 13px;
  }
  .status-done {
    color: var(--good);
  }
  .status-new {
    color: var(--accent-2);
  }
</style>
