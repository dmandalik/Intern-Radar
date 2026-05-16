<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import JobCard from "../components/JobCard.svelte";
  import MetricCard from "../components/MetricCard.svelte";
  import MiniBarChart from "../components/MiniBarChart.svelte";
  import type { SummaryResponse, DashboardJob } from "../lib/types";

  export let summary: SummaryResponse | null = null;

  export let onSelectJob: (jobId: string) => void;
  export let onAction: (jobId: string, action: string) => void;
  export let onNavigate: (page: "jobs" | "review" | "saved" | "coming_soon" | "hidden_gems") => void;
</script>

{#if !summary}
  <EmptyState title="No dashboard summary yet" message="Run a scan to generate the first live command-center view." />
{:else}
  <section class="space-y-5">
    <div class="shell-card signal-card hero-orbit rounded-[1.8rem] p-6">
      <div class="section-eyebrow">Overview</div>
      <h2 class="page-title mt-3">Your internship radar is live.</h2>
      <p class="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted)]">
        Local scan data, scoring, and evidence are all loaded. Start with the top apply-now roles,
        then sweep for hidden gems and watchlist signals before the next cycle opens.
      </p>
      <div class="mt-5 flex flex-wrap gap-2">
        <button class="radar-button" on:click={() => onNavigate("jobs")}>Open ranked jobs</button>
        <button class="ghost-button" on:click={() => onNavigate("review")}>Review uncertain roles</button>
        <button class="ghost-button" on:click={() => onNavigate("saved")}>Open pipeline</button>
      </div>
    </div>

    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Total Jobs" value={summary.total_jobs} hint="Normalized and deduplicated." />
      <MetricCard label="Open Roles" value={summary.counts.open + summary.counts.likely_open} hint="Immediate attention window." accent="var(--success)" />
      <MetricCard label="Hidden Gems" value={summary.counts.hidden_gems} hint="Credible, technical, less obvious." accent="var(--warning)" />
      <MetricCard label="Tracked / Applied" value={`${summary.counts.saved} / ${summary.counts.applied}`} hint="Application workflow state." accent="var(--accent-2)" />
    </div>

    <div class="grid gap-4 xl:grid-cols-3">
      <section class="shell-card signal-card rounded-[1.6rem] p-5">
        <div class="section-eyebrow">Do now</div>
        <h3 class="mt-2 text-xl font-semibold">Highest-value next moves.</h3>
        <div class="mt-4 space-y-3 text-sm text-[var(--muted)]">
          <button class="flex w-full items-center justify-between rounded-2xl border border-[var(--border)] px-4 py-3 text-left" on:click={() => onNavigate("jobs")}>
            <span>Apply-first queue</span>
            <span class="mono-label text-xs text-[var(--text)]">{summary.apply_first.length}</span>
          </button>
          <button class="flex w-full items-center justify-between rounded-2xl border border-[var(--border)] px-4 py-3 text-left" on:click={() => onNavigate("review")}>
            <span>Review needed</span>
            <span class="mono-label text-xs text-[var(--text)]">{summary.counts.review_needed}</span>
          </button>
          <button class="flex w-full items-center justify-between rounded-2xl border border-[var(--border)] px-4 py-3 text-left" on:click={() => onNavigate("coming_soon")}>
            <span>Watchlist signals</span>
            <span class="mono-label text-xs text-[var(--text)]">{summary.counts.coming_soon}</span>
          </button>
        </div>
      </section>

      <section class="shell-card signal-card rounded-[1.6rem] p-5">
        <div class="section-eyebrow">Focus mode</div>
        <h3 class="mt-2 text-xl font-semibold">Where this scan is strongest.</h3>
        <ul class="mt-4 space-y-3 text-sm text-[var(--muted)]">
          <li>• Open and likely-open roles are already separated for apply-now triage.</li>
          <li>• Hidden gems emphasize credible technical roles, not just obscure names.</li>
          <li>• Review mode isolates low-confidence records before they distort your shortlist.</li>
        </ul>
      </section>

      <section class="shell-card signal-card rounded-[1.6rem] p-5">
        <div class="section-eyebrow">Workflow pulse</div>
        <h3 class="mt-2 text-xl font-semibold">Tracked roles and momentum.</h3>
        <div class="mt-4 grid gap-3 sm:grid-cols-2">
          <div class="glass-panel rounded-[1.2rem] p-4">
            <div class="section-eyebrow">Tracked</div>
            <div class="mt-2 text-3xl font-semibold">{summary.counts.saved}</div>
          </div>
          <div class="glass-panel rounded-[1.2rem] p-4">
            <div class="section-eyebrow">Applied</div>
            <div class="mt-2 text-3xl font-semibold">{summary.counts.applied}</div>
          </div>
        </div>
      </section>
    </div>

    <div class="grid gap-5 xl:grid-cols-[1.4fr_0.9fr]">
      <section class="space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-xl font-semibold">Apply first</h3>
          <span class="section-eyebrow">Top 5 by opportunity</span>
        </div>
        {#if summary.apply_first.length === 0}
          <EmptyState title="No open roles yet" message="Once the scan finds open or likely-open jobs, they will surface here first." />
        {:else}
          <div class="grid gap-4">
            {#each summary.apply_first as job (job.id)}
              <JobCard {job} on:select={(event) => onSelectJob(event.detail.jobId)} on:action={(event) => onAction(event.detail.jobId, event.detail.action)} />
            {/each}
          </div>
        {/if}
      </section>

      <div class="grid gap-4">
        <MiniBarChart title="Jobs by status" rows={summary.charts.status} />
        <MiniBarChart title="Role families" rows={summary.charts.role_family} />
        <MiniBarChart title="Top companies" rows={summary.charts.top_companies} />
      </div>
    </div>

    <div class="grid gap-5 xl:grid-cols-3">
      <section class="shell-card signal-card rounded-[1.7rem] p-5">
        <div class="section-eyebrow">Hidden gems found</div>
        <div class="mt-3 space-y-3">
          {#each summary.signals.hidden_gems as job (job.id)}
            <button class="w-full rounded-2xl border border-[var(--border)] p-3 text-left" on:click={() => onSelectJob(job.id)}>
              <div class="font-medium">{job.company_name}</div>
              <div class="text-sm text-[var(--muted)]">{job.title}</div>
            </button>
          {/each}
        </div>
      </section>

      <section class="shell-card signal-card rounded-[1.7rem] p-5">
        <div class="section-eyebrow">Coming soon watchlist</div>
        <div class="mt-3 space-y-3">
          {#each summary.signals.coming_soon as job (job.id)}
            <button class="w-full rounded-2xl border border-[var(--border)] p-3 text-left" on:click={() => onSelectJob(job.id)}>
              <div class="font-medium">{job.company_name}</div>
              <div class="text-sm text-[var(--muted)]">{job.title}</div>
            </button>
          {/each}
        </div>
      </section>

      <section class="shell-card signal-card rounded-[1.7rem] p-5">
        <div class="section-eyebrow">Review needed</div>
        <div class="mt-3 space-y-3">
          {#each summary.signals.review_needed as job (job.id)}
            <button class="w-full rounded-2xl border border-[var(--border)] p-3 text-left" on:click={() => onSelectJob(job.id)}>
              <div class="font-medium">{job.company_name}</div>
              <div class="text-sm text-[var(--muted)]">{job.title}</div>
            </button>
          {/each}
        </div>
      </section>
    </div>
  </section>
{/if}
