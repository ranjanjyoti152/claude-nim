<div align="center">

# 🌉 claude-nim

### Use **Claude Code** with any **NVIDIA NIM** model.

**A drop-in gateway that translates the Anthropic Messages API ↔ NVIDIA NIM (OpenAI-compatible), so Claude Code can run on Llama, Qwen, Nemotron, DeepSeek & 100+ NIM models — with a beautiful claude.ai-styled dashboard for keys, models & usage.**

[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA-NIM-76B900?logo=nvidia&logoColor=white)](https://build.nvidia.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-D97757.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

---

## 💡 Why claude-nim?

**Claude Code is the best agentic coding CLI.** But it only speaks the **Anthropic Messages API**. **NVIDIA NIM** — the hosted catalog at [build.nvidia.com](https://build.nvidia.com) and self-hosted GPU containers — speaks the **OpenAI Chat Completions API**. The two don't talk to each other.

`claude-nim` is the bridge. Point Claude Code at it, and every request is transparently translated to NIM and back — **streaming, tool calls, system prompts, images, the works**. You get the full Claude Code experience (bash, file edits, grep, sub-agents, MCP) running on open models like **Llama 3.3 70B**, **Qwen**, and **Nemotron** — hosted for free on NVIDIA's cloud, or on your own GPUs.

> **It feels exactly like using Claude Code against the real Anthropic API — because to Claude Code, it *is* the Anthropic API.**

---

## ✨ Features

| | |
|---|---|
| 🔄 **Full API translation** | Anthropic Messages ⇄ OpenAI Chat Completions — streaming SSE, tool use, tool results, system prompts, vision, stop reasons, token usage |
| 🔌 **OpenAI-compatible too** | Also exposes `/openai/v1/chat/completions` + `/models` — use the OpenAI SDK, Cline, Continue, LangChain, LiteLLM & more |
| 🧰 **All Claude Code tools work** | bash, read/write/edit, grep, glob, web fetch, MCP, sub-agents — they run client-side and just work through the gateway |
| 🎛️ **Model slot mapping** | Map Claude Code's `opus` / `sonnet` / `haiku` slots to any NIM model from a dropdown |
| 🔑 **API key management** | Generate & revoke gateway keys from the UI — hashed at rest, shown once |
| 📊 **Usage dashboard** | Live request counts, token totals, per-model breakdown, recent request log |
| 👥 **Multi-user + roles** | Email/password auth, JWT sessions — **first signup becomes admin** |
| 🎨 **claude.ai-styled UI** | Warm, minimal dashboard that feels like home |
| 🐳 **One-command Docker** | `docker compose up` — FastAPI + MongoDB, fully self-hosted |
| 🖥️ **Hosted or self-hosted NIM** | Works with `integrate.api.nvidia.com` **or** a local NIM container |

---

## 🏗️ Architecture

```
   ┌──────────────┐   Anthropic Messages API    ┌───────────────────────┐   OpenAI Chat Completions   ┌──────────────┐
   │  Claude Code │ ──────  (SSE stream)  ─────▶ │   claude-nim gateway   │ ─────────────────────────▶ │  NVIDIA NIM  │
   │     CLI      │ ◀─── translated events ───── │      (FastAPI)         │ ◀───── SSE / JSON ───────── │ Llama · Qwen │
   └──────────────┘                              └───────────┬───────────┘                             │  · Nemotron  │
      ANTHROPIC_BASE_URL ─────────────────────────────────── │                                         └──────────────┘
      ANTHROPIC_AUTH_TOKEN                          ┌─────────┴─────────┐
                                                    │      MongoDB       │  users · api_keys
                                                    │                    │  model_mappings · usage
                                                    └────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/ranjanjyoti152/claude-nim.git
cd claude-nim
cp .env.example .env
```

Edit `.env` and set your NVIDIA key (get one free at [build.nvidia.com](https://build.nvidia.com)):

```ini
NVIDIA_API_KEY=nvapi-your-key-here
JWT_SECRET=$(openssl rand -hex 32)   # paste the output
```

### 2. Run

```bash
docker compose up --build
```

### 3. Set up in the dashboard

Open **http://localhost:8787** and:

1. **Sign up** — the first account becomes the **admin**.
2. **Models** → map at least `sonnet` and `default` to a working NIM model (e.g. `meta/llama-3.3-70b-instruct`).
3. **API Keys** → create a key and copy it (shown once).

### 4. Point Claude Code at the gateway

```bash
export ANTHROPIC_BASE_URL="http://localhost:8787"
export ANTHROPIC_AUTH_TOKEN="sk-gw-...your key..."
export ANTHROPIC_DEFAULT_OPUS_MODEL="claude-opus"
export ANTHROPIC_DEFAULT_SONNET_MODEL="claude-sonnet"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="claude-haiku"
```

Run `claude`, then `/status` to confirm it's pointed at your gateway. **That's it — you're coding on NIM models through Claude Code.** 🎉

---

## 🎛️ Recommended model mappings

Not every model in NIM's catalog is runnable on every account, and tool-calling quality varies. Battle-tested picks:

| Slot | Model | Why |
|---|---|---|
| `opus` / `sonnet` | `meta/llama-3.3-70b-instruct` | Best general tool use & coding |
| `sonnet` | `qwen/qwen3-next-80b-a3b-instruct` | Excellent for coding |
| `opus` | `nvidia/llama-3.1-nemotron-70b-instruct` | Strong all-rounder |
| `haiku` | `meta/llama-3.1-8b-instruct` | Fast — ideal for Claude Code's background tasks |

> 💡 **Tip:** Claude Code uses the `haiku` slot for lightweight background work (titles, summaries). Map it to a small fast model so the UI stays snappy, and reserve a 70B+ model for `sonnet`/`opus`.

---

## 🖥️ Using a self-hosted NIM container

Point the gateway at a NIM running on your own GPU by editing `.env`:

```ini
NIM_BASE_URL=http://host.docker.internal:8000/v1
NVIDIA_API_KEY=          # not needed for local NIM — leave blank
```

Everything else stays the same. No NVIDIA-side rate limits, throughput bounded only by your hardware.

---

## ⚙️ Configuration

All config lives in `.env`:

| Variable | Description | Default |
|---|---|---|
| `NVIDIA_API_KEY` | NIM hosted API key (`nvapi-…`). Blank for local NIM. | — |
| `NIM_BASE_URL` | NIM endpoint | `https://integrate.api.nvidia.com/v1` |
| `JWT_SECRET` | Secret for dashboard session tokens — **set this** | — |
| `JWT_EXPIRE_MINUTES` | Dashboard session lifetime | `1440` |
| `MONGO_URL` | Mongo connection string | `mongodb://mongo:27017` |
| `MONGO_DB` | Database name | `anthropic_gateway` |
| `MONGO_HOST_PORT` | Host port Mongo is exposed on | `37017` |
| `GATEWAY_PORT` | Port the gateway listens on | `8787` |

### Platform config for Claude Code

<details>
<summary><b>macOS / Linux (bash · zsh)</b></summary>

```bash
# ~/.zshrc or ~/.bashrc
export ANTHROPIC_BASE_URL="http://localhost:8787"
export ANTHROPIC_AUTH_TOKEN="sk-gw-...your key..."
export ANTHROPIC_DEFAULT_SONNET_MODEL="claude-sonnet"
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
$env:ANTHROPIC_BASE_URL="http://localhost:8787"
$env:ANTHROPIC_AUTH_TOKEN="sk-gw-...your key..."
# persist across sessions:
setx ANTHROPIC_BASE_URL "http://localhost:8787"
setx ANTHROPIC_AUTH_TOKEN "sk-gw-...your key..."
```
</details>

<details>
<summary><b>Global / per-project via settings.json</b></summary>

Put config in `~/.claude/settings.json` (global) or `.claude/settings.local.json` (per-project — never commit secrets to the tracked `settings.json`):

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8787",
    "ANTHROPIC_AUTH_TOKEN": "sk-gw-...your key...",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet"
  }
}
```
</details>

---

## 🔌 OpenAI-compatible endpoints

Beyond Claude Code, the gateway also exposes **OpenAI-compatible endpoints**, so any OpenAI-format client — the OpenAI SDK, Cline, Continue, LangChain, LiteLLM, etc. — can use it with the same gateway keys, model mappings, caching, rate limits, and usage tracking.

**Base URL:** `http://localhost:8787/openai/v1`

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8787/openai/v1",
    api_key="sk-gw-...your gateway key...",
)

resp = client.chat.completions.create(
    model="meta/llama-3.3-70b-instruct",   # raw NIM id, or a slot alias like "claude-sonnet"
    messages=[{"role": "user", "content": "Hello!"}],
)
print(resp.choices[0].message.content)
```

| Endpoint | Notes |
|---|---|
| `POST /openai/v1/chat/completions` | Streaming + non-streaming; tool calls; full OpenAI response shape |
| `GET /openai/v1/models` | Lists available NIM models |

**Model field** accepts either a **raw NIM id** (`meta/llama-3.3-70b-instruct` — passed through) or a **slot alias** (`claude-opus` / `claude-sonnet` / `claude-haiku`, resolved via your mappings). Auth is the same `Authorization: Bearer sk-gw-…` gateway key.

> Any tool built for OpenAI works unchanged — just point its base URL at `/openai/v1` and use a gateway key.

---

## 🔬 How model resolution works

Claude Code sends a Claude model string (e.g. `claude-sonnet-4-6`). The gateway:

1. **Classifies** it into a slot by substring — `opus` / `sonnet` / `haiku`.
2. **Looks up** the NIM model you mapped to that slot.
3. **Falls back** to your `default` mapping, or passes the string through unchanged (so you can send a raw NIM model id directly too).

---

## 🛡️ Security

- Gateway API keys are stored as **SHA-256 hashes** — plaintext shown once, never persisted.
- User passwords are **bcrypt**-hashed.
- `.env` is **gitignored** — your NVIDIA key never leaves your machine.
- Rotate any key that has been shared or committed.

---

## 🧩 Tech stack

- **Backend** — Python 3.12 · FastAPI · httpx (async streaming) · Motor (async MongoDB)
- **Auth** — JWT · passlib/bcrypt · SHA-256 key hashing
- **Frontend** — dependency-free HTML/CSS/JS (no build step), claude.ai-styled
- **Infra** — Docker Compose (gateway + MongoDB)

---

## 🗺️ Roadmap

- [x] **"Test model" button** — fire a probe completion to detect runnable vs 404 models
- [x] **Per-key rate limits & spend caps** — `rpm` + token cap per key, enforced with `429`
- [x] **Prometheus metrics export** — `/metrics` with request/token counters + latency histogram
- [x] **Response caching** — identical non-streaming requests served from a Mongo TTL cache
- [x] **Prompt-caching passthrough emulation** — `cache_read/creation_input_tokens` surfaced to Claude Code
- [x] **Multi-backend load balancing** — round-robin across NIM backends with 5xx/connection failover

🎉 **All roadmap items shipped.** New ideas? Open an issue.

### Advanced configuration

| Variable | Description | Default |
|---|---|---|
| `NIM_BACKENDS` | Extra backends for load balancing — comma-separated `url\|key` pairs | — |
| `CACHE_ENABLED` | Cache identical non-streaming responses | `true` |
| `CACHE_TTL_SECONDS` | Cache entry lifetime | `300` |

**Metrics:** scrape `GET /metrics` (Prometheus text format — unauthenticated, no secrets).
**Test a model:** click **Test** next to any slot on the Models page to confirm it's runnable before use.
**Rate limits / caps:** set per key at creation, or edit later via the **Limits** button on the API Keys page.

Contributions welcome — see below.

---

## 🤝 Contributing

PRs and issues are welcome! If you find a model that works especially well (or breaks), open an issue so we can grow the recommended-models table.

1. Fork the repo
2. `git checkout -b feature/your-feature`
3. Commit & push
4. Open a Pull Request

---

## 📜 License

[MIT](LICENSE) — do whatever you want, just don't blame us. 🙂

---

<div align="center">

**If this saved you money on API bills, drop a ⭐ — it helps others find it.**

Built for developers who want Claude Code's magic on open models.

</div>
