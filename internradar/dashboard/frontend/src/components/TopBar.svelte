<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import { formatDateTime } from "../lib/format";

  export let search = "";
  export let activePack: string | null = null;
  export let lastScanAt: string | null = null;
  export let theme: "dusk" | "dawn" = "dusk";
  export let scanBusy = false;

  let searchDraft = search;

  const dispatch = createEventDispatcher<{
    search: { value: string };
    themeToggle: void;
    scan: void;
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
      <div class="glass-panel flex items-center gap-3 rounded-full px-3 py-2">
        <div class="hidden text-right sm:block">
          <div class="section-eyebrow">Live radar</div>
          <div class="text-xs text-[var(--muted)]">
            {scanBusy ? "Refreshing firms and signals…" : "Run a fresh scan from the command center"}
          </div>
        </div>
        <button
          class="radar-button min-w-[8.5rem]"
          type="button"
          disabled={scanBusy}
          aria-busy={scanBusy}
          on:click={() => dispatch("scan")}
        >
          {scanBusy ? "Scanning…" : "Run scan"}
        </button>
      </div>
      <ThemeToggle {theme} on:toggle={() => dispatch("themeToggle")} />
      <button class="ghost-button" type="button" on:click={() => dispatch("export")}>Export now</button>
    </div>
  </div>
</header>
