/* LUNA PWA — schedule reminders + future native push payloads */
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/app";
  event.waitUntil(
    (async () => {
      const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of clients) {
        if (client.url.includes("/app") && "focus" in client) {
          try {
            client.postMessage({ type: "luna-open", url });
          } catch (_) {}
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
      return undefined;
    })()
  );
});

function notifyOptions(data) {
  const payload = data || {};
  return {
    body: payload.body || "",
    tag: payload.tag || payload.id || "luna",
    icon: "/static/live2d/luna-expressions/luna-neutral.png",
    requireInteraction: !!payload.requireInteraction || !!payload.require_interaction,
    data: { url: payload.url || "/app" },
  };
}

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type !== "notify") return;
  const title = data.title || "LUNA";
  event.waitUntil(self.registration.showNotification(title, notifyOptions(data)));
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_) {
    payload = { body: event.data ? event.data.text() : "" };
  }
  const title = payload.title || "LUNA";
  event.waitUntil(
    self.registration.showNotification(title, notifyOptions(payload))
  );
});
