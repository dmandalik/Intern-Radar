<script lang="ts">
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { getFilters, getHealth, getJob, getJobs, getSettings, getSummary, postExport, postJobAction, postJobNotes } from "./api/client";
  import EvidenceDrawer from "./components/EvidenceDrawer.svelte";
  import EmptyState from "./components/EmptyState.svelte";
  import Layout from "./components/Layout.svelte";
  import ComingSoonPage from "./pages/ComingSoon.svelte";
  import ExportPage from "./pages/Export.svelte";
  import HiddenGemsPage from "./pages/HiddenGems.svelte";
  import JobsPage from "./pages/Jobs.svelte";
  import OverviewPage from "./pages/Overview.svelte";
  import ReviewPage from "./pages/Review.svelte";
  import SavedPage from "./pages/Saved.svelte";
  import SettingsPage from "./pages/Settings.svelte";
  import { emptyQuery } from "./lib/filters";
  import type { DashboardJob, FilterOptions, JobQuery, PageId, SettingsResponse, SummaryResponse } from "./lib/types";

  const hiddenGemDefaultThreshold = 70;
  const fullDatasetQuery: JobQuery = {
    ...emptyQuery(),
    limit: 5000,
    offset: 0,
  };

  let currentPage: PageId = "overview";
  let theme: "dusk" | "dawn" = "dusk";
  let summary: SummaryResponse | null = null;
  let settings: SettingsResponse | null = null;
  let filterOptions: FilterOptions | null = null;
  let jobQuery: JobQuery = emptyQuery();
  let jobs: DashboardJob[] = [];
  let allJobs: DashboardJob[] = [];
  let jobsTotal = 0;
  let selectedJob: DashboardJob | null = null;
  let loading = true;
  let error = "";
  let search = "";
  let view: "cards" | "table" = "cards";
  let hiddenGemThreshold = hiddenGemDefaultThreshold;
  let exportBusy = false;
  let exportPaths: string[] = [];

  onMount(async () => {
    const savedTheme = window.localStorage.getItem("internradar-theme");
    if (savedTheme === "dawn" || savedTheme === "dusk") {
      theme = savedTheme;
      applyTheme();
    } else {
      applyTheme();
    }
    await refreshAll();
  });

  async function refreshAll(): Promise<void> {
    loading = true;
    error = "";
    try {
      await getHealth();
      const [summaryResponse, filtersResponse, jobsResponse, allJobsResponse, settingsResponse] = await Promise.all([
        getSummary(),
        getFilters(),
        getJobs(jobQuery),
        getJobs(fullDatasetQuery),
        getSettings()
      ]);
      summary = summaryResponse;
      filterOptions = filtersResponse;
      jobs = jobsResponse.items;
      jobsTotal = jobsResponse.total;
      allJobs = allJobsResponse.items;
      settings = settingsResponse;
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Unknown dashboard error";
    } finally {
      loading = false;
    }
  }

  async function refreshJobs(): Promise<void> {
    try {
      const response = await getJobs(jobQuery);
      jobs = response.items;
      jobsTotal = response.total;
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Unknown job loading error";
    }
  }

  function applyTheme(): void {
    document.documentElement.dataset.theme = theme;
  }

  function toggleTheme(): void {
    theme = theme === "dusk" ? "dawn" : "dusk";
    window.localStorage.setItem("internradar-theme", theme);
    applyTheme();
  }

  async function handleSearch(value: string): Promise<void> {
    search = value;
    jobQuery = { ...jobQuery, search: value || undefined, offset: 0 };
    if (value.trim().length > 0 && currentPage !== "jobs") {
      currentPage = "jobs";
    }
    await refreshJobs();
  }

  async function handleFilterChange(next: JobQuery): Promise<void> {
    jobQuery = { ...next, offset: 0 };
    search = next.search ?? "";
    await refreshJobs();
  }

  async function handleSelectJob(jobId: string): Promise<void> {
    try {
      selectedJob = await getJob(jobId);
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Unable to load job detail";
    }
  }

  async function handleAction(jobId: string, action: string): Promise<void> {
    try {
      const response = await postJobAction(jobId, action);
      selectedJob = response.job;
      await refreshAll();
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Unable to persist action";
    }
  }

  async function handleNoteSave(notes: string): Promise<void> {
    if (!selectedJob) return;
    try {
      const response = await postJobNotes(selectedJob.id, notes);
      selectedJob = response.job;
      await refreshAll();
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Unable to save notes";
    }
  }

  async function handleExport(payload: { format: string; all?: boolean }): Promise<void> {
    exportBusy = true;
    try {
      const response = await postExport({ format: payload.format, all: payload.all ?? false });
      exportPaths = response.paths;
      currentPage = "export";
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Unable to export";
    } finally {
      exportBusy = false;
    }
  }

  function navigate(page: PageId): void {
    currentPage = page;
  }

  $: hiddenGemJobs = allJobs.filter((job) => job.scores.hidden_gem_score >= hiddenGemThreshold);
  $: comingSoonJobs = allJobs.filter((job) => job.status === "coming_soon");
  $: savedJobs = allJobs.filter((job) => Boolean(job.application_status));
  $: reviewJobs = allJobs.filter((job) => job.needs_review);
</script>

<Layout
  {currentPage}
  {summary}
  {search}
  activePack={summary?.pack ?? settings?.active_pack ?? null}
  lastScanAt={summary?.last_scan_at ?? null}
  {theme}
  onNavigate={navigate}
  onSearch={handleSearch}
  onThemeToggle={toggleTheme}
  onExportNavigate={() => navigate("export")}
>
  {#if loading}
    <div class="shell-card rounded-[1.8rem] p-12 text-center text-[var(--muted)]">Loading local radar data…</div>
  {:else if error}
    <EmptyState title="Dashboard unavailable" message={error} />
  {:else}
    {#key currentPage}
      <div class="page-shell" transition:fade={{ duration: 170 }}>
        {#if currentPage === "overview"}
          <OverviewPage {summary} onSelectJob={handleSelectJob} onAction={handleAction} onNavigate={navigate} />
        {:else if currentPage === "jobs"}
          <JobsPage
            {jobs}
            total={jobsTotal}
            {view}
            filters={jobQuery}
            options={filterOptions}
            onFilterChange={handleFilterChange}
            onSelectJob={handleSelectJob}
            onAction={handleAction}
            onViewChange={(next) => (view = next)}
          />
        {:else if currentPage === "hidden_gems"}
          <HiddenGemsPage
            jobs={hiddenGemJobs}
            threshold={hiddenGemThreshold}
            onThresholdChange={(value) => (hiddenGemThreshold = value)}
            onSelectJob={handleSelectJob}
            onAction={handleAction}
          />
        {:else if currentPage === "coming_soon"}
          <ComingSoonPage jobs={comingSoonJobs} onSelectJob={handleSelectJob} onAction={handleAction} />
        {:else if currentPage === "saved"}
          <SavedPage jobs={savedJobs} onSelectJob={handleSelectJob} onAction={handleAction} />
        {:else if currentPage === "review"}
          <ReviewPage jobs={reviewJobs} onSelectJob={handleSelectJob} onAction={handleAction} />
        {:else if currentPage === "settings"}
          <SettingsPage {settings} />
        {:else if currentPage === "export"}
          <ExportPage busy={exportBusy} resultPaths={exportPaths} onExport={handleExport} />
        {/if}
      </div>
    {/key}
  {/if}
</Layout>

<EvidenceDrawer
  job={selectedJob}
  on:close={() => (selectedJob = null)}
  on:noteSave={(event) => handleNoteSave(event.detail.notes)}
  on:action={(event) => handleAction(event.detail.jobId, event.detail.action)}
/>
