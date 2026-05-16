<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { PageId, SummaryResponse } from "../lib/types";
  import { compactNumber } from "../lib/format";

  export let currentPage: PageId;
  export let summary: SummaryResponse | null = null;

  const dispatch = createEventDispatcher<{ navigate: { page: PageId } }>();

  const items: Array<{ id: PageId; label: string; metric?: string }> = [
    { id: "overview", label: "Overview" },
    { id: "jobs", label: "Jobs" },
    { id: "hidden_gems", label: "Hidden Gems", metric: "hidden_gems" },
    { id: "coming_soon", label: "Coming Soon", metric: "coming_soon" },
    { id: "saved", label: "Pipeline", metric: "saved" },
    { id: "review", label: "Review", metric: "review_needed" },
    { id: "settings", label: "Settings" },
    { id: "export", label: "Export" }
  ];
</script>

<aside class="shell-card h-full rounded-[1.8rem] p-4">
  <div class="rounded-[1.4rem] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-2)_86%,transparent)] p-4">
    <div class="section-eyebrow">Command center</div>
    <h1 class="mt-3 text-2xl font-semibold tracking-tight">Intern Radar</h1>
    <p class="mt-2 text-sm text-[var(--muted)]">A local signal console for internships worth real attention.</p>
  </div>

  <nav class="mt-5 space-y-2">
    {#each items as item}
      <button
        class={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
          currentPage === item.id
            ? "border-[var(--accent)]/40 bg-[color-mix(in_srgb,var(--accent)_12%,transparent)]"
            : "border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_86%,transparent)]"
        }`}
        on:click={() => dispatch("navigate", { page: item.id })}
      >
        <span>{item.label}</span>
        {#if item.metric && summary}
          <span class="mono-label text-xs text-[var(--muted)]">{compactNumber(summary.counts[item.metric] ?? 0)}</span>
        {/if}
      </button>
    {/each}
  </nav>

  <div class="mt-5 rounded-[1.4rem] border border-[var(--border)] p-4 text-sm text-[var(--muted)]">
    <div class="section-eyebrow">Live signal</div>
    <p class="mt-2">Open roles, hidden gems, and evidence-first review are all local to this workspace.</p>
  </div>
</aside>
