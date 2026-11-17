const CACHE = "my-player-v1";
const FILES = ["/player/", "/player/manifest.webmanifest", "/player/icon.svg"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(hit => hit || fetch(event.request))
  );
});
