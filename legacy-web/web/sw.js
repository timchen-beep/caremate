/* CareMate service worker：外壳可离线，接口永远走网络（离线时页面提示"离线"，不假装成功） */
const CACHE = "caremate-shell-v1";
const SHELL = ["/app", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // 接口：只走网络，失败就如实失败（不缓存健康数据）
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(JSON.stringify({ error: "离线：连不上云端，记录会留在本机队列" }),
          { status: 503, headers: { "Content-Type": "application/json; charset=utf-8" } })
      )
    );
    return;
  }

  // 导航请求：网络优先，断网回落到缓存的应用外壳
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request).catch(() => caches.match("/app").then((r) => r || caches.match("/app")))
    );
    return;
  }

  // 静态资源：缓存优先
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match(e.request)))
  );
});
