<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { emptyQuery } from "../lib/filters";
  import type { FilterOptions, JobQuery } from "../lib/types";

  export let filters: JobQuery;
  export let options: FilterOptions | null = null;

  const dispatch = createEventDispatcher<{ change: { filters: JobQuery } }>();

  function update(key: keyof JobQuery, value: string): void {
    const next = {
      ...filters,
      [key]: value || undefined,
    };
    dispatch("change", { filters: next });
  }

  function updateNumber(key: keyof JobQuery, value: string): void {
    const next = {
      ...filters,
      [key]: value ? Number(value) : undefined,
    };
    dispatch("change", { filters: next });
  }

  function reset(): void {
    dispatch("change", { filters: emptyQuery() });
  }
</script>

<div class="shell-card rounded-[1.6rem] p-4">
  <div class="mb-3 flex items-center justify-between">
    <div>
      <div class="section-eyebrow">Filters</div>
      <h3 class="mt-1 text-lg font-medium">Tighten the radar cone.</h3>
    </div>
    <button class="ghost-button text-sm" on:click={reset}>Clear</button>
  </div>
  <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
    <select class="surface-input" on:change={(event) => update("status", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All statuses</option>
      {#each options?.statuses ?? [] as item}
        <option value={item} selected={filters.status === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("role_family", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All role families</option>
      {#each options?.role_families ?? [] as item}
        <option value={item} selected={filters.role_family === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("application_status", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All application states</option>
      {#each options?.application_statuses ?? [] as item}
        <option value={item} selected={filters.application_status === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("source_type", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All sources</option>
      {#each options?.source_types ?? [] as item}
        <option value={item} selected={filters.source_type === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("company", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All companies</option>
      {#each options?.companies ?? [] as item}
        <option value={item} selected={filters.company === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("prestige_tier", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All prestige tiers</option>
      {#each options?.prestige_tiers ?? [] as item}
        <option value={item} selected={filters.prestige_tier === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("location", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All locations</option>
      {#each options?.locations ?? [] as item}
        <option value={item} selected={filters.location === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("season", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All seasons</option>
      {#each options?.seasons ?? [] as item}
        <option value={item} selected={filters.season === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("year", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All years</option>
      {#each options?.years ?? [] as item}
        <option value={item} selected={filters.year === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("remote_type", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All remote modes</option>
      {#each options?.remote_types ?? [] as item}
        <option value={item} selected={filters.remote_type === item}>{item}</option>
      {/each}
    </select>
    <select class="surface-input" on:change={(event) => update("sponsorship", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="">All sponsorship states</option>
      {#each options?.sponsorships ?? [] as item}
        <option value={item} selected={filters.sponsorship === item}>{item}</option>
      {/each}
    </select>
    <input
      class="surface-input"
      type="number"
      min="0"
      max="100"
      placeholder="Min opportunity"
      value={filters.min_opportunity_score ?? ""}
      on:change={(event) => updateNumber("min_opportunity_score", (event.currentTarget as HTMLInputElement).value)}
    />
    <input
      class="surface-input"
      type="number"
      min="0"
      max="100"
      placeholder="Min hidden gem"
      value={filters.min_hidden_gem_score ?? ""}
      on:change={(event) => updateNumber("min_hidden_gem_score", (event.currentTarget as HTMLInputElement).value)}
    />
    <input
      class="surface-input"
      type="number"
      min="0"
      max="100"
      placeholder="Min eligibility"
      value={filters.min_eligibility_score ?? ""}
      on:change={(event) => updateNumber("min_eligibility_score", (event.currentTarget as HTMLInputElement).value)}
    />
    <select class="surface-input" on:change={(event) => update("sort", (event.currentTarget as HTMLSelectElement).value)}>
      <option value="opportunity_score" selected={filters.sort === "opportunity_score"}>Opportunity</option>
      <option value="newest" selected={filters.sort === "newest"}>Newest</option>
      <option value="hidden_gem_score" selected={filters.sort === "hidden_gem_score"}>Hidden gem</option>
      <option value="eligibility_score" selected={filters.sort === "eligibility_score"}>Eligibility</option>
      <option value="technical_depth" selected={filters.sort === "technical_depth"}>Technical depth</option>
      <option value="prestige" selected={filters.sort === "prestige"}>Prestige</option>
    </select>
  </div>
</div>
