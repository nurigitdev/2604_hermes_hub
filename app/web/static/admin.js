const LOGIN_PATH = "/admin/login";
const DASHBOARD_PATH = "/admin/dashboard";
const AGENTS_PATH = "/admin/agents";

const PAGE_TITLES = {
  [DASHBOARD_PATH]: "Dashboard",
  [AGENTS_PATH]: "Agent Registry",
};

function showView(name) {
  document.querySelectorAll("[data-view]").forEach((view) => {
    view.hidden = view.dataset.view !== name;
  });
}

async function postJson(path, payload = {}) {
  return requestJson(path, { method: "POST", payload });
}

async function patchJson(path, payload = {}) {
  return requestJson(path, { method: "PATCH", payload });
}

async function requestJson(path, { method, payload = {} }) {
  const response = await fetch(path, {
    method,
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

async function loadAdminIdentity() {
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
  return true;
}

async function loadDashboard() {
  const { response, body } = await fetchJson("/admin/api/dashboard/summary");
  if (!response.ok) {
    document.querySelector("[data-dashboard-note]").textContent = "Dashboard data unavailable.";
    return;
  }
  setMetrics(body);
}

function setActivePage(pageName) {
  const title = PAGE_TITLES[window.location.pathname] || PAGE_TITLES[DASHBOARD_PATH];
  document.querySelector("[data-page-title]").textContent = title;
  document.querySelectorAll("[data-page]").forEach((page) => {
    page.hidden = page.dataset.page !== pageName;
  });
  document.querySelectorAll("[data-nav]").forEach((navItem) => {
    navItem.classList.toggle("active", navItem.dataset.nav === pageName);
  });
}

function agentStatusClass(status) {
  return `status-badge status-${status.toLowerCase()}`;
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderAgents(items) {
  const rows = document.querySelector("[data-agent-rows]");
  if (!rows) return;
  if (items.length === 0) {
    rows.innerHTML = '<tr><td colspan="6">No agents match the current filters.</td></tr>';
    return;
  }

  rows.innerHTML = items
    .map((agent) => {
      const displayName = agent.display_name || "";
      const ownerEmail = agent.owner_email || "";
      const disabled = agent.status === "DISABLED" ? "disabled" : "";
      return `
        <tr data-agent-uid="${escapeHtml(agent.agent_uid)}">
          <td data-label="Agent">
            <div class="cell-stack">
              <strong>${escapeHtml(displayName || agent.profile_name)}</strong>
              <span>${escapeHtml(agent.agent_uid)}</span>
              <span>${escapeHtml(agent.profile_name)}</span>
            </div>
          </td>
          <td data-label="Owner">${escapeHtml(ownerEmail || "-")}</td>
          <td data-label="Runtime">
            <div class="cell-stack">
              <strong>${escapeHtml(agent.source)}</strong>
              <span>${escapeHtml(agent.hostname)} / ${escapeHtml(agent.ip_addr)}</span>
            </div>
          </td>
          <td data-label="Status">
            <span class="${agentStatusClass(agent.status)}">${escapeHtml(agent.status)}</span>
          </td>
          <td data-label="Last seen">${escapeHtml(formatDateTime(agent.last_seen_at))}</td>
          <td data-label="Actions">
            <div class="row-actions">
              <input
                aria-label="Display name for ${escapeHtml(agent.agent_uid)}"
                data-agent-display-name
                placeholder="Display name"
                type="text"
                value="${escapeHtml(displayName)}"
              />
              <button class="secondary-button" data-agent-action="save-display-name" type="button">
                Save
              </button>
              <input
                aria-label="Owner email for ${escapeHtml(agent.agent_uid)}"
                data-agent-owner-email
                placeholder="owner@example.com"
                type="email"
                value="${escapeHtml(ownerEmail)}"
              />
              <button class="secondary-button" data-agent-action="map-owner" type="button">
                Map
              </button>
              <button class="danger-button" data-agent-action="disable" ${disabled} type="button">
                Disable
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function agentFilterQuery() {
  const form = document.querySelector("[data-agent-filters]");
  const params = new URLSearchParams({ limit: "50", offset: "0" });
  new FormData(form).forEach((value, key) => {
    const text = String(value).trim();
    if (text) params.set(key, text);
  });
  return params;
}

async function loadAgents() {
  const status = document.querySelector("[data-agents-status]");
  status.textContent = "Loading agents.";
  const { response, body } = await fetchJson(`/admin/api/agents?${agentFilterQuery()}`);
  if (!response.ok) {
    status.textContent = "Agent registry unavailable.";
    return;
  }
  document.querySelector("[data-agents-count]").textContent = String(body.total);
  status.textContent = body.total === 1 ? "1 matching agent." : `${body.total} matching agents.`;
  renderAgents(body.items);
}

function agentUidForAction(button) {
  return button.closest("tr")?.dataset.agentUid;
}

async function handleAgentAction(event) {
  const button = event.target.closest("[data-agent-action]");
  if (!button) return;
  const agentUid = agentUidForAction(button);
  if (!agentUid) return;
  button.disabled = true;

  const row = button.closest("tr");
  const action = button.dataset.agentAction;
  let result;
  if (action === "save-display-name") {
    const displayName = row.querySelector("[data-agent-display-name]").value.trim() || null;
    result = await patchJson(`/admin/api/agents/${encodeURIComponent(agentUid)}`, {
      display_name: displayName,
    });
  } else if (action === "map-owner") {
    const ownerEmail = row.querySelector("[data-agent-owner-email]").value.trim();
    result = await postJson(`/admin/api/agents/${encodeURIComponent(agentUid)}/map`, {
      owner_email: ownerEmail,
    });
  } else if (action === "disable") {
    result = await postJson(`/admin/api/agents/${encodeURIComponent(agentUid)}/disable`);
  }

  if (!result?.response.ok) {
    document.querySelector("[data-agents-status]").textContent = "Agent action failed.";
    button.disabled = false;
    return;
  }
  await loadAgents();
}

function bindAgents() {
  const form = document.querySelector("[data-agent-filters]");
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadAgents();
  });
  document.querySelector("[data-reset-agent-filters]")?.addEventListener("click", () => {
    form.reset();
    loadAgents();
  });
  document.querySelector("[data-agent-rows]")?.addEventListener("click", handleAgentAction);
}

async function refreshCurrentPage() {
  if (window.location.pathname === AGENTS_PATH) {
    await loadAgents();
    return;
  }
  await loadDashboard();
}

async function bindApp() {
  showView("app");
  const pageName = window.location.pathname === AGENTS_PATH ? "agents" : "dashboard";
  setActivePage(pageName);
  bindAgents();
  document.querySelector("[data-refresh-dashboard]")?.addEventListener("click", refreshCurrentPage);
  document.querySelector("[data-logout]")?.addEventListener("click", async () => {
    await postJson("/auth/logout");
    window.location.assign(LOGIN_PATH);
  });
  if (await loadAdminIdentity()) {
    await refreshCurrentPage();
  }
}

if (window.location.pathname === LOGIN_PATH) {
  bindLogin();
} else {
  bindApp();
}
