<script>
  import { onDestroy } from "svelte";
  import { getAnalyser } from "./equalizer.svelte.js";
  import { player, THIS_DEVICE } from "./player.svelte.js";

  const BAR_COUNT = 32;
  const HEIGHT = 100;

  let canvasEl = $state(null);
  let containerWidth = $state(320);
  let rafId = null;

  function sizeCanvas() {
    if (!canvasEl || !containerWidth) return;
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = containerWidth * dpr;
    canvasEl.height = HEIGHT * dpr;
    canvasEl.style.width = `${containerWidth}px`;
    canvasEl.style.height = `${HEIGHT}px`;
    canvasEl.getContext("2d").scale(dpr, dpr);
  }

  function draw() {
    rafId = requestAnimationFrame(draw);
    const analyser = getAnalyser();
    if (!analyser || !canvasEl) return;

    const bins = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(bins);

    const ctx = canvasEl.getContext("2d");
    ctx.clearRect(0, 0, containerWidth, HEIGHT);

    const binsPerBar = Math.floor(bins.length / BAR_COUNT) || 1;
    const barWidth = containerWidth / BAR_COUNT;
    const gap = barWidth * 0.25;

    for (let i = 0; i < BAR_COUNT; i++) {
      let sum = 0;
      for (let j = 0; j < binsPerBar; j++) sum += bins[i * binsPerBar + j];
      const barHeight = (sum / binsPerBar / 255) * HEIGHT;
      ctx.fillStyle = "#7c5cff";
      ctx.fillRect(i * barWidth + gap / 2, HEIGHT - barHeight, barWidth - gap, barHeight);
    }
  }

  $effect(() => {
    sizeCanvas();
  });

  $effect(() => {
    const shouldRun = player.selectedOutput === THIS_DEVICE && player.isPlaying;
    if (shouldRun && rafId === null) {
      draw();
    } else if (!shouldRun && rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  });

  onDestroy(() => {
    if (rafId !== null) cancelAnimationFrame(rafId);
  });
</script>

{#if player.selectedOutput === THIS_DEVICE}
  <div class="visualizer-wrap" bind:clientWidth={containerWidth}>
    <canvas bind:this={canvasEl}></canvas>
  </div>
{:else}
  <p class="empty-state" style="padding:8px 0;">Visualizer only works for "This device" playback.</p>
{/if}
