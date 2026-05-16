<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let busy = false;
  export let resultPaths: string[] = [];

  const dispatch = createEventDispatcher<{
    export: { format: string; all?: boolean; hidden_gems?: boolean; saved?: boolean; applied?: boolean };
  }>();

  const actions = [
    { label: "CSV", format: "csv", note: "Quick spreadsheet imports and ad-hoc slicing." },
    { label: "JSON", format: "json", note: "Complete machine-readable archive of the shortlist." },
    { label: "XLSX", format: "xlsx", note: "Best for tracking and recruiter-style application lists." },
    { label: "HTML", format: "html", note: "Polished static report for review and sharing locally." },
    { label: "Markdown", format: "markdown", note: "GitHub-friendly summary and notes-ready output." }
  ];
</script>

<div class="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
  <section class="shell-card rounded-[1.7rem] p-5">
    <div class="section-eyebrow">Export formats</div>
    <h3 class="mt-2 text-2xl font-semibold">Publish a polished application list.</h3>
    <p class="mt-2 text-sm text-[var(--muted)]">Generate spreadsheet, report, and archival formats straight from the local job database.</p>
    <div class="mt-5 grid gap-3 md:grid-cols-2">
      {#each actions as action}
        <button class="glass-panel rounded-[1.2rem] p-4 text-left transition hover:border-[var(--accent)]/35" disabled={busy} on:click={() => dispatch("export", { format: action.format })}>
          <div class="flex items-center justify-between gap-3">
            <span class="text-base font-semibold">{action.label}</span>
            <span class="section-eyebrow">Export</span>
          </div>
          <div class="mt-2 text-sm text-[var(--muted)]">{action.note}</div>
        </button>
      {/each}
    </div>
    <div class="mt-4 flex flex-wrap gap-3">
      <button class="radar-button" disabled={busy} on:click={() => dispatch("export", { format: "json", all: true })}>Export all formats</button>
      <button class="ghost-button" disabled={busy} on:click={() => dispatch("export", { format: "html" })}>Build polished report</button>
    </div>
  </section>

  <section class="shell-card rounded-[1.7rem] p-5">
    <div class="section-eyebrow">Recent export paths</div>
    {#if resultPaths.length === 0}
      <p class="mt-3 text-sm text-[var(--muted)]">No export created in this session yet.</p>
    {:else}
      <ul class="mt-3 space-y-2 text-sm text-[var(--muted)]">
        {#each resultPaths as path}
          <li class="rounded-2xl border border-[var(--border)] px-3 py-2 mono-label">{path}</li>
        {/each}
      </ul>
    {/if}
  </section>
</div>
