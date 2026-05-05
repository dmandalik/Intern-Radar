<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let theme: "dusk" | "dawn" = "dusk";

  const dispatch = createEventDispatcher<{ toggle: void }>();
</script>

<button class="ghost-button gap-2" on:click={() => dispatch("toggle")}>
  <span>{theme === "dusk" ? "Dusk" : "Dawn"}</span>
  <span class="text-xs text-[var(--muted)]">{theme === "dusk" ? "switch to light" : "switch to dark"}</span>
</button>
