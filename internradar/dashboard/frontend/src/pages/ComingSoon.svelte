<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import StatusPill from "../components/StatusPill.svelte";
  import type { DashboardJob } from "../lib/types";
  import { formatDateTime } from "../lib/format";

  export let jobs: DashboardJob[] = [];
  export let onSelectJob: (jobId: string) => void;
  export let onAction: (jobId: string, action: string) => void;
</script>

<section class="space-y-5">
  <div class="shell-card signal-card hero-orbit rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Watchlist</div>
    <h2 class="page-title mt-3">Signals that are not open yet, but matter.</h2>
    <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
      Track the firms and pages that hint at future internship cycles so you can return before the market gets crowded.
    </p>
  </div>

  <div class="grid gap-4 xl:grid-cols-3">
    <section class="shell-card signal-card rounded-[1.5rem] p-5">
      <div class="section-eyebrow">Watchlist count</div>
      <div class="mt-2 text-4xl font-semibold">{jobs.length}</div>
      <p class="mt-2 text-sm text-[var(--muted)]">Signals worth checking back on before the next cycle opens.</p>
    </section>
    <section class="shell-card signal-card rounded-[1.5rem] p-5">
      <div class="section-eyebrow">How to use this</div>
      <p class="mt-2 text-sm leading-7 text-[var(--muted)]">Save firms with credible timing hints, then revisit them before broader lists become saturated.</p>
    </section>
    <section class="shell-card signal-card rounded-[1.5rem] p-5">
      <div class="section-eyebrow">Best next move</div>
      <p class="mt-2 text-sm leading-7 text-[var(--muted)]">Open the source, save the role, and use the pipeline to keep it visible instead of letting the signal disappear.</p>
    </section>
  </div>

  {#if jobs.length === 0}
    <EmptyState title="No coming-soon signals found" message="Roles with watchlist language or future-cycle evidence will appear here." />
  {:else}
    <div class="grid gap-4 xl:grid-cols-2">
      {#each jobs as job (job.id)}
        <article class="shell-card rounded-[1.6rem] p-5">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="section-eyebrow">{job.company_name}</div>
              <h3 class="mt-2 text-xl font-semibold">{job.title}</h3>
            </div>
            <StatusPill status={job.status} />
          </div>
          <p class="mt-3 text-sm text-[var(--muted)]">{job.status_evidence.join(" • ") || "Monitor this source for the next cycle."}</p>
          <div class="mt-4 flex flex-wrap gap-3 text-sm text-[var(--muted)]">
            <span>Last checked {formatDateTime(job.last_verified)}</span>
            <span>{job.location_label}</span>
          </div>
          <div class="mt-5 flex flex-wrap gap-2">
            <button class="ghost-button" on:click={() => onSelectJob(job.id)}>View evidence</button>
            <button class="ghost-button" on:click={() => onAction(job.id, "save")}>Watch / save</button>
            <a class="radar-button" href={job.source_url} target="_blank" rel="noreferrer">Open source</a>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</section>
