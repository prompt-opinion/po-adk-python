"""
healthcare_agent — A2A application entry point.

Start the server with:
    uvicorn healthcare_agent.app:a2a_app --host 0.0.0.0 --port 8001

The agent card is served publicly at:
    GET http://localhost:8001/.well-known/agent-card.json

All other endpoints require an X-API-Key header (see shared/middleware.py).
"""
import os

from a2a.types import AgentSkill
from shared.app_factory import create_a2a_app

from .agent import root_agent

a2a_app = create_a2a_app(
    agent=root_agent,
    name="healthcare_fhir_agent",
    description=(
        "A clinical assistant that queries a patient's FHIR health record to answer "
        "questions about demographics, active medications, conditions, and observations."
    ),
    url=os.getenv("HEALTHCARE_AGENT_URL", "http://localhost:8001"),
    port=8001,
    # This URI is the key under which callers send FHIR credentials in the
    # A2A message metadata.  Update to match your Prompt Opinion workspace URL.
    fhir_extension_uri="http://localhost:5139/schemas/a2a/v1/fhir-context",
    skills=[
        AgentSkill(
            id="patient-demographics",
            name="patient-demographics",
            description="Retrieve patient demographics like name, DOB, and contacts.",
            tags=["demographics", "fhir"],
        ),
        AgentSkill(
            id="active-medications",
            name="active-medications",
            description="Get a list of the patient's active medications and dosages.",
            tags=["medications", "fhir"],
        ),
        AgentSkill(
            id="active-conditions",
            name="active-conditions",
            description="Get the patient's active conditions and diagnoses.",
            tags=["conditions", "fhir"],
        ),
        AgentSkill(
            id="recent-observations",
            name="recent-observations",
            description="Retrieve recent vitals, lab results, and social history.",
            tags=["observations", "fhir"],
        ),
    ],
)
