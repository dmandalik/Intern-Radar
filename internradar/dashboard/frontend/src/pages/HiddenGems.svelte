<script lang="ts">
  import JobCard from "../components/JobCard.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import type { DashboardJob } from "../lib/types";

  export let jobs: DashboardJob[] = [];
  export let threshold = 70;

  export let onThresholdChange: (value: number) => void;
  export let onSelectJob: (jobId: string) => void;
  export let onAction: (jobId: string, action: string) => void;
</script>

<section class="space-y-5">
  <div class="shell-card signal-card hero-orbit rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Hidden gems</div>
    <h2 class="page-title mt-3">Under-the-radar roles with real signal.</h2>
    <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
      This is not a dump of obscure companies. It is the shortlist of technically credible, fresh,
      eligible roles that are less obvious than the prestige-first herd.
    </p>
    <div class="mt-5 max-w-sm">
      <label class="section-eyebrow" for="hidden-gem-threshold">Threshold {threshold}</label>
      <input id="hidden-gem-threshold" class="mt-3 w-full accent-[var(--accent)]" type="range" min="50" max="95" step="1" value={threshold} on:input={(event) => onThresholdChange(Number((event.currentTarget as HTMLInputElement).value))} />
    </div>
  </div>

  <div class="grid gap-4 xl:grid-cols-3">
    <section class="shell-card signal-card rounded-[1.5rem] p-5">
      <div class="section-eyebrow">Signal count</div>
      <div class="mt-2 text-4xl font-semibold">{jobs.length}</div>
      <p class="mt-2 text-sm text-[var(--muted)]">Roles currently clearing the hidden-gem threshold.</p>
    </section>
    <section class="shell-card signal-card rounded-[1.5rem] p-5">
      <div class="section-eyebrow">Why these surfaced</div>
      <p class="mt-2 text-sm leading-7 text-[var(--muted)]">They combine technical depth, freshness, and candidate fit without relying only on prestige.</p>
    </section>
    <section class="shell-card signal-card rounded-[1.5rem] p-5">
      <div class="section-eyebrow">Use this page for</div>
      <p class="mt-2 text-sm leading-7 text-[var(--muted)]">Finding credible roles that the prestige-first crowd may overlook but that still have real application signal.</p>
    </section>
  </div>

  {#if jobs.length === 0}
    <EmptyState title="No hidden gems cleared the current bar" message="Lower the threshold or rescan to widen the set of high-signal technical roles." />
  {:else}
    <div class="grid gap-4 xl:grid-cols-2">
      {#each jobs as job (job.id)}
        <JobCard {job} emphasizeHiddenGem={true} on:select={(event) => onSelectJob(event.detail.jobId)} on:action={(event) => onAction(event.detail.jobId, event.detail.action)} />
      {/each}
    </div>
  {/if}
</section>
