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
  <div class="shell-card rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Watchlist</div>
    <h2 class="page-title mt-3">Signals that are not open yet, but matter.</h2>
    <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
      Track the firms and pages that hint at future internship cycles so you can return before the market gets crowded.
    </p>
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
