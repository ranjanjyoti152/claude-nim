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

let _toastTimer;
function toast(msg, isErr = false) {
  let t = document.getElementById("toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.className = isErr ? "err show" : "show";
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
    if (btn) { const o = btn.textContent; btn.textContent = "Copied ✓"; setTimeout(() => btn.textContent = o, 1200); }
  } catch { toast("Copy failed — select and copy manually", true); }
}

// --- Navigation ---
const views = ["usage", "keys", "models", "users", "settings", "setup"];
function show(view) {
  views.forEach(v => document.getElementById("view-" + v).classList.toggle("hidden", v !== view));
  document.querySelectorAll(".nav a").forEach(a => a.classList.toggle("active", a.dataset.view === view));
  if (view === "usage") loadUsage();
  if (view === "keys") loadKeys();
  if (view === "models") loadModels();
  if (view === "users") loadUsers();
  if (view === "settings") loadSettings();
  if (view === "setup") renderSetup();
}

// --- Init ---
document.getElementById("whoami").textContent = email + (role === "admin" ? " (admin)" : "");
if (role === "admin") {
  document.getElementById("nav-users").classList.remove("hidden");
  document.getElementById("nav-settings").classList.remove("hidden");
}
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
      ? `<div class="table-wrap"><table><thead><tr><th>NIM model</th><th>Requests</th><th>Input</th><th>Output</th></tr></thead><tbody>` +
        s.by_model.map(m => `<tr><td class="mono">${esc(m.nim_model)}</td><td>${fmt(m.requests)}</td><td>${fmt(m.input_tokens)}</td><td>${fmt(m.output_tokens)}</td></tr>`).join("") + "</tbody></table></div>"
      : '<div class="empty">No requests yet. Point Claude Code at the gateway to see traffic here.</div>';

    recent.innerHTML = r.length
      ? `<div class="table-wrap"><table><thead><tr><th>Time</th>${role === "admin" ? "<th>User</th>" : ""}<th>Model</th><th>In</th><th>Out</th><th>Mode</th><th>Status</th></tr></thead><tbody>` +
        r.map(x => `<tr>
          <td>${new Date(x.created_at).toLocaleString()}</td>
          ${role === "admin" ? `<td>${esc(x.owner_email || "")}</td>` : ""}
          <td class="mono">${esc(x.nim_model || "")}</td>
          <td>${fmt(x.input_tokens)}</td>
          <td>${fmt(x.output_tokens)}</td>
          <td>${x.streamed ? "stream" : "sync"}</td>
          <td>${x.status === "ok" ? '<span class="badge user">ok</span>' : `<span class="badge revoked">${esc(x.status)}</span>`}</td>
        </tr>`).join("") + "</tbody></table></div>"
      : '<div class="empty">No requests yet.</div>';
  } catch (e) {
    grid.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
}

// --- Keys ---
async function createKey() {
  const label = document.getElementById("keyLabel").value.trim() || "default";
  const rpm = parseInt(document.getElementById("keyRpm").value, 10) || 0;
  const cap = parseInt(document.getElementById("keyCap").value, 10) || 0;
  try {
    const data = await api("/api/keys", {
      method: "POST",
      body: JSON.stringify({ label, rpm_limit: rpm, token_cap: cap }),
    });
    const box = document.getElementById("newKey");
    box.classList.remove("hidden");
    box.innerHTML = `<strong>Copy this now</strong> — it won't be shown again.
      <div class="key-value"><span>${esc(data.key)}</span>
      <button class="btn sm" onclick="copyText('${esc(data.key)}', this)">Copy</button></div>`;
    toast("API key created");
    loadKeys();
  } catch (e) { toast(e.message, true); }
}

async function revokeKey(id) {
  if (!confirm("Revoke this key? Claude Code using it will stop working.")) return;
  try { await api("/api/keys/" + id, { method: "DELETE" }); toast("Key revoked"); loadKeys(); }
  catch (e) { toast(e.message, true); }
}

async function editLimits(id, rpm, cap) {
  const nrpm = prompt("Requests per minute (0 = unlimited):", rpm);
  if (nrpm === null) return;
  const ncap = prompt("Total token cap (0 = unlimited):", cap);
  if (ncap === null) return;
  try {
    await api("/api/keys/" + id + "/limits", {
      method: "PUT",
      body: JSON.stringify({ rpm_limit: parseInt(nrpm, 10) || 0, token_cap: parseInt(ncap, 10) || 0 }),
    });
    loadKeys();
  } catch (e) { alert(e.message); }
}

function capCell(k) {
  const rpm = k.rpm_limit ? k.rpm_limit + "/min" : "∞";
  const cap = k.token_cap ? `${fmt(k.tokens_used)}/${fmt(k.token_cap)}` : `${fmt(k.tokens_used)} / ∞`;
  return `${rpm} · ${cap} tok`;
}

async function loadKeys() {
  const el = document.getElementById("keysTable");
  try {
    const keys = await api("/api/keys");
    if (!keys.length) { el.innerHTML = '<div class="empty">No keys yet.</div>'; return; }
    const showOwner = role === "admin";
    el.innerHTML = `<div class="table-wrap"><table><thead><tr>
      <th>Label</th><th>Key</th>${showOwner ? "<th>Owner</th>" : ""}<th>Limits · Usage</th><th>Status</th><th></th>
      </tr></thead><tbody>` + keys.map(k => `<tr>
        <td>${esc(k.label)}</td>
        <td class="mono">${esc(k.masked)}</td>
        ${showOwner ? `<td>${esc(k.owner_email || "")}</td>` : ""}
        <td class="mono" style="font-size:12px">${capCell(k)}</td>
        <td>${k.revoked ? '<span class="badge revoked">revoked</span>' : '<span class="badge user">active</span>'}</td>
        <td>${k.revoked ? "" : `
          <button class="btn ghost sm" onclick="editLimits('${k.id}', ${k.rpm_limit}, ${k.token_cap})">Limits</button>
          <button class="btn danger sm" onclick="revokeKey('${k.id}')">Revoke</button>`}</td>
      </tr>`).join("") + "</tbody></table></div>";
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
        <button class="btn ghost sm" onclick="testModel('${slot}', this)">Test</button>
        <span id="test-${slot}" class="hint" style="min-width:120px"></span>
      </div>`;
    }).join("");
  } catch (e) { el.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

async function testModel(slot, btn) {
  const model = document.getElementById("slot-" + slot).value;
  const out = document.getElementById("test-" + slot);
  if (!model) { out.innerHTML = '<span style="color:var(--muted)">pick a model first</span>'; return; }
  const orig = btn.textContent;
  btn.textContent = "Testing…"; btn.disabled = true;
  out.textContent = "";
  try {
    const r = await api("/api/models/test", { method: "POST", body: JSON.stringify({ model }) });
    out.innerHTML = r.ok
      ? `<span style="color:var(--ok)">✓ runnable${r.latency_ms ? " (" + r.latency_ms + "ms)" : ""}</span>`
      : `<span style="color:var(--danger)">✗ ${r.status || "err"}: ${esc((r.detail || "").slice(0, 60))}</span>`;
  } catch (e) {
    out.innerHTML = `<span style="color:var(--danger)">✗ ${esc(e.message)}</span>`;
  } finally {
    btn.textContent = orig; btn.disabled = false;
  }
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
    el.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Email</th><th>Role</th><th>Joined</th><th>Actions</th></tr></thead><tbody>` +
      users.map(u => {
        const isSelf = u.email === email;
        const toRole = u.role === "admin" ? "user" : "admin";
        return `<tr>
          <td>${esc(u.email)}${isSelf ? ' <span class="hint">(you)</span>' : ""}</td>
          <td><span class="badge ${u.role}">${u.role}</span></td>
          <td>${new Date(u.created_at).toLocaleString()}</td>
          <td>
            <button class="btn ghost sm" onclick="setUserRole('${u.id}','${toRole}')">Make ${toRole}</button>
            ${isSelf ? "" : `<button class="btn danger sm" onclick="deleteUser('${u.id}','${esc(u.email)}')">Delete</button>`}
          </td>
        </tr>`;
      }).join("") + "</tbody></table></div>";
  } catch (e) { el.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

async function setUserRole(id, role) {
  try {
    await api("/api/auth/users/" + id + "/role", { method: "PUT", body: JSON.stringify({ role }) });
    loadUsers();
  } catch (e) { alert(e.message); }
}

async function deleteUser(id, em) {
  if (!confirm(`Delete ${em}? Their gateway keys will be revoked. This cannot be undone.`)) return;
  try { await api("/api/auth/users/" + id, { method: "DELETE" }); loadUsers(); }
  catch (e) { alert(e.message); }
}

// --- Settings (admin) ---
function applyProviderPreset() {
  const sel = document.getElementById("setProvider");
  if (sel.value) {
    document.getElementById("setBaseUrl").value = sel.value;
    document.getElementById("setApiKey").focus();
  }
  sel.value = ""; // reset so it stays a picker, not a bound field
}

async function loadSettings() {
  try {
    const s = await api("/api/settings");
    document.getElementById("setBaseUrl").value = s.nim_base_url || "";
    document.getElementById("setApiKey").value = "";
    document.getElementById("setApiKey").placeholder = s.nvidia_api_key_set
      ? `current: ${s.nvidia_api_key} (leave blank to keep)` : "sk-… / nvapi-…";
    document.getElementById("keyState").textContent = s.nvidia_api_key_set
      ? "A provider API key is configured." : "No API key set — provider calls will fail until you add one (not needed for keyless local servers).";
    document.getElementById("setBackends").value = s.nim_backends || "";
    document.getElementById("setCacheEnabled").value = String(!!s.cache_enabled);
    document.getElementById("setCacheTtl").value = s.cache_ttl_seconds ?? 300;
  } catch (e) {
    document.getElementById("settingsMsg").innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`;
  }
}

async function saveSettings(btn) {
  const body = {
    nim_base_url: document.getElementById("setBaseUrl").value.trim(),
    nim_backends: document.getElementById("setBackends").value.trim(),
    cache_enabled: document.getElementById("setCacheEnabled").value === "true",
    cache_ttl_seconds: parseInt(document.getElementById("setCacheTtl").value, 10) || 0,
  };
  const key = document.getElementById("setApiKey").value.trim();
  if (key) body.nvidia_api_key = key;
  const orig = btn.textContent; btn.textContent = "Saving…"; btn.disabled = true;
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
    document.getElementById("settingsMsg").innerHTML = '<span style="color:var(--ok)">Saved ✓</span>';
    loadSettings();
  } catch (e) {
    document.getElementById("settingsMsg").innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`;
  } finally { btn.textContent = orig; btn.disabled = false; }
}

async function testConnection(btn) {
  const orig = btn.textContent; btn.textContent = "Testing…"; btn.disabled = true;
  const msg = document.getElementById("settingsMsg"); msg.textContent = "";
  try {
    const r = await api("/api/settings/test-connection", { method: "POST" });
    msg.innerHTML = r.ok
      ? `<span style="color:var(--ok)">✓ Connected — ${r.model_count} models available</span>`
      : `<span style="color:var(--danger)">✗ ${r.status || "err"}: ${esc((r.detail || "").slice(0, 80))}</span>`;
  } catch (e) {
    msg.innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`;
  } finally { btn.textContent = orig; btn.disabled = false; }
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

    <h3 style="margin-top:24px">Use with any OpenAI-compatible client</h3>
    <p class="hint">The gateway also speaks the OpenAI API. Point the OpenAI SDK, Cline, Continue, LangChain, LiteLLM, etc. at:</p>
    <pre>Base URL:  ${base}/openai/v1
API key:   sk-gw-...your key...
Model:     meta/llama-3.3-70b-instruct   (raw NIM id, or a slot alias like "claude-sonnet")</pre>
    <p class="hint"><strong>OpenAI Python SDK</strong>:</p>
    <pre>from openai import OpenAI
client = OpenAI(base_url="${base}/openai/v1", api_key="sk-gw-...")
r = client.chat.completions.create(
    model="meta/llama-3.3-70b-instruct",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(r.choices[0].message.content)</pre>
    <p class="hint">Same gateway keys, model mappings, caching, rate limits, and usage tracking apply to both APIs. Endpoints: <span class="mono">POST /openai/v1/chat/completions</span>, <span class="mono">GET /openai/v1/models</span>.</p>
  `;
}
