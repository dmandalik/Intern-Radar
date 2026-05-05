<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import FilterBar from "../components/FilterBar.svelte";
  import JobCard from "../components/JobCard.svelte";
  import JobTable from "../components/JobTable.svelte";
  import type { DashboardJob, FilterOptions, JobQuery } from "../lib/types";

  export let jobs: DashboardJob[] = [];
  export let total = 0;
  export let filters: JobQuery;
  export let options: FilterOptions | null = null;
  export let view: "cards" | "table" = "cards";

  export let onFilterChange: (filters: JobQuery) => void;
  export let onSelectJob: (jobId: string) => void;
  export let onAction: (jobId: string, action: string) => void;
  export let onViewChange: (view: "cards" | "table") => void;
</script>

<section class="space-y-5">
  <div class="flex items-end justify-between gap-4">
    <div>
      <div class="section-eyebrow">Jobs</div>
      <h2 class="page-title mt-2">Every captured role, ranked and inspectable.</h2>
    </div>
    <div class="flex gap-2">
      <button class={`ghost-button ${view === "cards" ? "border-[var(--accent)]/40" : ""}`} on:click={() => onViewChange("cards")}>Cards</button>
      <button class={`ghost-button ${view === "table" ? "border-[var(--accent)]/40" : ""}`} on:click={() => onViewChange("table")}>Table</button>
    </div>
  </div>

  <FilterBar {filters} {options} on:change={(event) => onFilterChange(event.detail.filters)} />

  <div class="flex items-center justify-between text-sm text-[var(--muted)]">
    <span>{total} roles match the current query.</span>
  </div>

  {#if jobs.length === 0}
    <EmptyState title="No roles matched these filters" message="Relax the current thresholds or switch pages to widen the search cone." />
  {:else if view === "table"}
    <JobTable {jobs} on:select={(event) => onSelectJob(event.detail.jobId)} on:action={(event) => onAction(event.detail.jobId, event.detail.action)} />
  {:else}
    <div class="grid gap-4 xl:grid-cols-2">
      {#each jobs as job (job.id)}
        <JobCard {job} on:select={(event) => onSelectJob(event.detail.jobId)} on:action={(event) => onAction(event.detail.jobId, event.detail.action)} />
      {/each}
    </div>
  {/if}
</section>
