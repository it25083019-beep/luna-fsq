/** Shared auth token + post-login routing (admin vs user). */
(function (global) {
  const TOKEN_KEY = "luna_token";
  const LEGACY_KEYS = ["luna_demo_token", "luna_admin_token"];

  function getToken() {
    let t = localStorage.getItem(TOKEN_KEY);
    if (t) return t;
    for (const k of LEGACY_KEYS) {
      t = localStorage.getItem(k);
      if (t) {
        setToken(t);
        return t;
      }
    }
    return "";
  }

  function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
    LEGACY_KEYS.forEach((k) => localStorage.removeItem(k));
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    LEGACY_KEYS.forEach((k) => localStorage.removeItem(k));
  }

  const ALLOWED_NEXT = ["/app", "/admin", "/demo", "/live2d", "/luna-3d"];

  /** Resolve post-login URL. Admins default to chooser unless next=/admin. */
  function resolvePostLoginUrl(data, opts) {
    const params = new URLSearchParams(global.location.search);
    const next = (opts && opts.next) || params.get("next") || "";
    if (ALLOWED_NEXT.includes(next)) return next;
    return "/app";
  }

  /**
   * Save token and navigate.
   * Admins always get App vs Admin picker unless next is explicitly /admin
   * (or another allowed non-app demo path).
   * Returns destination string, or null when admin should pick App vs Admin.
   */
  function redirectAfterLogin(data, opts) {
    setToken(data.access_token);
    const params = new URLSearchParams(global.location.search);
    const next = (opts && opts.next) || params.get("next") || "";
    const forceChoice = !(opts && opts.forceChoice === false);
    if (data.is_admin && forceChoice) {
      if (next === "/admin") {
        global.location.href = "/admin";
        return "/admin";
      }
      if (next && next !== "/app" && ALLOWED_NEXT.includes(next)) {
        global.location.href = next;
        return next;
      }
      // next empty or /app → show destination picker
      return null;
    }
    const dest = resolvePostLoginUrl(data, opts);
    global.location.href = dest;
    return dest;
  }

  function goApp() {
    global.location.href = "/app";
  }

  function goAdmin() {
    global.location.href = "/admin";
  }

  function goLogin(nextPath) {
    const next = nextPath || global.location.pathname;
    global.location.href = "/login?next=" + encodeURIComponent(next);
  }

  function requireLogin(nextPath) {
    if (!getToken()) {
      goLogin(nextPath);
      return false;
    }
    return true;
  }

  function formatApiError(res, data) {
    const detail = data && data.detail;
    if (detail && typeof detail === "object") {
      const msg = detail.message || detail.code || "エラーが発生しました";
      const sec = detail.retry_after_seconds;
      if (res.status === 429 || detail.code === "quota_exceeded") {
        return sec ? msg + "（約" + sec + "秒後に再試行できます）" : msg;
      }
      return msg;
    }
    if (typeof detail === "string") return detail;
    return res.statusText || "リクエストに失敗しました";
  }

  global.LunaAuth = {
    TOKEN_KEY,
    getToken,
    setToken,
    clearToken,
    redirectAfterLogin,
    resolvePostLoginUrl,
    goApp,
    goAdmin,
    goLogin,
    requireLogin,
    formatApiError,
    ALLOWED_NEXT,
  };
})(window);
