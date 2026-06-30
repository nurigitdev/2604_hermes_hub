const LOGIN_PATH = "/admin/login";
const DASHBOARD_PATH = "/admin/dashboard";

function showView(name) {
  document.querySelectorAll("[data-view]").forEach((view) => {
    view.hidden = view.dataset.view !== name;
  });
}

async function postJson(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  return { response, body };
}

async function fetchJson(path) {
  const response = await fetch(path, { credentials: "same-origin" });
  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  return { response, body };
}

function setLoginError(message) {
  const error = document.querySelector("[data-login-error]");
  if (!error) return;
  error.textContent = message;
  error.hidden = message === "";
}

function bindLogin() {
  showView("login");
  const form = document.querySelector("[data-login-form]");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setLoginError("");
    const submitButton = form.querySelector("button[type='submit']");
    submitButton.disabled = true;
    const formData = new FormData(form);
    const { response } = await postJson("/auth/login", {
      email: formData.get("email"),
      password: formData.get("password"),
    });
    submitButton.disabled = false;

    if (!response.ok) {
      setLoginError("Invalid email or password.");
      return;
    }

    window.location.assign(DASHBOARD_PATH);
  });
}

function setMetrics(summary) {
  Object.entries(summary).forEach(([key, value]) => {
    const target = document.querySelector(`[data-metric="${key}"]`);
    if (target) target.textContent = String(value);
  });

  const active = summary.active_agent_count || 0;
  const total = summary.total_agent_count || 0;
  const flow = (summary.messages_today_count || 0) + (summary.events_last_24h_count || 0);
  const errors = summary.error_events_last_24h_count || 0;

  document.querySelector("[data-summary='agent_coverage']").textContent =
    total === 0 ? "No agents enrolled" : `${active} of ${total} active`;
  document.querySelector("[data-summary='flow_count']").textContent = `${flow} recent records`;
  document.querySelector("[data-summary='error_pressure']").textContent =
    errors === 0 ? "No recent errors" : `${errors} recent errors`;

  const note = document.querySelector("[data-dashboard-note]");
  note.textContent =
    flow === 0
      ? "No message or event traffic has been collected in the current dashboard window."
      : "Recent message and event traffic is available for operational review.";
}

async function loadDashboard() {
  const { response: meResponse, body: me } = await fetchJson("/admin/api/me");
  if (meResponse.status === 401) {
    window.location.assign(LOGIN_PATH);
    return;
  }
  if (!meResponse.ok) {
    document.querySelector("[data-admin-identity]").textContent = "Session unavailable";
    return;
  }

  document.querySelector("[data-admin-identity]").textContent = me.name || me.email;

  const { response, body } = await fetchJson("/admin/api/dashboard/summary");
  if (!response.ok) {
    document.querySelector("[data-dashboard-note]").textContent = "Dashboard data unavailable.";
    return;
  }
  setMetrics(body);
}

function bindDashboard() {
  showView("dashboard");
  document.querySelector("[data-refresh-dashboard]")?.addEventListener("click", loadDashboard);
  document.querySelector("[data-logout]")?.addEventListener("click", async () => {
    await postJson("/auth/logout");
    window.location.assign(LOGIN_PATH);
  });
  loadDashboard();
}

if (window.location.pathname === LOGIN_PATH) {
  bindLogin();
} else {
  bindDashboard();
}
