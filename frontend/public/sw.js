self.addEventListener("push", event => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch { payload = { body: event.data ? event.data.text() : "A new alert is available." }; }
  event.waitUntil(self.registration.showNotification(payload.title || "Nathan Terminal alert", {
    body: payload.body || "Review your terminal for an update.",
    icon: "/icon.svg", badge: "/icon.svg",
    tag: payload.tag || "nathan-terminal-alert", renotify: false,
    data: { url: payload.url || "/", event_id: payload.event_id || null }
  }));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil((async () => {
    const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of clients) {
      if (client.url.startsWith(self.location.origin) && "focus" in client) { await client.focus(); return; }
    }
    if (self.clients.openWindow) await self.clients.openWindow(target);
  })());
});
