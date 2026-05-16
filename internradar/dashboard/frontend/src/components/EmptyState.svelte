<script lang="ts">
  export let title: string;
  export let message: string;
</script>

<div class="shell-card signal-card rounded-[1.6rem] p-10 text-center">
  <div class="section-eyebrow">No signal</div>
  <h3 class="mt-3 text-2xl font-semibold">{title}</h3>
  <p class="mx-auto mt-2 max-w-xl text-sm text-[var(--muted)]">{message}</p>
</div>
