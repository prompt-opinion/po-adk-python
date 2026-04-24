"""
general_agent — Agent definition.

This agent works without any patient context or FHIR server.
It demonstrates the minimal agent pattern: tools + instruction, no callback.

To customise:
  • Change model, description, and instruction below.
  • Add or remove tools from the tools=[...] list.
  • Write new tool functions in general_agent/tools/general.py.
  • If you later need FHIR access, import extract_fhir_context from shared.fhir_hook
    and add it as before_model_callback, then import FHIR tools from shared.tools.
"""
import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .tools import get_current_datetime, look_up_icd10

# ── Model selection ────────────────────────────────────────────────────────────
# Set GENERAL_AGENT_MODEL in your .env to switch models.
#
# Native Gemini (default — no extra dependencies):
#   GENERAL_AGENT_MODEL=gemini-2.5-flash
#
# Any LiteLLM-supported model (requires OPENAI_API_KEY / ANTHROPIC_API_KEY etc.):
#   GENERAL_AGENT_MODEL=openai/gpt-4o
#   GENERAL_AGENT_MODEL=anthropic/claude-3-5-sonnet-20241022
# ──────────────────────────────────────────────────────────────────────────────
_model_name = os.getenv("GENERAL_AGENT_MODEL", "gemini-2.5-flash")
_model = _model_name if _model_name.startswith("gemini") else LiteLlm(model=_model_name)

root_agent = Agent(
    name="general_agent",
    model=_model,
    description=(
        "A general-purpose clinical assistant for date/time queries "
        "and ICD-10-CM code lookups. Does not require patient context."
    ),
    instruction=(
        "You are a helpful clinical assistant. "
        "Use the available tools to answer questions accurately. "
        "For date and time questions, always ask for a timezone if not provided — "
        "default to UTC if the user doesn't specify. "
        "For ICD-10 lookups, return the code and full description clearly. "
        "Never invent codes or dates — always use the tools."
    ),
    tools=[
        get_current_datetime,
        look_up_icd10,
    ],
    # No before_model_callback — this agent does not need patient/FHIR context.
    # This is intentional: it demonstrates that the FHIR hook is optional.
)
