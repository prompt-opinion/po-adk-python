> **Updated April 15, 2026 — Migrated to A2A Specification v1**
>
> The agent card published by all agents in this repo has been updated to comply with the **A2A v1 specification** as required by Prompt Opinion.
> The following changes were made to `shared/app_factory.py`:
>
> | What changed | Detail |
> |---|---|
> | `url` removed from agent card | Deprecated in v1. The agent's endpoint URL is now expressed via `supportedInterfaces` (see below). |
> | `preferredTransport` removed | Deprecated in v1. Preference order is now implicit — the first entry in `supportedInterfaces` is the preferred transport. |
> | `supportedInterfaces` added | New field. Each entry contains `url`, `protocolBinding`, and `protocolVersion`. Replaces `url` + `preferredTransport`. |
> | `capabilities.stateTransitionHistory` set to `false` | No longer supported by Prompt Opinion. Field is retained in the schema but must be `false`. |
> | `securitySchemes` schema updated | Each scheme is now nested under a typed key (e.g. `apiKeySecurityScheme`) per the v1 JSON shape. |
>
> The `url` parameter passed to `create_a2a_app()` in each agent's `app.py` is unchanged — it is still read from environment variables (`HEALTHCARE_AGENT_URL`, `GENERAL_AGENT_URL`, `ORCHESTRATOR_URL`) and is now placed inside `supportedInterfaces` instead of the top-level `url` field.

---

# Prompt Opinion Agent Examples
### Built with Google ADK · A2A Protocol · Python

Runnable examples showing how to build external agents that connect to **[Prompt Opinion](https://promptopinion.ai)** — the multi-agent platform for healthcare and enterprise workflows.

This is not a single-file template. It is a **monorepo with three working agents** that share a common infrastructure library. Clone it, run `adk web .` to see all three agents in a browser UI, then copy whichever example matches your use case and customise from there.

---

## Contents

- [What's in this repo](#whats-in-this-repo)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [The three agents](#the-three-agents)
  - [healthcare\_agent](#healthcare_agent--fhir-connected-clinical-assistant)
  - [general\_agent](#general_agent--general-purpose-assistant-no-fhir)
  - [orchestrator](#orchestrator--multi-agent-orchestrator)
- [The shared library](#the-shared-library)
- [Adding tools](#adding-tools)
- [FHIR context (optional)](#fhir-context-optional)
- [Configuration reference](#configuration-reference)
- [API security](#api-security)
- [Testing locally](#testing-locally)
- [Running with Docker (local)](#running-with-docker-local)
- [Deploying to Google Cloud Run](#deploying-to-google-cloud-run)
- [Connecting to Prompt Opinion](#connecting-to-prompt-opinion)

---

## What's in this repo

| Agent | Description | FHIR? | Port |
|---|---|---|---|
| `healthcare_agent` | Queries a patient's FHIR R4 record — demographics, meds, conditions, observations | ✅ Yes | 8001 |
| `general_agent` | Date/time queries and ICD-10-CM code lookups — no patient data needed | ❌ No | 8002 |
| `orchestrator` | Delegates to the other two agents using ADK's built-in sub-agent routing | ✅ Optional | 8003 |

All three share a `shared/` library that provides middleware, logging, the FHIR context hook, FHIR R4 tools, and an app factory — so each agent's own files stay small and focused.

---

## Architecture

```
Prompt Opinion
     │  POST /  X-API-Key  A2A JSON-RPC
     │
     ▼
┌──────────────────────────────────────────────────┐
│  shared/middleware.py  (ApiKeyMiddleware)         │
│  · validates X-API-Key                           │
│  · bridges FHIR metadata to params.metadata      │
└──────────────┬───────────────────────────────────┘
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
healthcare_  general_   orchestrator
agent        agent           │
   │           │          delegates
   │           │          via AgentTool
   ▼           ▼              │
shared/      local            ├──► healthcare_agent
fhir_hook    tools/           └──► general_agent
   │          general.py
   ▼
session state
(fhir_url, fhir_token, patient_id)
   │
   ▼
shared/tools/fhir.py  ──►  FHIR R4 server
```

**Key design principle:** FHIR credentials travel in the A2A message metadata — they never appear in the LLM prompt. The `extract_fhir_context` callback intercepts them before the model is called and stores them in session state, where tools read them at call time.

---

## A2A Specification Compatibility

This repo targets **A2A specification v1**, which is the version required by the Prompt Opinion platform.

The Python `a2a-sdk` library (latest: `0.3.x`) has not yet been updated to reflect the v1 schema changes. To bridge the gap, `shared/app_factory.py` includes a pair of thin forward-compatibility subclasses — `AgentCardV1` and `AgentExtensionV1` — that patch three fields the library does not yet expose:

| Field | Change in v1 | How it's handled |
|---|---|---|
| `supportedInterfaces` | New — replaces `url` + `preferredTransport` | Added as an explicit Pydantic field on `AgentCardV1` |
| `securitySchemes` | Schema changed to nested typed-key format (e.g. `apiKeySecurityScheme`) | Overridden to `dict[str, Any]` on `AgentCardV1` so the v1 JSON shape passes through unmodified |
| `params` on extensions | New — carries SMART scope declarations | Added as an explicit Pydantic field on `AgentExtensionV1` |

The top-level `url` field is still passed to satisfy the current library's Pydantic validation; the same URL is also placed in `supportedInterfaces` for v1 compliance.

**These shims will be removed** once `a2a-sdk` ships native v1 support. Watch for a `⚠ BREAKING CHANGES` entry in the [a2a-python changelog](https://github.com/google-a2a/a2a-python/blob/main/CHANGELOG.md) mentioning `AgentCard` or spec version. At that point:
1. Delete `AgentExtensionV1` and `AgentCardV1` from `app_factory.py`
2. Remove `url=url` from the `AgentCardV1(...)` constructor call
3. Restore the typed `SecurityScheme` constructors if the new library types serialise correctly

Everything else in the repo — agent logic, FHIR tools, middleware, Docker, Cloud Run — is unaffected by this compatibility layer.

---

## Quick start

### Prerequisites

- Python 3.11 or later
- A [Google AI Studio](https://aistudio.google.com/app/apikey) API key (free)
- Git

### 1 — Clone the repository

```bash
git clone https://github.com/your-org/prompt-opinion-adk-python.git
cd prompt-opinion-adk-python
```

### 2 — Create a virtual environment and install dependencies

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (Command Prompt)
.venv\Scripts\activate

pip install -r requirements.txt
```

### 3 — Configure environment variables

```bash
# macOS / Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env
```

Open `.env` and set your Google API key:

```env
GOOGLE_API_KEY=your-google-api-key-here
```

### 4 — Run the agents

**Option A — `adk web` (recommended for local development)**

Opens a visual chat UI in your browser. All three agents appear in the dropdown. No API key header required.

```bash
adk web .
```

Then open **http://localhost:8000** and select which agent to chat with.

> **Note:** `adk web` bypasses the A2A middleware, so FHIR tools will report missing credentials (no metadata is sent). Everything else — tool calls, model responses, instructions — works normally. Use this for developing and testing agent logic before wiring to Prompt Opinion.

---

**Option B — A2A servers (required to connect to Prompt Opinion)**

**All three at once with `honcho` (recommended):**

```bash
pip install -r requirements-dev.txt   # one-time
honcho start
```

All three agents start in a single terminal with colour-coded logs — `healthcare` in one colour, `general` in another, `orchestrator` in a third. Ports 8001, 8002, and 8003 are all live simultaneously.

**Or start them individually in separate terminals:**

```bash
# Terminal 1 — FHIR healthcare agent
uvicorn healthcare_agent.app:a2a_app --host 0.0.0.0 --port 8001

# Terminal 2 — General-purpose agent
uvicorn general_agent.app:a2a_app --host 0.0.0.0 --port 8002

# Terminal 3 — Orchestrator (delegates to agents 1 & 2)
uvicorn orchestrator.app:a2a_app --host 0.0.0.0 --port 8003
```

---

**Option C — Docker Compose (no Python install required)**

If you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed, you can run all three agents in containers without setting up a Python virtual environment at all.

```bash
# First run: build the image and start all three agents
docker compose up --build

# Subsequent runs (image already built)
docker compose up

# Stop all agents
docker compose down
```

Agents are available on the same ports as the bare-Python option — `localhost:8001`, `localhost:8002`, `localhost:8003`. See [Running with Docker (local)](#running-with-docker-local) for more detail.

### 5 — Verify an agent is running

```bash
curl http://localhost:8001/.well-known/agent-card.json
```

You should see the agent card JSON describing the agent's capabilities and security requirements.

---

## The three agents

### `healthcare_agent` — FHIR-connected clinical assistant

The most complete example. Receives FHIR credentials from the caller via A2A metadata, extracts them into session state, and uses them to query a FHIR R4 server.

**Files to change when building your own:**

| File | What to change |
|---|---|
| `healthcare_agent/agent.py` | Model, instruction, tools list |
| `healthcare_agent/app.py` | Agent name, description, URL, FHIR extension URI |
| `shared/tools/fhir.py` | Add or modify FHIR query tools |
| `shared/middleware.py` | Update `VALID_API_KEYS` |

**Use this as your starting point if** your agent needs to query patient data from a FHIR server.

---

### `general_agent` — General-purpose assistant (no FHIR)

The minimal example. No `before_model_callback`, no FHIR tools. Demonstrates that the FHIR layer is completely optional.

Includes two tools that work offline with no external APIs:
- `get_current_datetime(timezone)` — current date/time in any IANA timezone
- `look_up_icd10(term)` — ICD-10-CM code lookup from a built-in reference table (15 common conditions)

**Files to change when building your own:**

| File | What to change |
|---|---|
| `general_agent/agent.py` | Model, instruction, tools list |
| `general_agent/app.py` | Agent name, description, URL |
| `general_agent/tools/general.py` | Replace with your own tools |

**Use this as your starting point if** your agent does not need patient data (knowledge lookup, scheduling, notifications, etc.).

---

### `orchestrator` — Multi-agent orchestrator

Shows ADK's built-in sub-agent routing (`AgentTool`). Gemini decides which specialist to call based on the question. Both `healthcare_agent` and `general_agent` run in-process as sub-agents — no separate HTTP calls needed.

Session state is shared, so FHIR credentials extracted by the orchestrator's `before_model_callback` are immediately available to the `healthcare_agent`'s tools.

**Use this as your starting point if** you want a single endpoint that coordinates multiple specialties.

To add a third sub-agent:
1. Create a new agent package (copy `general_agent` as a template)
2. Import its `root_agent` in `orchestrator/agent.py`
3. Add `AgentTool(agent=your_new_agent)` to the tools list
4. Update the instruction

---

## The shared library

```
shared/
├── logging_utils.py    ANSI-colour logger, configure_logging(package_name)
├── middleware.py        API key enforcement + FHIR metadata bridging
├── fhir_hook.py        before_model_callback — extracts FHIR credentials into state
├── app_factory.py      create_a2a_app() — builds the A2A ASGI app for any agent
└── tools/
    ├── __init__.py     Re-exports all shared tools
    └── fhir.py         FHIR R4 query tools (demographics, meds, conditions, observations)
```

Think of `shared/` as a class library. Any agent can import from it:

```python
from shared.fhir_hook import extract_fhir_context
from shared.tools import get_patient_demographics
from shared.app_factory import create_a2a_app
```

`shared/` is never run directly — it has no `agent.py` or `app.py`.

---

## Adding tools

### To an existing agent

**Step 1** — Write the tool function (last param must be `tool_context: ToolContext`):

```python
# general_agent/tools/general.py
from google.adk.tools import ToolContext
import logging

logger = logging.getLogger(__name__)

def get_care_team(tool_context: ToolContext) -> dict:
    """Returns the patient's care team members."""
    patient_id = tool_context.state.get("patient_id", "unknown")
    logger.info("tool_get_care_team patient_id=%s", patient_id)
    # your implementation here
    return {"status": "success", "care_team": [...]}
```

**Step 2** — Export it from the tools `__init__.py`:

```python
from .general import get_current_datetime, look_up_icd10, get_care_team
__all__ = [..., "get_care_team"]
```

**Step 3** — Register it in `agent.py`:

```python
from .tools import get_current_datetime, look_up_icd10, get_care_team

root_agent = Agent(..., tools=[..., get_care_team])
```

### As a shared FHIR tool

Add it to `shared/tools/fhir.py`, export from `shared/tools/__init__.py`, then import it in any agent that needs it.

---

## FHIR context (optional)

FHIR context is **completely optional**. Agents that don't need it simply omit `before_model_callback` — `general_agent` is the example.

### How credentials flow

```
A2A request
  └── params.message.metadata
        └── "http://.../fhir-context": { fhirUrl, fhirToken, patientId }
              │
              ▼  shared/middleware.py bridges to params.metadata
              │
              ▼  extract_fhir_context() runs before every LLM call
              │
              ▼
        session state
              ├── fhir_url   → tool_context.state["fhir_url"]
              ├── fhir_token → tool_context.state["fhir_token"]
              └── patient_id → tool_context.state["patient_id"]
```

### What Prompt Opinion sends

```json
{
  "jsonrpc": "2.0",
  "method": "message/stream",
  "params": {
    "message": {
      "metadata": {
        "https://your-workspace.promptopinion.ai/schemas/a2a/v1/fhir-context": {
          "fhirUrl":   "https://your-fhir-server.example.org/r4",
          "fhirToken": "<short-lived-bearer-token>",
          "patientId": "patient-uuid"
        }
      },
      "parts": [{ "kind": "text", "text": "What medications is this patient on?" }],
      "role": "user"
    }
  }
}
```

### What if FHIR context is not sent?

`extract_fhir_context` writes nothing to session state. FHIR tools return a clear error message explaining that credentials were not provided. The agent passes that back to the caller rather than hallucinating data.

### Log markers to watch

| Log marker | Meaning |
|---|---|
| `FHIR_URL_FOUND` | FHIR server URL received |
| `FHIR_TOKEN_FOUND fingerprint=len=N sha256=X` | Token received (value never logged) |
| `FHIR_PATIENT_FOUND` | Patient ID received |
| `hook_called_fhir_found` | All three credentials stored in state |
| `hook_called_no_metadata` | Request had no metadata |
| `hook_called_fhir_not_found` | Metadata present but FHIR key not found |
| `hook_called_fhir_malformed` | FHIR key found but value was not a JSON object |

---

## Configuration reference

Copy `.env.example` to `.env` and set values before starting any server.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | **Yes** | — | Google AI Studio key for Gemini |
| `API_KEYS` | No | — | Comma-separated list of valid `X-API-Key` values for authenticated agents, e.g. `key1,key2` |
| `API_KEY_PRIMARY` | No | — | First named API key slot for authenticated agents |
| `API_KEY_SECONDARY` | No | — | Second named API key slot for authenticated agents |
| `PO_PLATFORM_BASE_URL` | No | `http://localhost:5139` | Base URL of your Prompt Opinion workspace. Used to construct the FHIR extension URI in the agent card for `healthcare_agent` and `orchestrator`. Set this to your actual workspace URL (e.g. `https://your-workspace.promptopinion.ai`). |
| `LOG_FULL_PAYLOAD` | No | `true` | Log full JSON-RPC request body on each request |
| `LOG_HOOK_RAW_OBJECTS` | No | `false` | Dump raw ADK callback objects — debug only |
| `HEALTHCARE_AGENT_URL` | No | `http://localhost:8001` | Public URL for the healthcare agent. Placed in the agent card's `supportedInterfaces` so Prompt Opinion knows where to send requests. |
| `GENERAL_AGENT_URL` | No | `http://localhost:8002` | Public URL for the general agent. Placed in the agent card's `supportedInterfaces`. |
| `ORCHESTRATOR_URL` | No | `http://localhost:8003` | Public URL for the orchestrator. Placed in the agent card's `supportedInterfaces`. |

---

## API security

Each agent independently controls whether it requires an API key.
The setting is declared in the agent's `app.py` and is automatically advertised in the agent card — so callers like Prompt Opinion discover the security requirement before sending any requests.

### Security modes at a glance

| Agent | `require_api_key` | Who can call it |
|---|---|---|
| `healthcare_agent` | `True` *(default)* | Only callers with a valid `X-API-Key` |
| `general_agent` | `False` | Anyone — no key needed |
| `orchestrator` | `True` *(default)* | Only callers with a valid `X-API-Key` |

### Changing an agent's security mode

Open the agent's `app.py` and set `require_api_key`:

```python
# healthcare_agent/app.py — authenticated (default)
a2a_app = create_a2a_app(
    ...
    require_api_key=True,   # agent card declares X-API-Key required
                            # ApiKeyMiddleware blocks requests without a valid key
)

# general_agent/app.py — anonymous / public
a2a_app = create_a2a_app(
    ...
    require_api_key=False,  # agent card declares no security scheme
                            # no middleware attached — all requests pass through
)
```

When `require_api_key=False`, the agent card's `security` field is empty — this is the standard A2A v1 way to signal "no authentication required" to any caller.

### Agent card security scheme format (A2A v1)

As of A2A v1, `securitySchemes` uses a nested typed-key format. The factory emits this automatically — you do not need to construct it yourself:

```json
"securitySchemes": {
  "apiKey": {
    "apiKeySecurityScheme": {
      "name": "X-API-Key",
      "in": "header",
      "description": "API key required to access this agent."
    }
  }
}
```

This replaced the previous `SecurityScheme(root=APIKeySecurityScheme(...))` typed wrapper from the older a2a-sdk API.

### Updating the allowed keys (authenticated agents only)

Configure one or more valid keys in your environment:

```python
# Either comma-separated:
API_KEYS=my-secret-key-123,another-valid-key

# Or named slots:
API_KEY_PRIMARY=my-secret-key-123
API_KEY_SECONDARY=another-valid-key
```

The middleware loads both formats automatically, so you can keep the example
multi-key friendly without storing secrets in source control.

In production, populate those environment variables from a secrets manager:

```python
# Example: inject API_KEYS or API_KEY_PRIMARY / API_KEY_SECONDARY
# from Azure Key Vault, AWS Secrets Manager, GCP Secret Manager, etc.
```

### Endpoints (per agent)

| Endpoint | `require_api_key=True` | `require_api_key=False` |
|---|---|---|
| `GET /.well-known/agent-card.json` | Open (always) | Open (always) |
| `POST /` | Requires `X-API-Key` | Open |

---

## Testing locally

A shell script exercises the full `healthcare_agent` pipeline with `curl`:

```bash
# Start the healthcare agent first (separate terminal)
uvicorn healthcare_agent.app:a2a_app --host 127.0.0.1 --port 8001 --log-level info

# Run all test cases
bash scripts/test_fhir_hook.sh
```

| Case | Description | Expected log marker |
|---|---|---|
| A | Missing API key | `security_rejected_missing_api_key` |
| B | Valid key, no metadata | `hook_called_no_metadata` |
| C | Valid key, wrong metadata key | `hook_called_fhir_not_found` |
| D | Valid key + FHIR context — clinical summary | `hook_called_fhir_found` |
| D2 | Valid key + FHIR context — vital signs | `tool_get_recent_observations` |
| E | Valid key + malformed FHIR value | `hook_called_fhir_malformed` |

---

## Running with Docker (local)

Docker lets you run the agents in containers on your local machine — no Python, no virtual environment, no `pip install`. You only need [Docker Desktop](https://www.docker.com/products/docker-desktop/).

This is also useful for testing the exact same image that will run in Google Cloud Run before you deploy.

### How the three tiers relate

```
Your machine (Option B)          Your machine (Option C)          Google Cloud Run
──────────────────────           ──────────────────────           ────────────────
Python venv + honcho             Docker Desktop                   Google's servers
    honcho start             →   docker compose up           →    gcloud run deploy
                                       ↕                                 ↕
                                same Dockerfile             same Dockerfile
```

All three options use the **same code and the same `Dockerfile`**. Docker and Cloud Run are not separate things — Cloud Run is just "Docker hosted by Google."

> **Only run one option at a time.** Docker (Option C) and honcho/uvicorn (Option B) all listen on the same ports — 8001, 8002, and 8003. If both are running simultaneously, the second one will crash with `address already in use`. Always stop one before starting the other.

---

### Start all three agents with Docker Compose

```bash
# First run — builds the image then starts all three agents
docker compose up --build

# Subsequent runs — image is already cached, starts immediately
docker compose up
```

| Agent | Local URL |
|---|---|
| `healthcare_agent` | http://localhost:8001 |
| `general_agent` | http://localhost:8002 |
| `orchestrator` | http://localhost:8003 |

> **Seeing logs in your terminal? That's correct.** `docker compose up` streams container output to the terminal you ran it from. The agents are running inside Docker — your terminal is just a live log viewer. To verify, open a second terminal and run `docker ps`; you should see three running containers. If you'd rather Docker run silently in the background, use `docker compose up -d` instead (see below).

**Stop the agents:**

```bash
docker compose down
```

> **Ctrl+C vs `docker compose down`:** If you started with `docker compose up` (attached), Ctrl+C stops the containers and frees the ports — but `docker compose down` is cleaner as it also removes the containers fully. If you started with `docker compose up -d` (background), Ctrl+C does nothing; you must run `docker compose down` to stop them.

**Run in the background (no log output in terminal):**

```bash
docker compose up -d             # start silently
docker compose logs -f           # view logs on demand (Ctrl+C to stop following)
docker compose logs -f healthcare # view one agent's logs only
```

**Rebuild after changing code:**

```bash
docker compose up --build
```

**Run a single agent only (e.g. for testing just `general_agent`):**

```bash
docker compose up general
```

---

### Run a single agent manually with plain Docker

```bash
# Build the image once
docker build -t adk-agents .

# Start the general_agent on port 8002
docker run --rm -p 8002:8002 \
  -e AGENT_MODULE=general_agent.app:a2a_app \
  -e PORT=8002 \
  -e GOOGLE_API_KEY=your-key-here \
  -e GOOGLE_GENAI_USE_VERTEXAI=FALSE \
  adk-agents
```

Change `AGENT_MODULE` and `-p` to start a different agent.

---

## Deploying to Google Cloud Run

Cloud Run is the recommended way to publish these agents with a permanent public HTTPS URL. Each agent runs as its own managed service. The [Cloud Run free tier](https://cloud.google.com/run/pricing#tables) includes:

| Resource | Free per month |
|---|---|
| Requests | 2,000,000 |
| Compute (memory) | 360,000 GB-seconds |
| Compute (CPU) | 180,000 vCPU-seconds |

This is more than enough for development and light production use. **Gemini model calls are billed through the AI Studio API** — using `GOOGLE_GENAI_USE_VERTEXAI=FALSE` (the default in `.env.example`) keeps you on the AI Studio free quota and avoids Vertex AI charges entirely.

> **Avoid Agent Engine.** Google ADK also offers "Agent Engine" (Vertex AI Managed Agents), which is a paid service with no free tier. The `gcloud run deploy` approach used here deploys to standard Cloud Run, which has the free tier above.

---

### Prerequisites

- A [Google Cloud account](https://cloud.google.com/free) (a billing account is required for account verification, but the free tier means no charges for normal dev usage)
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed
- A GCP project (create one at [console.cloud.google.com](https://console.cloud.google.com))

---

### Step 1 — One-time GCP setup

**Authenticate and point `gcloud` at your project:**

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

**Enable the required APIs** (takes ~1 minute, run once per project):

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

**Store your Google API key in Secret Manager** (keeps it out of deployment logs and the Cloud Console UI):

```bash
echo -n "your-google-api-key-here" | \
  gcloud secrets create google-api-key --data-file=-
```

---

### Step 2 — Deploy each agent

All three agents are built from the **same `Dockerfile`** at the root of the repo. The `AGENT_MODULE` environment variable tells the container which agent to start — so each Cloud Run service is just a separate deployment of the same image with a different value.

**Deploy `healthcare_agent`** (authenticated, FHIR-connected):

```bash
gcloud run deploy healthcare-agent \
  --source . \
  --region us-central1 \
  --set-env-vars "AGENT_MODULE=healthcare_agent.app:a2a_app,GOOGLE_GENAI_USE_VERTEXAI=FALSE" \
  --set-secrets "GOOGLE_API_KEY=google-api-key:latest" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3
```

**Deploy `general_agent`** (public, no API key needed):

```bash
gcloud run deploy general-agent \
  --source . \
  --region us-central1 \
  --set-env-vars "AGENT_MODULE=general_agent.app:a2a_app,GOOGLE_GENAI_USE_VERTEXAI=FALSE" \
  --set-secrets "GOOGLE_API_KEY=google-api-key:latest" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3
```

**Deploy `orchestrator`** (authenticated, delegates to both sub-agents in-process):

```bash
gcloud run deploy orchestrator \
  --source . \
  --region us-central1 \
  --set-env-vars "AGENT_MODULE=orchestrator.app:a2a_app,GOOGLE_GENAI_USE_VERTEXAI=FALSE" \
  --set-secrets "GOOGLE_API_KEY=google-api-key:latest" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3
```

After each deploy, `gcloud` prints the service URL — save all three:

```
Service URL: https://healthcare-agent-abc123-uc.a.run.app
Service URL: https://general-agent-abc123-uc.a.run.app
Service URL: https://orchestrator-abc123-uc.a.run.app
```

> **Note on `--allow-unauthenticated`:** This disables Cloud Run's IAM layer so requests can reach the agent without a Google identity. Application-level security (the `X-API-Key` header) is still enforced by `ApiKeyMiddleware` for the agents that require it. The `general_agent` is intentionally open.

---

### Step 3 — Set public URLs on each service

The agent card advertises the agent's own public URL so callers (including Prompt Opinion) know where to send requests. After deploying, update each service with its real Cloud Run URL:

```bash
# Replace the URLs below with the ones printed by gcloud in Step 2
HEALTHCARE_URL=https://healthcare-agent-abc123-uc.a.run.app
GENERAL_URL=https://general-agent-abc123-uc.a.run.app
ORCHESTRATOR_URL=https://orchestrator-abc123-uc.a.run.app

gcloud run services update healthcare-agent \
  --region us-central1 \
  --update-env-vars "HEALTHCARE_AGENT_URL=${HEALTHCARE_URL}"

gcloud run services update general-agent \
  --region us-central1 \
  --update-env-vars "GENERAL_AGENT_URL=${GENERAL_URL}"

gcloud run services update orchestrator \
  --region us-central1 \
  --update-env-vars "ORCHESTRATOR_URL=${ORCHESTRATOR_URL}"
```

> **Why the orchestrator doesn't need the other URLs:** Sub-agents run **in-process** via `AgentTool` — no HTTP calls are made from the orchestrator to the other Cloud Run services. `ORCHESTRATOR_URL` is only used for the agent card.

---

### Step 4 — Verify the deployments

```bash
# Check the agent card for each service
curl https://healthcare-agent-abc123-uc.a.run.app/.well-known/agent-card.json
curl https://general-agent-abc123-uc.a.run.app/.well-known/agent-card.json
curl https://orchestrator-abc123-uc.a.run.app/.well-known/agent-card.json

# Call the public general_agent (no key needed)
curl -X POST https://general-agent-abc123-uc.a.run.app/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"What is the ICD-10 code for hypertension?"}]}}}'
```

---

### Free tier tips

| Setting | Why it matters |
|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI=FALSE` | Uses AI Studio API key — Gemini free quota. Vertex AI is billed from the first call. |
| `--min-instances 0` | Container scales to zero when idle — no compute charge while no requests arrive. |
| `--max-instances 3` | Caps concurrency during development so you don't accidentally burn compute. |
| `--region us-central1` | Cloud Run free tier applies to this region; not all regions qualify. |

> **Cold starts:** With `--min-instances 0`, the first request after a period of inactivity takes a few extra seconds while the container boots. This is fine for development. Set `--min-instances 1` to keep a container warm at all times (approximately $5/month on Cloud Run sustained-use pricing).

---

### Why not `adk deploy cloud_run`?

Google ADK ships an `adk deploy cloud_run` command designed for agents served through the ADK web UI (`adk web`). It wraps the agent using ADK's built-in FastAPI server, not the A2A `to_a2a()` ASGI server that this repo uses.

Because these agents expose the A2A JSON-RPC protocol (required by Prompt Opinion), `gcloud run deploy --source .` is the correct approach. The deployment infrastructure is identical — managed containers on Cloud Run — but the server wrapper is `to_a2a()` + `uvicorn` rather than ADK's web UI.

---

## Connecting to Prompt Opinion

[Prompt Opinion](https://promptopinion.ai) is a multi-agent platform that orchestrates agents like these — routing conversations, injecting patient context, and composing results across multiple specialised agents.

### Registration steps

1. **Deploy your agent** to a publicly reachable URL (e.g. `https://my-agent.example.com`).

2. **Set the public URL** via environment variable — this URL is placed in the agent card's `supportedInterfaces` array (A2A v1 format):
   ```bash
   HEALTHCARE_AGENT_URL=https://my-agent.example.com
   ```

3. **Set your Prompt Opinion workspace base URL** so the FHIR extension URI in the agent card is correct:
   ```bash
   PO_PLATFORM_BASE_URL=https://your-workspace.promptopinion.ai
   ```
   This causes `fhir_extension_uri` to resolve to:
   `https://your-workspace.promptopinion.ai/schemas/a2a/v1/fhir-context`

4. **Register the agent in Prompt Opinion** by providing:
   - Agent card URL: `https://my-agent.example.com/.well-known/agent-card.json`
   - Your `X-API-Key` value (Prompt Opinion sends this on every request)

5. **Prompt Opinion discovers your agent** by fetching the agent card, reads `supportedInterfaces` to find your endpoint, learns that an API key is required, and begins routing requests to it.

### What Prompt Opinion provides

When your agent is called from Prompt Opinion, the platform automatically injects into the A2A message metadata:

- The patient's **FHIR server URL** for your workspace
- A **short-lived bearer token** scoped to the current user session
- The **patient ID** selected in the active encounter

Your tools receive these transparently from `tool_context.state` — you never handle FHIR authentication yourself.

---

## License

MIT

---

*Built on [Google ADK](https://google.github.io/adk-docs/) and the [A2A protocol](https://google.github.io/A2A/). Designed for the [Prompt Opinion](https://promptopinion.ai) multi-agent platform.*
