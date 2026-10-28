// Heatline service worker: makes the app installable, keeps the page shell for a flaky pool-side connection,
// and opens the app when an alert is tapped. Results are always fetched fresh.
const SHELL = "hl-shell-v1";
self.addEventListener("install", e => { self.skipWaiting(); e.waitUntil(caches.open(SHELL).then(c => c.addAll(["/heatline/", "/heatline/icon.svg", "/heatline/icon-192.png"])).catch(() => {})); });
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.mode === "navigate" && u.pathname.startsWith("/heatline")) {
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(SHELL).then(x => x.put("/heatline/", c)); return r; }).catch(() => caches.match("/heatline/")));
  }
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window" }).then(cs => cs.length ? cs[0].focus() : self.clients.openWindow("/heatline/")));
});
