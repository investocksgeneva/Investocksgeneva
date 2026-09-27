<script>
  import { onMount } from "svelte";
  import { route, navigate } from "./lib/router.svelte.js";
  import { player, initPlayer, bindAudioElement, bindRadioAudioElement } from "./lib/player.svelte.js";
  import MiniPlayer from "./lib/MiniPlayer.svelte";
  import Home from "./routes/Home.svelte";
  import Search from "./routes/Search.svelte";
  import Artist from "./routes/Artist.svelte";
  import Album from "./routes/Album.svelte";
  import Genre from "./routes/Genre.svelte";
  import Year from "./routes/Year.svelte";
  import NowPlaying from "./routes/NowPlaying.svelte";
  import Queue from "./routes/Queue.svelte";
  import Playlists from "./routes/Playlists.svelte";
  import Stats from "./routes/Stats.svelte";
  import Equalizer from "./routes/Equalizer.svelte";
  import Lyrics from "./routes/Lyrics.svelte";
  import Radio from "./routes/Radio.svelte";

  let audioEl;
  let radioAudioEl;

  onMount(() => {
    bindAudioElement(audioEl);
    // Deliberately never wired into the Web Audio graph (no ensureGraph
    // here) -- see player.svelte.js's module docstring for why: once an
    // element has ever been connected to Web Audio, cross-origin content
    // without CORS headers (almost every internet radio station) plays back
    // completely silent afterward. Radio gets its own untouched element so
    // it can never be tainted that way, at the cost of the EQ/visualizer
    // simply not applying to it.
    bindRadioAudioElement(radioAudioEl);
    initPlayer();
  });

  function decodeSegment(path, prefix) {
    return decodeURIComponent(path.slice(prefix.length));
  }

  const screen = $derived.by(() => {
    const path = route.path;
    if (path === "/") return { component: Home, props: {} };
    if (path === "/search") return { component: Search, props: {} };
    if (path.startsWith("/artist/")) return { component: Artist, props: { id: decodeSegment(path, "/artist/") } };
    if (path.startsWith("/album/")) return { component: Album, props: { id: decodeSegment(path, "/album/") } };
    if (path.startsWith("/genre/")) return { component: Genre, props: { id: decodeSegment(path, "/genre/") } };
    if (path.startsWith("/year/")) return { component: Year, props: { year: decodeSegment(path, "/year/") } };
    if (path === "/now-playing") return { component: NowPlaying, props: {} };
    if (path === "/queue") return { component: Queue, props: {} };
    if (path === "/playlists") return { component: Playlists, props: {} };
    if (path === "/stats") return { component: Stats, props: {} };
    if (path === "/equalizer") return { component: Equalizer, props: {} };
    if (path === "/lyrics") return { component: Lyrics, props: {} };
    if (path === "/radio") return { component: Radio, props: {} };
    return { component: Home, props: {} };
  });

  const tabs = [
    { path: "/", label: "Home", icon: "🏠" },
    { path: "/search", label: "Search", icon: "🔍" },
    { path: "/radio", label: "Radio", icon: "📻" },
    { path: "/queue", label: "Queue", icon: "🎵" },
    { path: "/playlists", label: "Playlists", icon: "📃" },
    { path: "/stats", label: "Stats", icon: "📊" },
  ];

  function isTabActive(tabPath) {
    return tabPath === "/" ? route.path === "/" : route.path.startsWith(tabPath);
  }
</script>

<audio bind:this={audioEl} preload="metadata"></audio>
<audio bind:this={radioAudioEl}></audio>

<main class="screen">
  <screen.component {...screen.props} />
</main>

<MiniPlayer />

<nav class="tabbar">
  {#each tabs as tab (tab.path)}
    <button class:active={isTabActive(tab.path)} onclick={() => navigate(tab.path)}>
      <span class="tab-icon">{tab.icon}</span>
      <span>{tab.label}</span>
    </button>
  {/each}
</nav>
