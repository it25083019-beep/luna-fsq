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

  function redirectAfterLogin(data) {
    setToken(data.access_token);
    const params = new URLSearchParams(location.search);
    const next = params.get("next") || "";
    if (data.is_admin) {
      global.location.href = "/admin";
      return;
    }
    const safeNext = ["/demo", "/live2d"].includes(next) ? next : "/demo";
    global.location.href = safeNext;
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

  global.LunaAuth = { TOKEN_KEY, getToken, setToken, clearToken, redirectAfterLogin, goLogin, requireLogin };
})(window);
