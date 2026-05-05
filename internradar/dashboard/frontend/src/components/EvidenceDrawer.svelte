<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { fly, fade } from "svelte/transition";
  import type { DashboardJob } from "../lib/types";
  import { formatDateTime, formatLabel } from "../lib/format";
  import StatusPill from "./StatusPill.svelte";

  export let job: DashboardJob | null = null;

  const dispatch = createEventDispatcher<{ close: void; noteSave: { notes: string } }>();
  let draftNotes = "";

  $: if (job) {
    draftNotes = job.notes ?? "";
  }
</script>

{#if job}
  <div
    class="fixed inset-0 z-50 flex justify-end bg-black/45"
    transition:fade
    role="presentation"
    on:click={() => dispatch("close")}
  >
    <div
      class="shell-card h-full w-full max-w-[38rem] overflow-y-auto rounded-none rounded-l-[2rem] p-6"
      transition:fly={{ x: 24, duration: 180 }}
      role="dialog"
      aria-modal="true"
      tabindex="-1"
      on:click|stopPropagation
      on:keydown|stopPropagation={() => {}}
    >
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="section-eyebrow">{job.company_name}</div>
          <h2 class="mt-2 text-2xl font-semibold tracking-tight">{job.title}</h2>
          <div class="mt-3 flex flex-wrap gap-2">
            <StatusPill status={job.status} />
            <span class="status-pill">{job.role_family}</span>
            <span class="status-pill">{job.location_label}</span>
          </div>
        </div>
        <button class="ghost-button" on:click={() => dispatch("close")}>Close</button>
      </div>

      <div class="mt-6 grid gap-5">
        <section class="glass-panel rounded-[1.4rem] p-4">
          <div class="section-eyebrow">Scoring explanation</div>
          <ul class="mt-3 space-y-2 text-sm text-[var(--muted)]">
            {#each job.score_explanation as item}
              <li>• {item}</li>
            {/each}
          </ul>
        </section>

        <section class="glass-panel rounded-[1.4rem] p-4">
          <div class="section-eyebrow">Eligibility evidence</div>
          <ul class="mt-3 space-y-2 text-sm text-[var(--muted)]">
            {#each job.eligibility.raw_evidence as item}
              <li>• {item}</li>
            {/each}
          </ul>
        </section>

        <section class="glass-panel rounded-[1.4rem] p-4">
          <div class="section-eyebrow">Role and status evidence</div>
          <div class="mt-3 grid gap-4 sm:grid-cols-2">
            <div>
              <div class="mono-label text-xs uppercase tracking-[0.16em] text-[var(--muted)]">Role evidence</div>
              <ul class="mt-2 space-y-2 text-sm text-[var(--muted)]">
                {#each job.role_evidence as item}
                  <li>• {item}</li>
                {/each}
              </ul>
            </div>
            <div>
              <div class="mono-label text-xs uppercase tracking-[0.16em] text-[var(--muted)]">Status evidence</div>
              <ul class="mt-2 space-y-2 text-sm text-[var(--muted)]">
                {#each job.status_evidence as item}
                  <li>• {item}</li>
                {/each}
              </ul>
            </div>
          </div>
        </section>

        <section class="glass-panel rounded-[1.4rem] p-4">
          <div class="section-eyebrow">Audit trail</div>
          <dl class="mt-3 grid gap-3 text-sm sm:grid-cols-2">
            <div><dt class="text-[var(--muted)]">First seen</dt><dd>{formatDateTime(job.first_seen)}</dd></div>
            <div><dt class="text-[var(--muted)]">Last verified</dt><dd>{formatDateTime(job.last_verified)}</dd></div>
            <div><dt class="text-[var(--muted)]">Application state</dt><dd>{job.application_status ? formatLabel(job.application_status) : "Not set"}</dd></div>
            <div><dt class="text-[var(--muted)]">Source</dt><dd>{job.source_type}</dd></div>
          </dl>
        </section>

        <section class="glass-panel rounded-[1.4rem] p-4">
          <div class="section-eyebrow">Notes</div>
          <textarea class="surface-input mt-3 min-h-32 w-full" bind:value={draftNotes}></textarea>
          <div class="mt-3 flex justify-end">
            <button class="radar-button" on:click={() => dispatch("noteSave", { notes: draftNotes })}>Save notes</button>
          </div>
        </section>

        <section class="glass-panel rounded-[1.4rem] p-4">
          <div class="section-eyebrow">Links</div>
          <div class="mt-3 flex flex-wrap gap-3 text-sm">
            <a class="ghost-button" href={job.apply_url} target="_blank" rel="noreferrer">Apply</a>
            <a class="ghost-button" href={job.source_url} target="_blank" rel="noreferrer">Source</a>
          </div>
        </section>
      </div>
    </div>
  </div>
{/if}
