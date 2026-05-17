<script lang="ts">
  export let label: string;
  export let value: string | number;
  export let hint = "";
  export let accent = "var(--accent)";
</script>

<article class="shell-card signal-card metric-glow rounded-[1.4rem] p-5">
  <div class="section-eyebrow">{label}</div>
  <div class="mt-3 flex items-end justify-between gap-3">
    <div class="text-4xl font-semibold tracking-[-0.04em]" style={`color:${accent}`}>{value}</div>
    {#if hint}
      <div class="max-w-[12rem] text-right text-sm text-[var(--muted)]">{hint}</div>
    {/if}
  </div>
</article>
