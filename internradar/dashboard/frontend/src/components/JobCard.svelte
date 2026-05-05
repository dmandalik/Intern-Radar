<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { DashboardJob } from "../lib/types";
  import { formatDate, formatLabel } from "../lib/format";
  import ScorePill from "./ScorePill.svelte";
  import StatusPill from "./StatusPill.svelte";

  export let job: DashboardJob;
  export let emphasizeHiddenGem = false;

  const dispatch = createEventDispatcher<{
    select: { jobId: string };
    action: { jobId: string; action: string };
  }>();
</script>

<article class={`shell-card rounded-[1.6rem] p-5 ${emphasizeHiddenGem ? "ring-1 ring-[var(--warning)]/35" : ""}`}>
  <div class="flex items-start justify-between gap-4">
    <div>
      <div class="section-eyebrow">{job.company_name}</div>
      <h3 class="mt-2 text-xl font-semibold tracking-tight">{job.title}</h3>
      <div class="mt-2 flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
        <span>{job.role_family}</span>
        <span>•</span>
        <span>{job.location_label}</span>
        <span>•</span>
        <span>{job.season ?? "Season TBD"} {job.year ?? ""}</span>
      </div>
    </div>
    <StatusPill status={job.status} />
  </div>

  <div class="mt-4 flex flex-wrap gap-2">
    <ScorePill label="Opp." value={job.scores.opportunity_score} />
    <ScorePill label="Fit" value={job.scores.role_fit_score} accent="var(--accent-2)" />
    <ScorePill label="Elig." value={job.scores.eligibility_score} accent="var(--info)" />
    <ScorePill label="Gem" value={job.scores.hidden_gem_score} accent="var(--warning)" />
  </div>

  <p class="mt-4 line-clamp-3 text-sm leading-6 text-[var(--muted)]">
    {job.description ?? "No description captured yet."}
  </p>

  <div class="mt-4 flex flex-wrap gap-2 text-xs text-[var(--muted)]">
    <span class="mono-label rounded-full border border-[var(--border)] px-3 py-1">{job.source_type}</span>
    <span class="mono-label rounded-full border border-[var(--border)] px-3 py-1">{job.prestige_tier ?? "Unknown prestige"}</span>
    <span class="mono-label rounded-full border border-[var(--border)] px-3 py-1">Verified {formatDate(job.last_verified)}</span>
    {#if job.application_status}
      <span class="mono-label rounded-full border border-[var(--border)] px-3 py-1">{formatLabel(job.application_status)}</span>
    {/if}
  </div>

  <div class="mt-5 flex flex-wrap gap-2">
    <button class="ghost-button" on:click={() => dispatch("select", { jobId: job.id })}>View evidence</button>
    <button class="ghost-button" on:click={() => dispatch("action", { jobId: job.id, action: "save" })}>Save</button>
    <button class="ghost-button" on:click={() => dispatch("action", { jobId: job.id, action: "mark_applied" })}>Applied</button>
    <a class="radar-button" href={job.apply_url} target="_blank" rel="noreferrer">Open apply link</a>
  </div>
</article>
