<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import JobCard from "../components/JobCard.svelte";
  import type { DashboardJob } from "../lib/types";

  export let jobs: DashboardJob[] = [];
  export let onSelectJob: (jobId: string) => void;
  export let onAction: (jobId: string, action: string) => void;
</script>

<section class="space-y-5">
  <div class="shell-card rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Review</div>
    <h2 class="page-title mt-3">Low-confidence or incomplete roles needing a human pass.</h2>
  </div>

  {#if jobs.length === 0}
    <EmptyState title="No review queue right now" message="Unknown status, weak evidence, or incomplete records will show up here for manual triage." />
  {:else}
    <div class="grid gap-4 xl:grid-cols-2">
      {#each jobs as job (job.id)}
        <JobCard {job} on:select={(event) => onSelectJob(event.detail.jobId)} on:action={(event) => onAction(event.detail.jobId, event.detail.action)} />
      {/each}
    </div>
  {/if}
</section>
