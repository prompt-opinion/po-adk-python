"""
orchestrator — A2A application entry point.

Start the server with:
    uvicorn orchestrator.app:a2a_app --host 0.0.0.0 --port 8003

The agent card is served publicly at:
    GET http://localhost:8003/.well-known/agent-card.json

All other endpoints require an X-API-Key header (see shared/middleware.py).
"""
import os

from a2a.types import AgentSkill
from shared.app_factory import create_a2a_app

from .agent import root_agent

a2a_app = create_a2a_app(
    agent=root_agent,
    name="orchestrator",
    description=(
        "A clinical orchestrator that routes questions to specialist sub-agents: "
        "healthcare_fhir_agent for patient record queries, "
        "general_agent for date/time and ICD-10 lookups."
    ),
    url=os.getenv("ORCHESTRATOR_URL", "http://localhost:8003"),
    port=8003,
    # The orchestrator supports FHIR context so it can pass credentials through
    # to the healthcare sub-agent.
    fhir_extension_uri="http://localhost:5139/schemas/a2a/v1/fhir-context",
    skills=[
        AgentSkill(
            id="clinical-orchestration",
            name="clinical-orchestration",
            description="Routes questions to specialist agents (demographics, medications, vitals, ICD-10, date/time) to answer clinical queries.",
            tags=["clinical", "orchestrator", "routing"],
        ),
    ],
)
