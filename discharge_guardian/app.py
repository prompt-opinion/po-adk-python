"""
discharge_guardian — A2A application entry point.

Start the server with:
    uvicorn discharge_guardian.app:a2a_app --host 0.0.0.0 --port 8004

The agent card is served publicly at:
    GET http://localhost:8004/.well-known/agent-card.json

All other endpoints require an X-API-Key header (see shared/middleware.py).
"""
import os

from a2a.types import AgentSkill
from shared.app_factory import create_a2a_app

from .agent import root_agent

a2a_app = create_a2a_app(
    agent=root_agent,
    name="discharge_guardian",
    description=(
        "The Discharge Guardian performs comprehensive discharge safety assessments "
        "for hospitalized patients. It analyzes medication changes, lab safety, and "
        "follow-up completeness to identify risks during care transitions — catching "
        "issues that could lead to adverse events, readmissions, or patient harm. "
        "Consult this agent when preparing to discharge a patient from the hospital."
    ),
    url=os.getenv("DISCHARGE_GUARDIAN_URL", os.getenv("BASE_URL", "http://localhost:8004")),
    port=8004,
    fhir_extension_uri=f"{os.getenv('PO_PLATFORM_BASE_URL', 'http://localhost:5139')}/schemas/a2a/v1/fhir-context",
    fhir_scopes=[
        {"name": "patient/Patient.rs",           "required": True},
        {"name": "patient/MedicationRequest.rs", "required": True},
        {"name": "patient/Condition.rs",         "required": True},
        {"name": "patient/Observation.rs",       "required": True},
    ],
    skills=[
        AgentSkill(
            id="discharge-safety-assessment",
            name="discharge-safety-assessment",
            description=(
                "Performs a comprehensive discharge safety review including medication "
                "reconciliation, lab safety checks, and follow-up gap analysis. Returns "
                "a structured safety report with RED/YELLOW/GREEN flags and prioritized "
                "action items."
            ),
            tags=["discharge", "safety", "medication-reconciliation", "care-transitions", "fhir"],
        ),
        AgentSkill(
            id="medication-change-analysis",
            name="medication-change-analysis",
            description=(
                "Analyzes changes between pre-admission and discharge medication lists "
                "to identify drug interactions, contraindications, therapeutic duplications, "
                "and inappropriately discontinued medications."
            ),
            tags=["medications", "safety", "drug-interactions", "reconciliation"],
        ),
        AgentSkill(
            id="lab-safety-check",
            name="lab-safety-check",
            description=(
                "Cross-references recent lab values against discharge medications to "
                "identify unsafe combinations, missing monitoring labs, and concerning trends."
            ),
            tags=["labs", "safety", "monitoring", "fhir"],
        ),
        AgentSkill(
            id="followup-gap-detection",
            name="followup-gap-detection",
            description=(
                "Evaluates whether appropriate follow-up appointments, specialist referrals, "
                "and pending tests have been arranged for a patient being discharged."
            ),
            tags=["follow-up", "referrals", "care-coordination", "readmission-prevention"],
        ),
    ],
    require_api_key=True,
)
