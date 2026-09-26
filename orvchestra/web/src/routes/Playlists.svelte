<script>
  import { onMount } from "svelte";
  import { api } from "../lib/api.js";

  let playlists = $state([]);

  onMount(async () => {
    playlists = await api.playlists();
  });
</script>

<h1>Playlists</h1>

{#if playlists.length === 0}
  <p class="empty-state">No playlists yet. Creating playlists (and smart playlists) arrives in Phase 4.</p>
{:else}
  <div class="row-list">
    {#each playlists as playlist (playlist.id)}
      <div class="row-item">
        <div class="row-text">
          <div class="row-title">{playlist.name}</div>
          {#if playlist.description}<div class="row-subtitle">{playlist.description}</div>{/if}
        </div>
      </div>
    {/each}
  </div>
{/if}
