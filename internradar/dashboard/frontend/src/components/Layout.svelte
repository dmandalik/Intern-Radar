<script lang="ts">
  import Sidebar from "./Sidebar.svelte";
  import TopBar from "./TopBar.svelte";
  import type { PageId, SummaryResponse } from "../lib/types";

  export let currentPage: PageId;
  export let summary: SummaryResponse | null = null;
  export let search = "";
  export let activePack: string | null = null;
  export let lastScanAt: string | null = null;
  export let theme: "dusk" | "dawn" = "dusk";

  export let onNavigate: (page: PageId) => void;
  export let onSearch: (value: string) => void;
  export let onThemeToggle: () => void;
  export let onExportNavigate: () => void;
</script>

<div class="relative min-h-screen px-3 py-3 sm:px-4 sm:py-4">
  <div class="mx-auto grid min-h-[calc(100vh-1.5rem)] max-w-[1600px] grid-cols-1 gap-4 lg:grid-cols-[300px_1fr]">
    <Sidebar {currentPage} {summary} on:navigate={(event) => onNavigate(event.detail.page)} />
    <div class="flex min-w-0 flex-col gap-4">
      <TopBar
        {search}
        {activePack}
        {lastScanAt}
        {theme}
        on:search={(event) => onSearch(event.detail.value)}
        on:themeToggle={onThemeToggle}
        on:export={onExportNavigate}
      />
      <main class="min-w-0 flex-1">
        <slot />
      </main>
    </div>
  </div>
</div>
