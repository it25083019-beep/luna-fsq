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
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes("/app") && "focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
      return undefined;
    })
  );
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type !== "notify") return;
  const title = data.title || "LUNA";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || "",
      tag: data.tag || "luna",
      icon: "/static/live2d/luna-expressions/luna-neutral.png",
      data: { url: data.url || "/app" },
    })
  );
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
    self.registration.showNotification(title, {
      body: payload.body || "今日の予定を確認してね",
      tag: payload.tag || payload.id || "luna-push",
      icon: "/static/live2d/luna-expressions/luna-neutral.png",
      data: { url: payload.url || "/app" },
    })
  );
});
