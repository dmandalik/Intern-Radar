<script lang="ts">
  import { formatLabel } from "../lib/format";

  export let status: string;

  const toneMap: Record<string, string> = {
    open: "border-[var(--success)]/35 bg-[color-mix(in_srgb,var(--success)_14%,transparent)] text-[var(--success)]",
    likely_open: "border-[var(--success)]/25 bg-[color-mix(in_srgb,var(--success)_10%,transparent)] text-[var(--success)]",
    coming_soon: "border-[var(--warning)]/35 bg-[color-mix(in_srgb,var(--warning)_14%,transparent)] text-[var(--warning)]",
    closed: "border-[var(--danger)]/35 bg-[color-mix(in_srgb,var(--danger)_12%,transparent)] text-[var(--danger)]",
    unknown: "border-[var(--muted)]/35 bg-[color-mix(in_srgb,var(--muted)_12%,transparent)] text-[var(--muted)]",
    requires_login: "border-[var(--accent-2)]/35 bg-[color-mix(in_srgb,var(--accent-2)_14%,transparent)] text-[var(--accent-2)]",
    stale: "border-[var(--muted-2)]/35 bg-[color-mix(in_srgb,var(--muted-2)_12%,transparent)] text-[var(--muted)]"
  };
</script>

<span class={`status-pill ${toneMap[status] ?? toneMap.unknown}`}>
  {formatLabel(status)}
</span>
