const token = localStorage.getItem("token");
const role = localStorage.getItem("role");
const email = localStorage.getItem("email");
if (!token) location.href = "/";

const H = { "Authorization": "Bearer " + token, "Content-Type": "application/json" };

function logout() {
  localStorage.clear();
  location.href = "/";
}

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: H, ...opts });
  if (res.status === 401) { logout(); return; }
  const data = res.status === 204 ? {} : await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || ("HTTP " + res.status));
  return data;
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// --- Navigation ---
const views = ["usage", "keys", "models", "users", "setup"];
function show(view) {
  views.forEach(v => document.getElementById("view-" + v).classList.toggle("hidden", v !== view));
  document.querySelectorAll(".nav a").forEach(a => a.classList.toggle("active", a.dataset.view === view));
  if (view === "usage") loadUsage();
  if (view === "keys") loadKeys();
  if (view === "models") loadModels();
  if (view === "users") loadUsers();
  if (view === "setup") renderSetup();
}

// --- Init ---
document.getElementById("whoami").textContent = email + (role === "admin" ? " (admin)" : "");
if (role === "admin") document.getElementById("nav-users").classList.remove("hidden");
loadUsage();

// --- Usage ---
function fmt(n) { return (n || 0).toLocaleString(); }
async function loadUsage() {
  const grid = document.getElementById("statGrid");
  const byModel = document.getElementById("byModel");
  const recent = document.getElementById("recentTable");
  try {
    const [s, r] = await Promise.all([api("/api/usage/summary"), api("/api/usage/recent")]);
    grid.innerHTML = [
      ["Total requests", fmt(s.requests)],
      ["Last 24h", fmt(s.requests_last_24h)],
      ["Input tokens", fmt(s.input_tokens)],
      ["Output tokens", fmt(s.output_tokens)],
    ].map(([l, v]) => `<div class="stat"><div class="label">${l}</div><div class="value">${v}</div></div>`).join("");

    byModel.innerHTML = s.by_model.length
      ? `<table><thead><tr><th>NIM model</th><th>Requests</th><th>Input</th><th>Output</th></tr></thead><tbody>` +
        s.by_model.map(m => `<tr><td class="mono">${esc(m.nim_model)}</td><td>${fmt(m.requests)}</td><td>${fmt(m.input_tokens)}</td><td>${fmt(m.output_tokens)}</td></tr>`).join("") + "</tbody></table>"
      : '<div class="empty">No requests yet. Point Claude Code at the gateway to see traffic here.</div>';

    recent.innerHTML = r.length
      ? `<table><thead><tr><th>Time</th>${role === "admin" ? "<th>User</th>" : ""}<th>Model</th><th>In</th><th>Out</th><th>Mode</th><th>Status</th></tr></thead><tbody>` +
        r.map(x => `<tr>
          <td>${new Date(x.created_at).toLocaleString()}</td>
          ${role === "admin" ? `<td>${esc(x.owner_email || "")}</td>` : ""}
          <td class="mono">${esc(x.nim_model || "")}</td>
          <td>${fmt(x.input_tokens)}</td>
          <td>${fmt(x.output_tokens)}</td>
          <td>${x.streamed ? "stream" : "sync"}</td>
          <td>${x.status === "ok" ? '<span class="badge user">ok</span>' : `<span class="badge revoked">${esc(x.status)}</span>`}</td>
        </tr>`).join("") + "</tbody></table>"
      : '<div class="empty">No requests yet.</div>';
  } catch (e) {
    grid.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
}

// --- Keys ---
async function createKey() {
  const label = document.getElementById("keyLabel").value.trim() || "default";
  try {
    const data = await api("/api/keys", { method: "POST", body: JSON.stringify({ label }) });
    const box = document.getElementById("newKey");
    box.classList.remove("hidden");
    box.innerHTML = `Copy this now — it won't be shown again:<br><br><strong>${esc(data.key)}</strong>`;
    loadKeys();
  } catch (e) { alert(e.message); }
}

async function revokeKey(id) {
  if (!confirm("Revoke this key? Claude Code using it will stop working.")) return;
  try { await api("/api/keys/" + id, { method: "DELETE" }); loadKeys(); }
  catch (e) { alert(e.message); }
}

async function loadKeys() {
  const el = document.getElementById("keysTable");
  try {
    const keys = await api("/api/keys");
    if (!keys.length) { el.innerHTML = '<div class="empty">No keys yet.</div>'; return; }
    const showOwner = role === "admin";
    el.innerHTML = `<table><thead><tr>
      <th>Label</th><th>Key</th>${showOwner ? "<th>Owner</th>" : ""}<th>Status</th><th></th>
      </tr></thead><tbody>` + keys.map(k => `<tr>
        <td>${esc(k.label)}</td>
        <td class="mono">${esc(k.masked)}</td>
        ${showOwner ? `<td>${esc(k.owner_email || "")}</td>` : ""}
        <td>${k.revoked ? '<span class="badge revoked">revoked</span>' : '<span class="badge user">active</span>'}</td>
        <td>${k.revoked ? "" : `<button class="btn danger sm" onclick="revokeKey('${k.id}')">Revoke</button>`}</td>
      </tr>`).join("") + "</tbody></table>";
  } catch (e) { el.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

// --- Models ---
const SLOTS = ["opus", "sonnet", "haiku", "default"];
async function loadModels() {
  const el = document.getElementById("mapRows");
  el.innerHTML = '<div class="empty">Loading NIM models…</div>';
  try {
    const [{ models }, mappings] = await Promise.all([
      api("/api/models/nim"),
      api("/api/models/mappings"),
    ]);
    const current = {};
    mappings.forEach(m => current[m.slot] = m.nim_model);
    el.innerHTML = SLOTS.map(slot => {
      const opts = ['<option value="">— not set —</option>'].concat(
        models.map(m => `<option value="${esc(m)}" ${current[slot] === m ? "selected" : ""}>${esc(m)}</option>`)
      ).join("");
      return `<div class="row" style="margin-bottom:12px">
        <div><label>${slot}</label><select id="slot-${slot}">${opts}</select></div>
        <button class="btn sm" onclick="saveMapping('${slot}', this)">Save</button>
      </div>`;
    }).join("");
  } catch (e) { el.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

async function saveMapping(slot, btn) {
  const val = document.getElementById("slot-" + slot).value;
  if (!val) return;
  try {
    await api("/api/models/mappings", { method: "PUT", body: JSON.stringify({ slot, nim_model: val }) });
    const orig = btn.textContent;
    btn.textContent = "Saved ✓"; setTimeout(() => btn.textContent = orig, 1200);
  } catch (e) { alert(e.message); }
}

// --- Users ---
async function loadUsers() {
  const el = document.getElementById("usersTable");
  try {
    const users = await api("/api/auth/users");
    el.innerHTML = `<table><thead><tr><th>Email</th><th>Role</th><th>Joined</th></tr></thead><tbody>` +
      users.map(u => `<tr>
        <td>${esc(u.email)}</td>
        <td><span class="badge ${u.role}">${u.role}</span></td>
        <td>${new Date(u.created_at).toLocaleString()}</td>
      </tr>`).join("") + "</tbody></table>";
  } catch (e) { el.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

// --- Setup ---
function renderSetup() {
  const base = location.origin;
  document.getElementById("setupCard").innerHTML = `
    <h3>1. Create a key</h3>
    <p class="hint">Go to <a onclick="show('keys')">API Keys</a> and generate one. Copy it.</p>
    <h3 style="margin-top:20px">2. Map at least the <span class="mono">sonnet</span> and <span class="mono">default</span> slots</h3>
    <p class="hint">On the <a onclick="show('models')">Models</a> page.</p>
    <h3 style="margin-top:20px">3. Point Claude Code here</h3>
    <p class="hint"><strong>macOS / Linux</strong> (add to ~/.zshrc or ~/.bashrc):</p>
    <pre>export ANTHROPIC_BASE_URL="${base}"
export ANTHROPIC_AUTH_TOKEN="sk-gw-...your key..."
export ANTHROPIC_DEFAULT_OPUS_MODEL="claude-opus"
export ANTHROPIC_DEFAULT_SONNET_MODEL="claude-sonnet"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="claude-haiku"</pre>
    <p class="hint"><strong>Windows (PowerShell)</strong>:</p>
    <pre>$env:ANTHROPIC_BASE_URL="${base}"
$env:ANTHROPIC_AUTH_TOKEN="sk-gw-...your key..."
# persist across sessions:
setx ANTHROPIC_BASE_URL "${base}"
setx ANTHROPIC_AUTH_TOKEN "sk-gw-...your key..."</pre>
    <h3 style="margin-top:20px">4. Verify</h3>
    <p class="hint">Run <span class="mono">claude</span>, then <span class="mono">/status</span> — it should show this gateway as the base URL. See the README for full details.</p>

    <h3 style="margin-top:24px">Full tool access — like real Claude Code</h3>
    <p class="hint">All of Claude Code's tools (bash, file read/write/edit, grep, glob, web fetch, MCP, sub-agents) run on your machine and work through this gateway unchanged — the gateway translates the model's tool calls to and from NVIDIA NIM. To make agentic tool use reliable, map your slots to NIM models with strong function-calling:</p>
    <ul class="hint" style="line-height:1.9">
      <li><span class="mono">meta/llama-3.3-70b-instruct</span> — best general tool use</li>
      <li><span class="mono">qwen/qwen3-next-80b-a3b-instruct</span> or a Qwen Coder — strong for coding</li>
      <li><span class="mono">nvidia/llama-3.1-nemotron-70b-instruct</span> — solid all-round</li>
      <li><span class="mono">meta/llama-3.1-8b-instruct</span> — fastest; good for the <span class="mono">haiku</span> (background) slot</li>
    </ul>
    <p class="hint">Tip: map <span class="mono">haiku</span> to a fast small model — Claude Code uses it for background tasks (titles, summaries) — and <span class="mono">sonnet</span>/<span class="mono">opus</span> to a larger model for the main work. To enable gateway model discovery in the picker, also set <span class="mono">CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1</span>.</p>
  `;
}
