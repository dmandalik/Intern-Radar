<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import { formatDateTime } from "../lib/format";

  export let search = "";
  export let activePack: string | null = null;
  export let lastScanAt: string | null = null;
  export let theme: "dusk" | "dawn" = "dusk";

  let searchDraft = search;

  const dispatch = createEventDispatcher<{
    search: { value: string };
    themeToggle: void;
    export: void;
  }>();

  $: if (search !== searchDraft) {
    searchDraft = search;
  }

  function handleInput(event: Event): void {
    searchDraft = (event.currentTarget as HTMLInputElement).value;
    dispatch("search", { value: searchDraft });
  }

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    dispatch("search", { value: searchDraft });
  }
</script>

<header class="shell-card rounded-[1.7rem] p-4 sm:p-5">
  <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
    <div>
      <div class="section-eyebrow">Intern Radar</div>
      <div class="mt-2 flex flex-wrap items-center gap-3 text-sm text-[var(--muted)]">
        <span class="mono-label">Pack {activePack ?? "unknown"}</span>
        <span>Last scan {lastScanAt ? formatDateTime(lastScanAt) : "not yet recorded"}</span>
      </div>
    </div>
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
      <form class="flex min-w-[16rem] gap-2" on:submit={handleSubmit}>
        <input
          class="surface-input min-w-0 flex-1"
          placeholder="Search company, role, status, signal..."
          value={searchDraft}
          on:input={handleInput}
        />
        <button class="ghost-button" type="submit">Search</button>
      </form>
      <ThemeToggle {theme} on:toggle={() => dispatch("themeToggle")} />
      <button class="radar-button" on:click={() => dispatch("export")}>Export now</button>
    </div>
  </div>
</header>
