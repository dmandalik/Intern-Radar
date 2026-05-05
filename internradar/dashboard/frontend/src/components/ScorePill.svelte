<script lang="ts">
  import { formatScore } from "../lib/format";

  export let label: string;
  export let value: number;
  export let accent = "var(--accent)";
</script>

<span
  class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
  style={`border-color: color-mix(in srgb, ${accent} 24%, var(--border)); background: color-mix(in srgb, ${accent} 10%, transparent);`}
>
  <span class="mono-label uppercase tracking-[0.16em] text-[0.65rem] text-[var(--muted)]">{label}</span>
  <strong style={`color: ${accent}`}>{formatScore(value)}</strong>
</span>
