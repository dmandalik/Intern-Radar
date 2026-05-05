<script lang="ts">
  import ExportPanel from "../components/ExportPanel.svelte";

  export let busy = false;
  export let resultPaths: string[] = [];
  export let onExport: (payload: { format: string; all?: boolean }) => void;
</script>

<section class="space-y-5">
  <div class="shell-card rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Export</div>
    <h2 class="page-title mt-3">Ship the current radar view into polished files.</h2>
    <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
      Generate Excel, HTML, Markdown, JSON, or CSV exports straight from the local score-aware job database.
    </p>
  </div>
  <ExportPanel {busy} {resultPaths} on:export={(event) => onExport(event.detail)} />
</section>
