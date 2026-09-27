<script>
  import { onMount } from "svelte";
  import {
    eq,
    EQ_BANDS,
    EQ_PRESETS,
    setEnabled,
    setBandGain,
    applyPreset,
    resetEq,
  } from "../lib/equalizer.svelte.js";
  import { enableWebAudioGraph } from "../lib/player.svelte.js";

  // Opening this screen is the explicit signal that Web Audio should get
  // involved at all -- see player.svelte.js's enableWebAudioGraph for why
  // that's not just done automatically on every play.
  onMount(() => {
    enableWebAudioGraph();
  });
</script>

<h1>Equalizer</h1>

<div class="top-bar">
  <span class="section-title" style="margin:0;">This device only</span>
  <button class="link-button" onclick={() => setEnabled(!eq.enabled)}>
    {eq.enabled ? "On" : "Off"}
  </button>
</div>

<p class="empty-state" style="padding:10px 0; text-align:left;">
  This only shapes audio played through "This device" (your Mac or phone's own speakers).
  Playing on the WiiM Amp Pro streams straight from the engine to it, bypassing the browser,
  so this has no effect there -- use the WiiM Home app's own EQ for that output instead.
</p>

<div class="section-title">Presets</div>
<div class="output-picker">
  {#each Object.keys(EQ_PRESETS) as name (name)}
    <button class="output-option" onclick={() => applyPreset(name)}>
      <span>{name}</span>
    </button>
  {/each}
  <button class="link-button" onclick={resetEq}>Reset to flat</button>
</div>

<div class="section-title">Bands</div>
<div class="row-list">
  {#each EQ_BANDS as band, i (band.freq)}
    <div class="volume-row">
      <span style="width:52px; flex-shrink:0;">{band.label}</span>
      <input
        type="range"
        min="-12"
        max="12"
        step="0.5"
        value={eq.gains[i]}
        disabled={!eq.enabled}
        oninput={(event) => setBandGain(i, Number(event.target.value))}
      />
      <span style="width:40px; flex-shrink:0; text-align:right;">{eq.gains[i].toFixed(1)}</span>
    </div>
  {/each}
</div>
