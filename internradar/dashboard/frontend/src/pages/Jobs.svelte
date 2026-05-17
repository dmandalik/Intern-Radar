<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import FilterBar from "../components/FilterBar.svelte";
  import JobCard from "../components/JobCard.svelte";
  import JobTable from "../components/JobTable.svelte";
  import { formatLabel } from "../lib/format";
  import { emptyQuery } from "../lib/filters";
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

  const chipFields: Array<{ key: keyof JobQuery; label: string }> = [
    { key: "search", label: "Search" },
    { key: "status", label: "Status" },
    { key: "role_family", label: "Role" },
    { key: "company", label: "Company" },
    { key: "location", label: "Location" },
    { key: "season", label: "Season" },
    { key: "year", label: "Year" },
    { key: "application_status", label: "Stage" },
    { key: "source_type", label: "Source" },
    { key: "remote_type", label: "Remote" },
    { key: "sponsorship", label: "Sponsorship" },
    { key: "prestige_tier", label: "Prestige" },
    { key: "min_opportunity_score", label: "Min opp." },
    { key: "min_hidden_gem_score", label: "Min gem" },
    { key: "min_eligibility_score", label: "Min elig." },
  ];

  $: activeChips = chipFields
    .map((field) => {
      const value = filters[field.key];
      if (value === undefined || value === null || value === "") return null;
      return {
        key: field.key,
        label: field.label,
        value: typeof value === "string" ? formatLabel(value) : String(value),
      };
    })
    .filter(Boolean);

  function removeChip(key: keyof JobQuery): void {
    onFilterChange({
      ...filters,
      [key]: undefined,
    });
  }
</script>

<section class="space-y-5">
  <div class="shell-card signal-card hero-orbit rounded-[1.8rem] p-6">
    <div class="flex items-end justify-between gap-4">
      <div>
        <div class="section-eyebrow">Jobs</div>
        <h2 class="page-title mt-2">Every captured role, ranked and inspectable.</h2>
        <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
          Search across the full job database, tighten the cone with filters, then open a dossier when a role is worth real attention.
        </p>
      </div>
      <div class="flex gap-2">
        <button class={`ghost-button ${view === "cards" ? "border-[var(--accent)]/40" : ""}`} on:click={() => onViewChange("cards")}>Cards</button>
        <button class={`ghost-button ${view === "table" ? "border-[var(--accent)]/40" : ""}`} on:click={() => onViewChange("table")}>Table</button>
      </div>
    </div>
  </div>

  <div class="flex items-end justify-between gap-4">
    <div>
      <div class="section-eyebrow">Active query</div>
      <div class="mt-2 text-lg font-medium">{total} roles match the current radar cone.</div>
    </div>
    <button class="ghost-button" on:click={() => onFilterChange(emptyQuery())}>Reset all filters</button>
  </div>

  {#if activeChips.length > 0}
    <div class="flex flex-wrap gap-2">
      {#each activeChips as chip}
        <button class="filter-chip" on:click={() => removeChip(chip.key)}>
          <span class="mono-label text-[var(--muted)]">{chip.label}</span>
          <span>{chip.value}</span>
          <span class="text-[var(--muted)]">×</span>
        </button>
      {/each}
    </div>
  {/if}

  <FilterBar {filters} {options} on:change={(event) => onFilterChange(event.detail.filters)} />

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
