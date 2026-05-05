<script lang="ts">
  import type { SettingsResponse } from "../lib/types";

  export let settings: SettingsResponse | null = null;
</script>

<section class="space-y-5">
  <div class="shell-card rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Settings</div>
    <h2 class="page-title mt-3">Current pack, ranking, and candidate context.</h2>
    <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
      This page is read-only for now. Edit the local config file if you want to change candidate preferences or ranking behavior.
    </p>
  </div>

  {#if settings}
    <div class="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
      <section class="shell-card rounded-[1.7rem] p-5">
        <div class="section-eyebrow">Paths</div>
        <dl class="mt-4 grid gap-4 text-sm">
          <div><dt class="text-[var(--muted)]">Config path</dt><dd class="mono-label break-all">{settings.config_path || "Default config only"}</dd></div>
          <div><dt class="text-[var(--muted)]">Database path</dt><dd class="mono-label break-all">{settings.database_path}</dd></div>
          <div><dt class="text-[var(--muted)]">Exports path</dt><dd class="mono-label break-all">{settings.exports_path}</dd></div>
          <div><dt class="text-[var(--muted)]">Active pack</dt><dd>{settings.active_pack ?? "Unknown"}</dd></div>
          <div><dt class="text-[var(--muted)]">Ranking preset</dt><dd>{settings.ranking_preset ?? "Not configured"}</dd></div>
        </dl>
      </section>

      <section class="shell-card rounded-[1.7rem] p-5">
        <div class="section-eyebrow">Raw config snapshot</div>
        <pre class="mt-4 overflow-x-auto rounded-[1.2rem] border border-[var(--border)] p-4 text-xs text-[var(--muted)]">{JSON.stringify(settings.raw_config, null, 2)}</pre>
      </section>
    </div>
  {/if}
</section>
