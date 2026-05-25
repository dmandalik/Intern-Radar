<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { DashboardJob } from "../lib/types";
  import { formatDate } from "../lib/format";
  import StatusPill from "./StatusPill.svelte";

  export let jobs: DashboardJob[] = [];

  const dispatch = createEventDispatcher<{
    select: { jobId: string };
    action: { jobId: string; action: string };
  }>();

  type QuickAction = { label: string; action: string } | null;

  function quickActionForJob(currentJob: DashboardJob): QuickAction {
    if (currentJob.ignored) return null;
    if (currentJob.needs_review && !currentJob.reviewed) {
      return { label: "Reviewed", action: "mark_reviewed" };
    }
    switch (currentJob.application_status) {
      case "":
        return { label: "Save", action: "save" };
      case "saved":
        return { label: "Applied", action: "mark_applied" };
      case "applied":
        return { label: "OA", action: "oa_received" };
      default:
        return null;
    }
  }
</script>

<div class="shell-card overflow-x-auto rounded-[1.6rem] p-2">
  <table class="min-w-full border-collapse text-sm">
    <thead>
      <tr class="text-left text-[0.72rem] uppercase tracking-[0.16em] text-[var(--muted)]">
        <th class="px-3 py-3">Company</th>
        <th class="px-3 py-3">Role</th>
        <th class="px-3 py-3">Status</th>
        <th class="px-3 py-3">Opp.</th>
        <th class="px-3 py-3">Hidden Gem</th>
        <th class="px-3 py-3">Location</th>
        <th class="px-3 py-3">Verified</th>
        <th class="px-3 py-3">Actions</th>
      </tr>
    </thead>
    <tbody>
      {#each jobs as job}
        <tr class="border-t border-[var(--border)] align-top">
          <td class="px-3 py-4">
            <div class="font-medium">{job.company_name}</div>
            <div class="text-xs text-[var(--muted)]">{job.title}</div>
          </td>
          <td class="px-3 py-4 text-[var(--muted)]">{job.role_family}</td>
          <td class="px-3 py-4"><StatusPill status={job.status} /></td>
          <td class="px-3 py-4 font-medium">{Math.round(job.scores.opportunity_score)}</td>
          <td class="px-3 py-4">{Math.round(job.scores.hidden_gem_score)}</td>
          <td class="px-3 py-4 text-[var(--muted)]">{job.location_label}</td>
          <td class="px-3 py-4 text-[var(--muted)]">{formatDate(job.last_verified)}</td>
          <td class="px-3 py-4">
            <div class="flex flex-wrap gap-2">
              <button class="ghost-button text-xs" on:click={() => dispatch("select", { jobId: job.id })}>Dossier</button>
              {#if quickActionForJob(job)}
                <button class="ghost-button text-xs" on:click={() => dispatch("action", { jobId: job.id, action: quickActionForJob(job)?.action ?? "save" })}>
                  {quickActionForJob(job)?.label}
                </button>
              {/if}
              {#if job.apply_url}
                <a class="ghost-button text-xs" href={job.apply_url} target="_blank" rel="noreferrer">Apply</a>
              {:else}
                <a class="ghost-button text-xs" href={job.source_url} target="_blank" rel="noreferrer">Source</a>
              {/if}
            </div>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
