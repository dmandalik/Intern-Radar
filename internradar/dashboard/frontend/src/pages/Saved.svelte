<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import JobCard from "../components/JobCard.svelte";
  import type { DashboardJob } from "../lib/types";

  export let jobs: DashboardJob[] = [];
  export let onSelectJob: (jobId: string) => void;
  export let onAction: (jobId: string, action: string) => void;

  const lanes = [
    { id: "saved", label: "Saved" },
    { id: "applied", label: "Applied" },
    { id: "oa_received", label: "OA Received" },
    { id: "interviewing", label: "Interviewing" },
    { id: "rejected", label: "Rejected" },
    { id: "offer", label: "Offer" },
    { id: "not_interested", label: "Not Interested" }
  ];
</script>

<section class="space-y-5">
  <div class="shell-card rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Workflow</div>
    <h2 class="page-title mt-3">Saved roles and application progress.</h2>
  </div>

  {#if jobs.length === 0}
    <EmptyState title="No saved or tracked jobs yet" message="Use the save and application actions from the jobs pages to build your pipeline here." />
  {:else}
    <div class="space-y-5">
      {#each lanes as lane}
        <section class="space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">{lane.label}</h3>
            <span class="section-eyebrow">{jobs.filter((job) => job.application_status === lane.id).length} tracked</span>
          </div>
          <div class="grid gap-4 xl:grid-cols-2">
            {#each jobs.filter((job) => job.application_status === lane.id) as job (job.id)}
              <JobCard {job} on:select={(event) => onSelectJob(event.detail.jobId)} on:action={(event) => onAction(event.detail.jobId, event.detail.action)} />
            {/each}
          </div>
        </section>
      {/each}
    </div>
  {/if}
</section>
