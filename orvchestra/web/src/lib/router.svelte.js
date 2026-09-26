// A minimal hash router. Hash-based routing means the path the *server*
// ever sees is always "/", so there's nothing for FastAPI's SPA fallback to
// get wrong (no history-API rewrite rules, no case where a refresh on
// "/album/xyz" 404s on a host that isn't configured for it) -- a good trade
// for a personal LAN app where "#/album/xyz" in the address bar costs
// nothing real.

function parseHash() {
  const raw = window.location.hash.slice(1) || "/";
  const [path, query] = raw.split("?");
  return { path: path || "/", query: new URLSearchParams(query || "") };
}

export const route = $state(parseHash());

window.addEventListener("hashchange", () => {
  const parsed = parseHash();
  route.path = parsed.path;
  route.query = parsed.query;
});

export function navigate(path) {
  window.location.hash = path;
}
