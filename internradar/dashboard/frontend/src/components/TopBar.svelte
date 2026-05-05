<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import { formatDateTime } from "../lib/format";

  export let search = "";
  export let activePack: string | null = null;
  export let lastScanAt: string | null = null;
  export let theme: "dusk" | "dawn" = "dusk";

  const dispatch = createEventDispatcher<{
    search: { value: string };
    themeToggle: void;
    export: void;
  }>();

  function handleInput(event: Event): void {
    dispatch("search", { value: (event.currentTarget as HTMLInputElement).value });
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
      <input
        class="surface-input min-w-[16rem]"
        placeholder="Search company, role, status, signal..."
        value={search}
        on:input={handleInput}
      />
      <ThemeToggle {theme} on:toggle={() => dispatch("themeToggle")} />
      <button class="radar-button" on:click={() => dispatch("export")}>Export now</button>
    </div>
  </div>
</header>
