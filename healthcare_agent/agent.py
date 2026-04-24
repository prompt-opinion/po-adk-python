"""
healthcare_agent — Agent definition.

This agent has read-only access to a patient's FHIR R4 record.
FHIR credentials (server URL, bearer token, patient ID) are injected via the
A2A message metadata by the caller (e.g. Prompt Opinion) and extracted into
session state by extract_fhir_context before every LLM call.

To customise:
  • Change model, description, and instruction below.
  • Add or remove tools from the tools=[...] list.
  • Add new FHIR tools in shared/tools/fhir.py and export from shared/tools/__init__.py.
  • Add non-FHIR tools in shared/tools/ or locally in a tools/ folder here.
"""
import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from shared.fhir_hook import extract_fhir_context
from shared.tools import (
    get_active_conditions,
    get_active_medications,
    get_patient_demographics,
    get_recent_observations,
)

# ── Model selection ────────────────────────────────────────────────────────────
# Set HEALTHCARE_AGENT_MODEL in your .env to switch models.
#
# Native Gemini (default — no extra dependencies):
#   HEALTHCARE_AGENT_MODEL=gemini-2.5-flash
#
# Any LiteLLM-supported model (requires OPENAI_API_KEY / ANTHROPIC_API_KEY etc.):
#   HEALTHCARE_AGENT_MODEL=openai/gpt-4o
#   HEALTHCARE_AGENT_MODEL=anthropic/claude-3-5-sonnet-20241022
# ──────────────────────────────────────────────────────────────────────────────
_model_name = os.getenv("HEALTHCARE_AGENT_MODEL", "gemini-2.5-flash")
_model = _model_name if _model_name.startswith("gemini") else LiteLlm(model=_model_name)

root_agent = Agent(
    name="healthcare_fhir_agent",
    model=_model,
    description=(
        "A clinical assistant that queries a patient's FHIR health record "
        "to answer questions about demographics, medications, conditions, and observations."
    ),
    instruction=(
        "You are a clinical assistant with secure, read-only access to a patient's FHIR health record. "
        "Use the available tools to retrieve real data from the connected FHIR server when answering questions. "
        "Always fetch data using the tools — never make up or guess clinical information. "
        "Present medical information clearly and concisely, as if briefing a clinician. "
        "If a tool returns an error, explain what went wrong and suggest how to resolve it. "
        "If FHIR context is not available, let the caller know they need to include it in their request."
    ),
    tools=[
        get_patient_demographics,
        get_active_medications,
        get_active_conditions,
        get_recent_observations,
    ],
    # Runs before every LLM call.
    # Reads fhir_url, fhir_token, and patient_id from A2A message metadata
    # and writes them into session state so tools can call the FHIR server.
    before_model_callback=extract_fhir_context,
)
