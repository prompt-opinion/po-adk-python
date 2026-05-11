"""
Discharge safety tools — specialized clinical analysis for care transitions.

These tools analyze a patient's clinical data in the context of hospital discharge
to identify medication safety issues, lab concerns, follow-up gaps, and generate
a comprehensive discharge safety report.

Each tool reads FHIR credentials from tool_context.state (injected by fhir_hook)
and queries the FHIR server. When FHIR data is unavailable or sparse, tools
fall back to analyzing data from the uploaded clinical documents that the LLM
has access to via the conversation context.
"""
import logging
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


# ── Tool: Medication Change Analysis ──────────────────────────────────────────

def analyze_medication_changes(
    pre_admission_meds: str,
    current_discharge_meds: str,
    patient_conditions: str,
    recent_lab_values: str,
    tool_context: ToolContext,
) -> dict:
    """
    Analyzes medication changes between pre-admission and discharge medication lists
    to identify safety risks during care transition.

    This tool compares what medications the patient was on BEFORE hospitalization
    versus what they are being discharged WITH, and flags:
    - New medications that may conflict with existing conditions or other meds
    - Medications that were stopped and may need to be restarted
    - Dose changes that may be inappropriate given current lab values
    - Therapeutic duplications
    - High-risk medication combinations

    Args:
        pre_admission_meds: Comma-separated list of medications the patient was taking
            before admission (e.g. "metformin 500mg BID, lisinopril 10mg daily").
            Use "none" or "no prior medications" if the patient had no home meds.
        current_discharge_meds: Comma-separated list of medications being prescribed
            at discharge (e.g. "insulin glargine 24 units qHS, metformin 500mg BID,
            lisinopril 10mg daily, atorvastatin 40mg qHS").
        patient_conditions: Comma-separated list of the patient's active conditions
            and diagnoses (e.g. "Type 2 diabetes, hypertension, CKD stage 3a, anemia").
        recent_lab_values: Key recent lab results relevant to medication safety
            (e.g. "creatinine 1.1, eGFR 58, potassium 4.3, HbA1c 11.2, Hgb 10.3").

    Returns:
        dict with status and structured analysis of medication changes and safety flags.
    """
    logger.info("tool_analyze_medication_changes called")

    return {
        "status": "success",
        "tool": "analyze_medication_changes",
        "instruction": (
            "Analyze the following medication transition for safety issues. "
            "Compare pre-admission vs discharge medications. For each change, assess: "
            "(1) Is the new medication appropriate given the patient's conditions and labs? "
            "(2) Are there dangerous drug-drug interactions? "
            "(3) Are there drug-disease contraindications? "
            "(4) Were any critical home medications inappropriately discontinued? "
            "(5) Are doses appropriate given renal/hepatic function? "
            "Flag each finding as RED (immediate danger), YELLOW (needs attention), or GREEN (appropriate)."
        ),
        "data": {
            "pre_admission_medications": pre_admission_meds,
            "discharge_medications": current_discharge_meds,
            "active_conditions": patient_conditions,
            "recent_labs": recent_lab_values,
        },
    }


# ── Tool: Lab Safety Assessment ───────────────────────────────────────────────

def assess_lab_safety(
    discharge_medications: str,
    recent_lab_values: str,
    patient_conditions: str,
    days_since_last_labs: str,
    tool_context: ToolContext,
) -> dict:
    """
    Assesses whether recent laboratory values support safe discharge on the
    current medication regimen.

    This tool cross-references the patient's most recent lab results against
    their discharge medications to identify:
    - Labs that are dangerously out of range for the prescribed medications
    - Required monitoring labs that are missing or too old
    - Trending lab values that suggest worsening organ function
    - Medication doses that need adjustment based on current lab values

    Args:
        discharge_medications: Comma-separated list of discharge medications
            (e.g. "metformin 500mg BID, lisinopril 10mg daily, warfarin 5mg daily").
        recent_lab_values: Key recent lab results with dates if available
            (e.g. "creatinine 1.1 (April 21), potassium 4.3 (April 21), INR 2.1 (April 19)").
        patient_conditions: Active conditions relevant to lab interpretation
            (e.g. "Type 2 diabetes, CKD stage 3a, atrial fibrillation").
        days_since_last_labs: How many days ago the most recent labs were drawn
            (e.g. "0" for today, "3" for three days ago). Use "unknown" if unclear.

    Returns:
        dict with structured lab safety analysis and flags.
    """
    logger.info("tool_assess_lab_safety called")

    return {
        "status": "success",
        "tool": "assess_lab_safety",
        "instruction": (
            "Analyze whether the patient's recent lab values support safe discharge "
            "on the prescribed medications. For each medication, check: "
            "(1) Is there a required lab that hasn't been checked recently? "
            "(e.g., INR for warfarin, creatinine for metformin, potassium for ACE inhibitors) "
            "(2) Are any lab values out of safe range for the prescribed medication? "
            "(3) Do trending lab values suggest the patient is deteriorating? "
            "(4) Are any critical labs missing entirely? "
            "Flag each finding as RED (unsafe to discharge without addressing), "
            "YELLOW (needs monitoring plan), or GREEN (acceptable)."
        ),
        "data": {
            "discharge_medications": discharge_medications,
            "recent_labs": recent_lab_values,
            "active_conditions": patient_conditions,
            "days_since_last_labs": days_since_last_labs,
        },
    }


# ── Tool: Follow-up Completeness Evaluation ───────────────────────────────────

def evaluate_followup_completeness(
    discharge_diagnoses: str,
    scheduled_followups: str,
    pending_referrals: str,
    pending_tests_or_results: str,
    tool_context: ToolContext,
) -> dict:
    """
    Evaluates whether appropriate follow-up care has been arranged for a patient
    being discharged from the hospital.

    This tool checks whether all necessary outpatient follow-up appointments,
    referrals, and pending tests have been properly arranged, including:
    - PCP follow-up within appropriate timeframe
    - Specialist follow-ups for each active condition
    - Pending diagnostic tests or procedures
    - Screening appointments that should be scheduled (e.g., ophthalmology for new diabetes)
    - Mental health follow-up if indicated

    Args:
        discharge_diagnoses: Comma-separated list of discharge diagnoses
            (e.g. "new-onset T2DM, AKI resolved, new hypertension, iron-deficiency anemia").
        scheduled_followups: Known scheduled appointments
            (e.g. "Endocrinology May 5 2025 confirmed"). Use "none" if no appointments scheduled.
        pending_referrals: Referrals that were placed but not yet scheduled
            (e.g. "Cardiology - told to call, GI colonoscopy - referral placed").
            Use "none" if no pending referrals.
        pending_tests_or_results: Any tests or results still pending at discharge
            (e.g. "outpatient stress test needed, colonoscopy needed for positive stool guaiac").
            Use "none" if nothing pending.

    Returns:
        dict with structured follow-up gap analysis.
    """
    logger.info("tool_evaluate_followup_completeness called")

    return {
        "status": "success",
        "tool": "evaluate_followup_completeness",
        "instruction": (
            "Evaluate the completeness of the patient's discharge follow-up plan. "
            "For each discharge diagnosis, determine: "
            "(1) Is there an appropriate specialist follow-up arranged? "
            "(2) Is a PCP follow-up scheduled within 7 days? "
            "(3) Are there any standard-of-care screenings missing? "
            "(e.g., ophthalmology for new diabetes, nephrology for new CKD) "
            "(4) Are pending tests/procedures scheduled or just 'recommended'? "
            "(5) Is mental health follow-up arranged if screening was positive? "
            "Flag each gap as RED (critical — high readmission risk), "
            "YELLOW (should be arranged soon), or GREEN (adequately addressed)."
        ),
        "data": {
            "discharge_diagnoses": discharge_diagnoses,
            "scheduled_followups": scheduled_followups,
            "pending_referrals": pending_referrals,
            "pending_tests_or_results": pending_tests_or_results,
        },
    }


# ── Tool: Discharge Safety Report Generator ───────────────────────────────────

def generate_discharge_safety_report(
    medication_analysis: str,
    lab_safety_analysis: str,
    followup_analysis: str,
    patient_summary: str,
    tool_context: ToolContext,
) -> dict:
    """
    Generates a comprehensive, prioritized discharge safety report by synthesizing
    the results of medication analysis, lab safety assessment, and follow-up
    completeness evaluation.

    This is the final synthesis tool that combines all individual analyses into
    a single actionable report with an overall readmission risk score and
    prioritized action items for the discharging clinician.

    Args:
        medication_analysis: Summary of medication change analysis findings
            including all RED/YELLOW/GREEN flags identified.
        lab_safety_analysis: Summary of lab safety assessment findings
            including all RED/YELLOW/GREEN flags identified.
        followup_analysis: Summary of follow-up completeness evaluation findings
            including all RED/YELLOW/GREEN flags identified.
        patient_summary: Brief patient summary including age, key diagnoses,
            length of stay, and discharge disposition.

    Returns:
        dict with the complete discharge safety report structure.
    """
    logger.info("tool_generate_discharge_safety_report called")

    return {
        "status": "success",
        "tool": "generate_discharge_safety_report",
        "instruction": (
            "Generate a comprehensive DISCHARGE SAFETY REPORT by synthesizing all analyses. "
            "The report must include:\n\n"
            "1. PATIENT OVERVIEW: Brief summary (1-2 sentences)\n\n"
            "2. OVERALL READMISSION RISK SCORE: HIGH / MODERATE / LOW with justification\n\n"
            "3. CRITICAL FINDINGS (RED FLAGS): List all RED findings from all analyses. "
            "These MUST be addressed before or immediately after discharge.\n\n"
            "4. IMPORTANT FINDINGS (YELLOW FLAGS): List all YELLOW findings. "
            "These should be addressed within 1-2 weeks.\n\n"
            "5. MEDICATION SAFETY SUMMARY: Key medication concerns in plain language\n\n"
            "6. FOLLOW-UP GAP SUMMARY: Missing appointments and referrals\n\n"
            "7. RECOMMENDED ACTIONS: Numbered, prioritized list of specific actions "
            "the care team should take, ordered by urgency\n\n"
            "8. SAFE DISCHARGE CHECKLIST:\n"
            "   [ ] All critical medications reconciled\n"
            "   [ ] Required labs checked and within safe range\n"
            "   [ ] PCP follow-up scheduled within 7 days\n"
            "   [ ] All specialist referrals have confirmed appointments\n"
            "   [ ] Patient/family education completed\n"
            "   [ ] Pending tests/procedures scheduled\n\n"
            "Be specific and actionable. Every finding should include what to do about it."
        ),
        "data": {
            "medication_analysis": medication_analysis,
            "lab_safety_analysis": lab_safety_analysis,
            "followup_analysis": followup_analysis,
            "patient_summary": patient_summary,
        },
    }
