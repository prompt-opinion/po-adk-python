from dotenv import load_dotenv
load_dotenv()  # this reads your .env file and loads GOOGLE_API_KEY into the environment
import datetime
import json
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.tools import ToolContext
from a2a.types import AgentCard, AgentCapabilities, APIKeySecurityScheme, AgentExtension, SecurityScheme, In
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# ─── CONFIG ───────────────────────────────────────────────────────────────────

# In real life load this from environment variable or secrets manager
# Think of it like reading from appsettings.json / Azure Key Vault
VALID_API_KEYS = {
    "my-secret-key-123",   # your .NET app's key
    "another-valid-key",   # any other trusted callers
}

FHIR_CONTEXT_KEY = "fhir-context"


# ─── SECURITY MIDDLEWARE ───────────────────────────────────────────────────────

class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    Validates API key on every request EXCEPT the agent card endpoint.
    Think of this like an ASP.NET AuthorizationMiddleware / API key filter.
    
    Your .NET app must send this header on every call:
        X-API-Key: my-secret-key-123
    """
    async def dispatch(self, request: Request, call_next):
        
        # Always allow the agent card through — it's public by design
        # This is how callers discover your agent and know it needs a key
        if request.url.path == "/.well-known/agent-card.json":
            return await call_next(request)

        # Extract the API key from the request header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            print("[Security] Request rejected — no X-API-Key header provided")
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "detail": "X-API-Key header is required"}
            )

        if api_key not in VALID_API_KEYS:
            print(f"[Security] Request rejected — invalid API key: {api_key[:6]}...")
            return JSONResponse(
                status_code=403,
                content={"error": "Forbidden", "detail": "Invalid API key"}
            )

        print(f"[Security] Request authorised — key: {api_key[:6]}...")
        return await call_next(request)


# ─── FHIR CONTEXT MIDDLEWARE ───────────────────────────────────────────────────

def extract_fhir_context(callback_context, llm_request):
    """Extracts FHIR metadata from A2A message and stores in session state."""
    metadata = getattr(callback_context, "metadata", {}) or {}

    if not metadata:
        return None

    fhir_data = None
    for key, value in metadata.items():
        if FHIR_CONTEXT_KEY in key:
            if isinstance(value, dict):
                fhir_data = value
            else:
                fhir_data = json.loads(json.dumps(value))
            break

    if fhir_data:
        callback_context.state["fhir_url"]   = fhir_data.get("fhirUrl", "")
        callback_context.state["fhir_token"] = fhir_data.get("fhirToken", "")
        callback_context.state["patient_id"] = fhir_data.get("patientId", "")
        print(f"[FHIR] Context extracted for patient: {callback_context.state['patient_id']}")
    else:
        print(f"[FHIR] No FHIR context found. Keys: {list(metadata.keys())}")

    return None


# ─── TOOLS ────────────────────────────────────────────────────────────────────

def get_weather(city: str, tool_context: ToolContext) -> dict:
    """Retrieves the current weather report for a specified city."""
    patient_id = tool_context.state.get("patient_id", "unknown")
    print(f"[get_weather] city={city}, patient={patient_id}")

    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                f"The weather in New York is sunny with a temperature of 25 degrees "
                f"Celsius (77 degrees Fahrenheit). Patient context: {patient_id}"
            ),
        }
    return {
        "status": "error",
        "error_message": f"Weather information for '{city}' is not available.",
    }


def get_current_time(city: str, tool_context: ToolContext) -> dict:
    """Returns the current time in a specified city."""
    patient_id = tool_context.state.get("patient_id", "unknown")
    print(f"[get_current_time] city={city}, patient={patient_id}")

    if city.lower() == "new york":
        tz  = ZoneInfo("America/New_York")
        now = datetime.datetime.now(tz)
        return {
            "status": "success",
            "report": f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}',
        }
    return {
        "status": "error",
        "error_message": f"Sorry, I don't have timezone information for {city}.",
    }


# ─── AGENT ────────────────────────────────────────────────────────────────────

root_agent = Agent(
    name="weather_time_agent",
    model="gemini-2.0-flash",
    description="Agent to answer questions about the time and weather in a city.",
    instruction="You are a helpful agent who can answer user questions about the time and weather in a city.",
    tools=[get_weather, get_current_time],
    before_model_callback=extract_fhir_context,
)


# ─── AGENT CARD — tells callers this agent requires an API key ─────────────────

agent_card = AgentCard(
    name="weather_time_agent",
    description="Agent to answer questions about the time and weather in a city.",
    url="http://localhost:8001",
    version="1.0.0",
    defaultInputModes=["text/plain"],
    defaultOutputModes=["text/plain"],
      capabilities=AgentCapabilities(
        streaming=True,
        pushNotifications=False,
        stateTransitionHistory=True,
        extensions=[
            AgentExtension(
                uri="http://localhost:5139/schemas/a2a/v1/fhir-context",
                description="FHIR context allowing the agent to query a FHIR server securely",
                required=False,
            )
        ],
    ),
    skills=[],
    
    securitySchemes={
        "apiKey": SecurityScheme(
            root=APIKeySecurityScheme(
                type="apiKey",
                name="X-API-Key",
                in_=In.header,        # ← correct field name and enum value
                description="API key required to access this agent."
            )
        )
    },
    security=[{"apiKey": []}],
)


# ─── WIRE IT ALL TOGETHER ──────────────────────────────────────────────────────

a2a_app = to_a2a(root_agent, port=8001, agent_card=agent_card)

# Add security middleware — this is what actually enforces the key check
a2a_app.add_middleware(ApiKeyMiddleware)