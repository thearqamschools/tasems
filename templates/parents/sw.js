// Parent portal service worker (M8). Pages always come from the server (they hold children's details and are
// never stored on the phone); only the stylesheet, logo and the "no internet" page are kept for offline use.
const CACHE = "arqam-parents-v1";
const OFFLINE = "/parents/offline/";
const ASSETS = [OFFLINE{% for a in assets %}, "{{ a|escapejs }}"{% endfor %}];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
    return;
  }
  if (ASSETS.includes(new URL(request.url).pathname)) {
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});
