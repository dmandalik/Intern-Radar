<script lang="ts">
  export let title: string;
  export let rows: Array<{ label: string; value: number }> = [];

  const max = Math.max(...rows.map((row) => row.value), 1);
</script>

<article class="shell-card signal-card rounded-[1.6rem] p-5">
  <div class="flex items-center justify-between">
    <h3 class="text-lg font-medium">{title}</h3>
    <span class="section-eyebrow">signal map</span>
  </div>
  <div class="mt-4 space-y-3">
    {#each rows as row}
      <div class="space-y-1">
        <div class="flex items-center justify-between gap-3 text-sm">
          <span class="truncate text-[var(--muted)]">{row.label}</span>
          <span class="mono-label text-xs text-[var(--text)]">{row.value}</span>
        </div>
        <div class="h-2 overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--surface-2)_84%,transparent)]">
          <div
            class="chart-bar h-full rounded-full"
            style={`width:${(row.value / max) * 100}%; background: linear-gradient(90deg, var(--accent), var(--accent-2));`}
          ></div>
        </div>
      </div>
    {/each}
  </div>
</article>
