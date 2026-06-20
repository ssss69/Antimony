(function () {
  const API = window.ANTIMONY_API || (window.location.protocol === "file:" ? "http://127.0.0.1:8765" : window.location.origin);
  window.ANTIMONY_API = API;

  const state = {
    enabled: false,
    url: "",
    anonKey: "",
    session: null,
    cloudSessionId: crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`,
  };

  function authHeaders(token = state.session?.access_token) {
    const headers = { apikey: state.anonKey, "Content-Type": "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  function saveSession(session) {
    state.session = session;
    if (session) localStorage.setItem("antimony_cloud_session", JSON.stringify(session));
    else localStorage.removeItem("antimony_cloud_session");
    renderAccount();
  }

  function renderAccount() {
    const button = document.querySelector("#accountButton");
    const overlay = document.querySelector("#authOverlay");
    const label = document.querySelector("#accountLabel");
    const form = document.querySelector("#authForm");
    const panel = document.querySelector("#accountPanel");
    const accountEmail = document.querySelector("#accountEmail");
    const close = document.querySelector("#authClose");
    if (!button) return;
    if (!state.enabled) {
      button.hidden = true;
      overlay.hidden = true;
      return;
    }
    button.hidden = false;
    if (state.session?.user) {
      label.textContent = state.session.user.email || "Cloud Account";
      overlay.hidden = true;
      form.hidden = true;
      panel.hidden = false;
      accountEmail.textContent = state.session.user.email || "Cloud account connected";
      close.hidden = false;
    } else {
      label.textContent = "Sign in";
      overlay.hidden = false;
      form.hidden = false;
      panel.hidden = true;
      close.hidden = true;
    }
  }

  async function validateSession() {
    if (!state.session?.access_token) return false;
    try {
      const response = await fetch(`${state.url}/auth/v1/user`, { headers: authHeaders() });
      if (!response.ok) throw new Error("Session expired");
      const user = await response.json();
      state.session.user = user;
      saveSession(state.session);
      return true;
    } catch {
      saveSession(null);
      return false;
    }
  }

  async function init() {
    const runtimeConfig = window.ANTIMONY_CONFIG || {};
    state.url = runtimeConfig.supabaseUrl || "";
    state.anonKey = runtimeConfig.supabaseAnonKey || "";
    state.enabled = Boolean(state.url && state.anonKey);
    if (!state.enabled) {
      try {
        const response = await fetch(`${API}/cloud/config`);
        if (!response.ok) throw new Error("Cloud config unavailable");
        const config = await response.json();
        state.enabled = Boolean(config.enabled);
        state.url = config.supabase_url || "";
        state.anonKey = config.anon_key || "";
      } catch {
        state.enabled = false;
      }
    }
    try { state.session = JSON.parse(localStorage.getItem("antimony_cloud_session") || "null"); } catch { state.session = null; }
    if (state.enabled && state.session) await validateSession();
    renderAccount();
    return state;
  }

  async function authenticate(email, password, mode) {
    const endpoint = mode === "signup" ? "signup" : "token?grant_type=password";
    const response = await fetch(`${state.url}/auth/v1/${endpoint}`, {
      method: "POST",
      headers: authHeaders(null),
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.msg || data.error_description || data.message || "Authentication failed");
    if (data.access_token) saveSession(data);
    return data;
  }

  async function cloudInsert(table, row) {
    if (!state.enabled || !state.session?.access_token) return;
    const response = await fetch(`${state.url}/rest/v1/${table}`, {
      method: "POST",
      headers: { ...authHeaders(), Prefer: "return=minimal" },
      body: JSON.stringify(row),
    });
    if (!response.ok) throw new Error(`Cloud sync failed for ${table}`);
  }

  async function cloudSelect(table, query) {
    if (!state.enabled || !state.session?.access_token) return [];
    const response = await fetch(`${state.url}/rest/v1/${table}?${query}`, { headers: authHeaders() });
    if (!response.ok) throw new Error(`Cloud read failed for ${table}`);
    return response.json();
  }

  async function syncMessage(role, content, persona) {
    if (!state.session?.user) return;
    return cloudInsert("antimony_messages", {
      user_id: state.session.user.id,
      session_id: state.cloudSessionId,
      persona,
      role,
      content,
    });
  }

  async function syncAgent(key, agent) {
    if (!state.session?.user) return;
    const response = await fetch(`${state.url}/rest/v1/antimony_agents?on_conflict=user_id,agent_key`, {
      method: "POST",
      headers: { ...authHeaders(), Prefer: "resolution=merge-duplicates,return=minimal" },
      body: JSON.stringify({ user_id: state.session.user.id, agent_key: key, profile: agent, visibility: agent.visibility || "private" }),
    });
    if (!response.ok) throw new Error("Cloud agent sync failed");
  }

  async function listChats() {
    const rows = await cloudSelect("antimony_messages", "select=session_id,persona,role,content,created_at&order=created_at.desc&limit=500");
    const sessions = new Map();
    rows.forEach(row => {
      if (!sessions.has(row.session_id)) sessions.set(row.session_id, { id: row.session_id, persona: row.persona, title: row.content.slice(0, 42), created_at: row.created_at });
      if (row.role === "user") sessions.get(row.session_id).title = row.content.slice(0, 42);
    });
    return [...sessions.values()];
  }

  async function loadChat(sessionId) {
    return cloudSelect("antimony_messages", `select=persona,role,content,created_at&session_id=eq.${encodeURIComponent(sessionId)}&order=created_at.asc`);
  }

  function newChat() {
    state.cloudSessionId = crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
  }

  function signOut() {
    saveSession(null);
    renderAccount();
  }

  window.AntimonyCloud = { state, init, authenticate, syncMessage, syncAgent, listChats, loadChat, newChat, signOut, renderAccount };
})();
