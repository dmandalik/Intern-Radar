<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import JobCard from "../components/JobCard.svelte";
  import type { DashboardJob } from "../lib/types";

  export let jobs: DashboardJob[] = [];
  export let onSelectJob: (jobId: string) => void;
  export let onAction: (jobId: string, action: string) => void;

  const sections = [
    { id: "unknown_status", label: "Unknown status", matches: (job: DashboardJob) => job.status === "unknown" || job.status === "requires_login" },
    { id: "low_role_confidence", label: "Low-confidence role", matches: (job: DashboardJob) => job.role_confidence < 0.55 },
    { id: "low_eligibility_confidence", label: "Weak eligibility evidence", matches: (job: DashboardJob) => job.eligibility.confidence < 0.35 },
    { id: "missing_season_year", label: "Missing season or year", matches: (job: DashboardJob) => !job.season || !job.year },
    { id: "missing_description", label: "No description captured", matches: (job: DashboardJob) => !job.description },
  ];

  function firstReason(job: DashboardJob): string {
    return sections.find((section) => section.matches(job))?.id ?? "other";
  }

  $: groupedSections = sections
    .map((section) => ({
      ...section,
      jobs: jobs.filter((job) => firstReason(job) === section.id),
    }))
    .filter((section) => section.jobs.length > 0);
</script>

<section class="space-y-5">
  <div class="shell-card signal-card hero-orbit rounded-[1.8rem] p-6">
    <div class="section-eyebrow">Review</div>
    <h2 class="page-title mt-3">Low-confidence or incomplete roles needing a human pass.</h2>
    <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
      This queue exists so uncertain jobs do not silently pollute the shortlist. Review them by reason, then mark them reviewed or move them into the pipeline.
    </p>
  </div>

  {#if jobs.length === 0}
    <EmptyState title="No review queue right now" message="Unknown status, weak evidence, or incomplete records will show up here for manual triage." />
  {:else}
    <div class="space-y-5">
      {#each groupedSections as section}
        <section class="space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">{section.label}</h3>
            <span class="section-eyebrow">{section.jobs.length} flagged</span>
          </div>
          <div class="grid gap-4 xl:grid-cols-2">
            {#each section.jobs as job (job.id)}
              <JobCard {job} on:select={(event) => onSelectJob(event.detail.jobId)} on:action={(event) => onAction(event.detail.jobId, event.detail.action)} />
            {/each}
          </div>
        </section>
      {/each}
    </div>
  {/if}
</section>
