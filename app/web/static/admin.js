const LOGIN_PATH = "/admin/login";
const DASHBOARD_PATH = "/admin/dashboard";
const AGENTS_PATH = "/admin/agents";
const AGENT_TOKENS_PATH = "/admin/agent-tokens";
const MESSAGES_PATH = "/admin/messages";
const MESSAGE_API_PATH = "/admin/api/messages";

const PAGE_TITLES = {
  [DASHBOARD_PATH]: "Dashboard",
  [AGENTS_PATH]: "Agent Registry",
  [AGENT_TOKENS_PATH]: "Agent Token",
  [MESSAGES_PATH]: "Message Explorer",
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

function setTokenError(message) {
  const error = document.querySelector("[data-token-error]");
  if (!error) return;
  error.textContent = message;
  error.hidden = message === "";
}

function setTokenStatus(message) {
  const status = document.querySelector("[data-token-status]");
  if (!status) return;
  status.textContent = message;
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

function roleBadgeClass(role) {
  return `role-badge role-${String(role).toLowerCase()}`;
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function padDatePart(number) {
  return String(number).padStart(2, "0");
}

function formatDateInput(value) {
  return [
    value.getFullYear(),
    padDatePart(value.getMonth() + 1),
    padDatePart(value.getDate()),
  ].join("-");
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function formatJsonValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string") {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  return JSON.stringify(value, null, 2);
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

function renderIssuedToken(token) {
  const result = document.querySelector("[data-token-result]");
  if (!result) return;
  result.hidden = false;
  document.querySelector("[data-token-owner]").textContent = token.owner_email;
  document.querySelector("[data-token-agent-uid]").textContent = token.agent_uid;
  document.querySelector("[data-issued-token]").textContent = token.token;
  document.querySelector("[data-token-type]").textContent = token.token_type;
  document.querySelector("[data-token-expires]").textContent = displayValue(
    token.expires_at ? formatDateTime(token.expires_at) : null
  );
  setTokenStatus("Agent token issued.");
}

function agentTokenStatus(token) {
  if (!token.is_active) return "INACTIVE";
  if (token.expires_at && new Date(token.expires_at) <= new Date()) return "EXPIRED";
  return "ACTIVE";
}

function renderAgentTokens(items) {
  const rows = document.querySelector("[data-token-rows]");
  if (!rows) return;
  if (items.length === 0) {
    rows.innerHTML = '<tr><td colspan="5">No agent tokens have been issued.</td></tr>';
    return;
  }

  rows.innerHTML = items
    .map((token) => {
      const status = agentTokenStatus(token);
      return `
        <tr>
          <td data-label="Agent">
            <div class="cell-stack">
              <strong>${escapeHtml(token.agent_uid || "-")}</strong>
              <span>${escapeHtml(token.owner_email || "-")}</span>
            </div>
          </td>
          <td data-label="Scope">
            <div class="cell-stack">
              <strong>${escapeHtml(token.scope)}</strong>
              <span>${escapeHtml(token.token_type)}</span>
            </div>
          </td>
          <td data-label="Status">
            <span class="${agentStatusClass(status)}">${escapeHtml(status)}</span>
          </td>
          <td data-label="Expires">${escapeHtml(formatDateTime(token.expires_at))}</td>
          <td data-label="Created">${escapeHtml(formatDateTime(token.created_at))}</td>
        </tr>
      `;
    })
    .join("");
}

async function loadAgentTokens() {
  const status = document.querySelector("[data-token-list-status]");
  if (status) status.textContent = "Loading issued tokens.";
  const { response, body } = await fetchJson("/admin/api/agent-tokens?limit=50&offset=0");
  if (response.status === 401) {
    window.location.assign(LOGIN_PATH);
    return;
  }
  if (!response.ok) {
    if (status) status.textContent = "Issued token list unavailable.";
    return;
  }

  document.querySelector("[data-token-count]").textContent = String(body.total);
  if (status) {
    status.textContent =
      body.total === 1 ? "1 issued token." : `${body.total} issued tokens.`;
  }
  renderAgentTokens(body.items || []);
}

async function issueAgentToken(form) {
  const formData = new FormData(form);
  const ownerEmail = String(formData.get("owner_email") || "").trim();
  const expiresAt = String(formData.get("expires_at") || "").trim();
  const payload = { owner_email: ownerEmail };
  if (expiresAt) payload.expires_at = expiresAt;

  const { response, body } = await postJson("/admin/api/agent-tokens", payload);
  if (response.status === 401) {
    window.location.assign(LOGIN_PATH);
    return;
  }
  if (!response.ok) {
    setTokenError("Agent token issue failed.");
    setTokenStatus("Token was not issued.");
    return;
  }

  setTokenError("");
  renderIssuedToken(body);
  await loadAgentTokens();
}

async function copyIssuedToken() {
  const token = document.querySelector("[data-issued-token]")?.textContent || "";
  if (!token) return;
  try {
    await navigator.clipboard.writeText(token);
    setTokenStatus("Agent token copied.");
  } catch {
    setTokenStatus("Copy unavailable. Select the token value.");
  }
}

function bindAgentTokens() {
  const form = document.querySelector("[data-agent-token-form]");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setTokenError("");
    setTokenStatus("Issuing agent token.");
    const submitButton = form.querySelector("button[type='submit']");
    submitButton.disabled = true;
    await issueAgentToken(form);
    submitButton.disabled = false;
  });
  document.querySelector("[data-reset-agent-token-form]")?.addEventListener("click", () => {
    form?.reset();
    document.querySelector("[data-token-result]").hidden = true;
    setTokenError("");
    setTokenStatus("Waiting for agent token issue.");
  });
  document.querySelector("[data-copy-issued-token]")?.addEventListener("click", copyIssuedToken);
}

function messageFilterQuery() {
  const form = document.querySelector("[data-message-filters]");
  const params = new URLSearchParams({ limit: "50", offset: "0" });
  syncMessageDateRanges();
  new FormData(form).forEach((value, key) => {
    const text = String(value).trim();
    if (text) params.set(key, text);
  });
  return params;
}

function populateTimeSelect(select, maxValue) {
  if (!select || select.options.length > 0) return;
  for (let value = 0; value <= maxValue; value += 1) {
    const option = document.createElement("option");
    option.value = padDatePart(value);
    option.textContent = padDatePart(value);
    select.append(option);
  }
}

function initializeMessageDateRangeControls() {
  const form = document.querySelector("[data-message-filters]");
  if (!form) return;

  ["date_from", "date_to"].forEach((name) => {
    populateTimeSelect(form.querySelector(`[data-time-hour="${name}"]`), 23);
    populateTimeSelect(form.querySelector(`[data-time-minute="${name}"]`), 59);
    populateTimeSelect(form.querySelector(`[data-time-second="${name}"]`), 59);
  });

  form
    .querySelectorAll("[data-date-part], [data-time-hour], [data-time-minute], [data-time-second]")
    .forEach((control) => {
      control.addEventListener("change", () => {
        syncMessageDateRange(
          control.dataset.datePart ||
            control.dataset.timeHour ||
            control.dataset.timeMinute ||
            control.dataset.timeSecond
        );
      });
    });
}

function setMessageDateRangeValue(name, value) {
  const form = document.querySelector("[data-message-filters]");
  if (!form) return;
  const dateInput = form.querySelector(`[data-date-part="${name}"]`);
  const hourSelect = form.querySelector(`[data-time-hour="${name}"]`);
  const minuteSelect = form.querySelector(`[data-time-minute="${name}"]`);
  const secondSelect = form.querySelector(`[data-time-second="${name}"]`);

  dateInput.value = formatDateInput(value);
  hourSelect.value = padDatePart(value.getHours());
  minuteSelect.value = padDatePart(value.getMinutes());
  secondSelect.value = padDatePart(value.getSeconds());
  syncMessageDateRange(name);
}

function syncMessageDateRange(name) {
  const form = document.querySelector("[data-message-filters]");
  if (!form) return;
  const dateInput = form.querySelector(`[data-date-part="${name}"]`);
  const hiddenInput = form.querySelector(`[data-date-range-value="${name}"]`);
  const hourValue = form.querySelector(`[data-time-hour="${name}"]`)?.value;
  const minuteValue = form.querySelector(`[data-time-minute="${name}"]`)?.value;
  const secondValue = form.querySelector(`[data-time-second="${name}"]`)?.value;

  hiddenInput.value =
    dateInput.value && hourValue && minuteValue && secondValue
      ? `${dateInput.value}T${hourValue}:${minuteValue}:${secondValue}`
      : "";
}

function syncMessageDateRanges() {
  syncMessageDateRange("date_from");
  syncMessageDateRange("date_to");
}

function setDefaultMessageDateRange() {
  const form = document.querySelector("[data-message-filters]");
  if (!form) return;
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0);
  setMessageDateRangeValue("date_from", todayStart);
  setMessageDateRangeValue("date_to", now);
}

function renderMessages(items) {
  const rows = document.querySelector("[data-message-rows]");
  if (!rows) return;
  if (items.length === 0) {
    rows.innerHTML = '<tr><td colspan="7">No messages match the current filters.</td></tr>';
    return;
  }

  rows.innerHTML = items
    .map(
      (message) => `
        <tr
          aria-label="Open message ${escapeHtml(message.id)} detail"
          class="message-row"
          data-message-id="${escapeHtml(message.id)}"
          tabindex="0"
        >
          <td data-label="Occurred">${escapeHtml(formatDateTime(message.occurred_at))}</td>
          <td data-label="Agent">
            <div class="cell-stack">
              <strong>${escapeHtml(message.profile_name)}</strong>
              <span>${escapeHtml(message.agent_uid)}</span>
            </div>
          </td>
          <td data-label="Owner">${escapeHtml(message.owner_email || "-")}</td>
          <td data-label="Source">
            <span class="source-chip">${escapeHtml(message.source)}</span>
          </td>
          <td data-label="Role">
            <span class="${roleBadgeClass(message.role)}">${escapeHtml(message.role)}</span>
          </td>
          <td data-label="Event">
            <div class="cell-stack">
              <span class="event-chip">${escapeHtml(message.event_type)}</span>
              <span>${escapeHtml(message.message_type)}</span>
            </div>
          </td>
          <td data-label="Preview">
            <span class="message-preview">${escapeHtml(message.content_preview)}</span>
          </td>
        </tr>
      `
    )
    .join("");
}

async function loadMessages() {
  const status = document.querySelector("[data-messages-status]");
  status.textContent = "Loading messages.";
  const { response, body } = await fetchJson(`/admin/api/messages?${messageFilterQuery()}`);
  if (!response.ok) {
    status.textContent = "Message explorer unavailable.";
    return;
  }
  document.querySelector("[data-messages-count]").textContent = String(body.total);
  status.textContent = body.total === 1 ? "1 matching message." : `${body.total} matching messages.`;
  renderMessages(body.items);
}

function setMessageDrawerOpen(isOpen) {
  const drawer = document.querySelector("[data-message-drawer]");
  if (!drawer) return;
  drawer.hidden = !isOpen;
  document.body.classList.toggle("detail-drawer-open", isOpen);
}

function closeMessageDetail() {
  setMessageDrawerOpen(false);
}

function setMessageDetailStatus(message) {
  const status = document.querySelector("[data-message-detail-status]");
  if (status) status.textContent = message;
}

function setMessageDetailField(name, value) {
  const target = document.querySelector(`[data-message-detail-field="${name}"]`);
  if (!target) return;
  target.textContent = displayValue(value);
}

function setMessageDetailPre(name, value) {
  const target = document.querySelector(`[data-message-detail-field="${name}"]`);
  if (!target) return;
  target.textContent = value;
}

function resetMessageDetail(messageId) {
  document.querySelector("[data-message-detail-title]").textContent = `Message #${messageId}`;
  [
    "agent_uid",
    "session_key",
    "request_id",
    "parent_message_id",
    "role",
    "direction",
    "message_type",
  ].forEach((name) => setMessageDetailField(name, "-"));
  ["content", "assistant_response", "tool_calls_json", "raw_payload"].forEach((name) =>
    setMessageDetailPre(name, "")
  );
  const relatedList = document.querySelector("[data-message-related-list]");
  if (relatedList) relatedList.innerHTML = "<p>No related messages.</p>";
}

function renderRelatedMessages(relatedMessages) {
  const relatedList = document.querySelector("[data-message-related-list]");
  if (!relatedList) return;
  if (relatedMessages.length === 0) {
    relatedList.innerHTML = "<p>No related messages.</p>";
    return;
  }

  relatedList.innerHTML = relatedMessages
    .map(
      (message) => `
        <button
          class="related-message-item"
          data-related-message-id="${escapeHtml(message.id)}"
          type="button"
        >
          <span class="related-message-meta">
            <strong>#${escapeHtml(message.id)}</strong>
            <span>${escapeHtml(formatDateTime(message.occurred_at))}</span>
          </span>
          <span class="related-message-tags">
            <span class="${roleBadgeClass(message.role)}">${escapeHtml(message.role)}</span>
            <span class="event-chip">${escapeHtml(message.event_type)}</span>
            <span class="source-chip">${escapeHtml(message.message_type)}</span>
          </span>
          <span class="message-preview">${escapeHtml(message.content_preview)}</span>
        </button>
      `
    )
    .join("");
}

function renderMessageDetail(detail) {
  document.querySelector("[data-message-detail-title]").textContent = `Message #${detail.id}`;
  setMessageDetailStatus("Message detail loaded.");
  setMessageDetailField("agent_uid", detail.agent_uid);
  setMessageDetailField("session_key", detail.session_key);
  setMessageDetailField("request_id", detail.request_id);
  setMessageDetailField("parent_message_id", detail.parent_message_id);
  setMessageDetailField("role", detail.role);
  setMessageDetailField("direction", detail.direction);
  setMessageDetailField("message_type", detail.message_type);
  setMessageDetailPre("content", detail.content);
  setMessageDetailPre("assistant_response", displayValue(detail.assistant_response));
  setMessageDetailPre("tool_calls_json", formatJsonValue(detail.tool_calls_json));
  setMessageDetailPre("raw_payload", formatJsonValue(detail.raw_payload));
  renderRelatedMessages(detail.related_messages || []);
}

async function openMessageDetail(messageId) {
  if (!messageId) return;
  setMessageDrawerOpen(true);
  resetMessageDetail(messageId);
  setMessageDetailStatus("Loading message detail.");

  const { response, body } = await fetchJson(
    `${MESSAGE_API_PATH}/${encodeURIComponent(messageId)}`
  );
  if (response.status === 401) {
    window.location.assign(LOGIN_PATH);
    return;
  }
  if (!response.ok) {
    setMessageDetailStatus(
      response.status === 404 ? "Message detail was not found." : "Message detail unavailable."
    );
    return;
  }
  renderMessageDetail(body);
}

function handleMessageRowClick(event) {
  const row = event.target.closest("[data-message-id]");
  if (!row) return;
  openMessageDetail(row.dataset.messageId);
}

function handleMessageRowKeydown(event) {
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest("[data-message-id]");
  if (!row) return;
  event.preventDefault();
  openMessageDetail(row.dataset.messageId);
}

function handleRelatedMessageClick(event) {
  const button = event.target.closest("[data-related-message-id]");
  if (!button) return;
  openMessageDetail(button.dataset.relatedMessageId);
}

function bindMessages() {
  const form = document.querySelector("[data-message-filters]");
  initializeMessageDateRangeControls();
  setDefaultMessageDateRange();
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadMessages();
  });
  document.querySelector("[data-reset-message-filters]")?.addEventListener("click", () => {
    form.reset();
    setDefaultMessageDateRange();
    loadMessages();
  });
  document.querySelector("[data-message-rows]")?.addEventListener("click", handleMessageRowClick);
  document
    .querySelector("[data-message-rows]")
    ?.addEventListener("keydown", handleMessageRowKeydown);
  document
    .querySelector("[data-message-related-list]")
    ?.addEventListener("click", handleRelatedMessageClick);
  document.querySelectorAll("[data-close-message-detail]").forEach((target) => {
    target.addEventListener("click", closeMessageDetail);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMessageDetail();
  });
}

async function refreshCurrentPage() {
  if (window.location.pathname === AGENTS_PATH) {
    await loadAgents();
    return;
  }
  if (window.location.pathname === AGENT_TOKENS_PATH) {
    setTokenStatus("Waiting for agent token issue.");
    await loadAgentTokens();
    return;
  }
  if (window.location.pathname === MESSAGES_PATH) {
    await loadMessages();
    return;
  }
  await loadDashboard();
}

async function bindApp() {
  showView("app");
  const pageName =
    window.location.pathname === AGENTS_PATH
      ? "agents"
      : window.location.pathname === AGENT_TOKENS_PATH
        ? "agent-tokens"
        : window.location.pathname === MESSAGES_PATH
        ? "messages"
        : "dashboard";
  setActivePage(pageName);
  bindAgents();
  bindAgentTokens();
  bindMessages();
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
