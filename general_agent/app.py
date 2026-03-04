"""
general_agent — A2A application entry point.

This agent is intentionally PUBLIC — no API key is required.
The agent card advertises no security scheme, so Prompt Opinion and other
callers know they can send requests without a key.

Compare with healthcare_agent/app.py which sets require_api_key=True —
that agent's card declares X-API-Key as required and enforces it on every request.

Start the server with:
    uvicorn general_agent.app:a2a_app --host 0.0.0.0 --port 8002

The agent card is served publicly at:
    GET http://localhost:8002/.well-known/agent-card.json
"""
import os

from a2a.types import AgentSkill
from shared.app_factory import create_a2a_app

from .agent import root_agent

a2a_app = create_a2a_app(
    agent=root_agent,
    name="general_agent",
    description=(
        "A general-purpose clinical assistant for date/time queries and ICD-10-CM "
        "code lookups. Does not require patient context or FHIR credentials."
    ),
    url=os.getenv("GENERAL_AGENT_URL", "http://localhost:8002"),
    port=8002,
    # No fhir_extension_uri — this agent does not use FHIR context.
    # require_api_key=False — this agent is publicly accessible, no key needed.
    require_api_key=False,
    skills=[
        AgentSkill(
            id="date-time-lookup",
            name="date-time-lookup",
            description="Get the current date and time for any given timezone.",
            tags=["utility", "time"],
        ),
        AgentSkill(
            id="icd-10-lookup",
            name="icd-10-lookup",
            description="Look up ICD-10-CM codes and descriptions.",
            tags=["clinical", "icd10"],
        ),
    ],
)
