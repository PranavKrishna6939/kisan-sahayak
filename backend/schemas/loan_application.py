"""Unified Indian Agricultural Loan Application schema derived from:
- Bank of India Form AG-100 (Agricultural Credit)
- SBI Loan Application for Agricultural Credit (PM-KISAN Beneficiaries)
- Axis Bank Kisan Power / Kisan Sampoorna / Kisan Rin Sahayata / Kisan Matsya
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class LoanApplication(BaseModel):
    # 1. Loan & Scheme Request
    facility_type: Optional[str] = Field(default=None, description="Fresh KCC / KCC Enhancement / Crop Loan / Agri-Term Loan / Dairy & Fisheries KCC / SHG")
    loan_purpose: Optional[str] = Field(default=None, description="Purpose of loan")
    amount_required_inr: Optional[str] = Field(default=None, description="Loan amount required in INR")

    # 2. Applicant Identity
    full_name: Optional[str] = Field(default=None)
    father_or_spouse_name: Optional[str] = Field(default=None)
    age: Optional[str] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    mobile_number: Optional[str] = Field(default=None)
    education_level: Optional[str] = Field(default=None)
    requires_thumb_impression_lti: Optional[str] = Field(default=None)
    social_category: Optional[str] = Field(default=None)

    # 3. Address & Location
    village: Optional[str] = Field(default=None)
    post_office: Optional[str] = Field(default=None)
    taluka_mandal: Optional[str] = Field(default=None)
    district: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    pin_code: Optional[str] = Field(default=None)
    residence_type: Optional[str] = Field(default=None)

    # 4. Land, Crops & Allied Activities
    land_title: Optional[str] = Field(default=None)
    total_land_acres: Optional[str] = Field(default=None)
    irrigated_acres: Optional[str] = Field(default=None)
    irrigation_source: Optional[str] = Field(default=None)
    survey_khasra_no: Optional[str] = Field(default=None)
    kharif_crops: Optional[str] = Field(default=None)
    rabi_crops: Optional[str] = Field(default=None)
    other_crops: Optional[str] = Field(default=None)
    allied_activities: Optional[str] = Field(default=None)
    farm_machinery: Optional[str] = Field(default=None)

    # 5. Banking, KYC & Income
    pm_kisan_beneficiary: Optional[str] = Field(default=None)
    existing_bank_name: Optional[str] = Field(default=None)
    has_savings_or_pmjdy_account: Optional[str] = Field(default=None)
    annual_agri_income_inr: Optional[str] = Field(default=None)
    annual_other_income_inr: Optional[str] = Field(default=None)
    available_kyc_docs: Optional[str] = Field(default=None)
    existing_loans_summary: Optional[str] = Field(default=None)

    # 6. Insurance & Field Agent Handoff
    pmfby_crop_insurance_consent: Optional[str] = Field(default=None)
    pmsby_pmjjby_consent: Optional[str] = Field(default=None)
    preferred_language: Optional[str] = Field(default=None)
    field_agent_visit_notes: Optional[str] = Field(default=None)
    verbal_consent_for_agent_callback: Optional[str] = Field(default=None)

    def apply_patch(self, patch: dict[str, Any]) -> list[str]:
        """Merge a validated dictionary patch into this application; return changed field names."""
        changed: list[str] = []
        valid_fields = set(self.__class__.model_fields.keys())
        for key, raw_val in patch.items():
            if key not in valid_fields:
                continue
            if raw_val is None:
                continue
            if isinstance(raw_val, list):
                val = ", ".join(str(x).strip() for x in raw_val if x is not None and str(x).strip())
            else:
                val = str(raw_val).strip()
            if not val or val.lower() in ("null", "none", "n/a", "unknown", ""):
                continue
            current = getattr(self, key)
            if current != val:
                setattr(self, key, val)
                changed.append(key)
        return changed


# 20 high-priority fields used for progress tracking and gentle conversation steering
CORE_PRIORITY_FIELDS: list[tuple[str, str]] = [
    ("loan_purpose", "What they need the loan for (crop expenses, dairy/fisheries, equipment)"),
    ("facility_type", "Type of loan facility (Fresh KCC, Crop Loan, Term Loan, Allied KCC)"),
    ("amount_required_inr", "Approximate loan amount needed in rupees"),
    ("full_name", "Farmer's full name"),
    ("father_or_spouse_name", "Father's or spouse's name"),
    ("village", "Village name"),
    ("district", "District name"),
    ("state", "State name"),
    ("land_title", "Whether land is owned, leased, or share-cropped"),
    ("total_land_acres", "Total farming land area (acres or bigha)"),
    ("kharif_crops", "Main Kharif (monsoon) crops grown"),
    ("rabi_crops", "Main Rabi (winter) crops grown"),
    ("irrigation_source", "Source of water / irrigation"),
    ("pm_kisan_beneficiary", "Whether they receive PM-KISAN (₹6,000/yr)"),
    ("existing_bank_name", "Which bank they currently have an account with"),
    ("available_kyc_docs", "Which documents they have (Aadhaar, Voter ID, land passbook)"),
    ("annual_agri_income_inr", "Rough annual farm income"),
    ("existing_loans_summary", "Whether they have any existing loan"),
    ("pmfby_crop_insurance_consent", "Whether interested in PMFBY crop insurance"),
    ("verbal_consent_for_agent_callback", "Consent for a local field agent to visit/call"),
]

FIELD_LABELS: dict[str, str] = {
    "facility_type": "Loan Facility Type",
    "loan_purpose": "Purpose of Loan",
    "amount_required_inr": "Amount Required (₹)",
    "full_name": "Full Name",
    "father_or_spouse_name": "Father / Spouse Name",
    "age": "Age / DOB",
    "gender": "Gender",
    "mobile_number": "Mobile Number",
    "education_level": "Education / Literacy",
    "requires_thumb_impression_lti": "Thumb Impression (LTI) Needed",
    "social_category": "Social Category",
    "village": "Village",
    "post_office": "Post Office",
    "taluka_mandal": "Taluka / Mandal",
    "district": "District",
    "state": "State",
    "pin_code": "PIN Code",
    "residence_type": "Residence Type",
    "land_title": "Land Title",
    "total_land_acres": "Total Land Area",
    "irrigated_acres": "Irrigated Area",
    "irrigation_source": "Irrigation Source",
    "survey_khasra_no": "Survey / Khasra No.",
    "kharif_crops": "Kharif Crops",
    "rabi_crops": "Rabi Crops",
    "other_crops": "Other / Horticulture Crops",
    "allied_activities": "Livestock / Dairy / Fisheries",
    "farm_machinery": "Farm Machinery Owned",
    "pm_kisan_beneficiary": "PM-KISAN Beneficiary",
    "existing_bank_name": "Existing Bank & Branch",
    "has_savings_or_pmjdy_account": "Savings / PMJDY Account",
    "annual_agri_income_inr": "Annual Farm Income (₹)",
    "annual_other_income_inr": "Other Annual Income (₹)",
    "available_kyc_docs": "Available KYC Documents",
    "existing_loans_summary": "Existing Loans / Liabilities",
    "pmfby_crop_insurance_consent": "PMFBY Crop Insurance",
    "pmsby_pmjjby_consent": "PMSBY / PMJJBY Insurance",
    "preferred_language": "Preferred Language",
    "field_agent_visit_notes": "Field Agent Visit Notes",
    "verbal_consent_for_agent_callback": "Agent Callback Consent",
}


def compute_recommended_schemes(app: LoanApplication) -> list[dict[str, str]]:
    """Deterministic eligibility engine suggesting matching Indian agri-credit schemes."""
    schemes: list[dict[str, str]] = []
    purpose_blob = " ".join(
        filter(
            None,
            [
                app.facility_type,
                app.loan_purpose,
                app.kharif_crops,
                app.rabi_crops,
                app.allied_activities,
                app.farm_machinery,
            ],
        )
    ).lower()

    if app.pm_kisan_beneficiary and app.pm_kisan_beneficiary.lower().startswith("y"):
        schemes.append({
            "id": "pm-kisan-kcc",
            "name": "PM-KISAN Fast-Track KCC",
            "badge": "1-Page Simplified Form",
            "highlight": "Fast approval via existing PM-KISAN bank KYC; effective 4% interest on timely repayment.",
        })

    if any(k in purpose_blob for k in ("crop", "kcc", "seed", "fertilizer", "wheat", "paddy", "rice", "cotton", "sugarcane", "soybean", "maize", "mustard")) or app.total_land_acres:
        schemes.append({
            "id": "kcc-miss",
            "name": "Kisan Credit Card (MISS 4%)",
            "badge": "4% Effective Interest",
            "highlight": "7% base rate reduced to 4% with 3% prompt repayment incentive; collateral-free up to ₹1.6–2 lakh.",
        })

    if any(k in purpose_blob for k in ("dairy", "cow", "buffalo", "cattle", "goat", "sheep", "poultry", "fish", "matsya", "animal", "milk")):
        schemes.append({
            "id": "kcc-allied",
            "name": "KCC Animal Husbandry & Fisheries",
            "badge": "Allied Working Capital",
            "highlight": "Working capital credit for dairy animals, goats/sheep, poultry, and aquaculture.",
        })

    if any(k in purpose_blob for k in ("tractor", "pump", "drip", "sprinkler", "harvester", "tiller", "warehouse", "cold storage", "shed", "machinery", "equipment", "term")):
        schemes.append({
            "id": "agri-term-aif",
            "name": "Agri-Term Loan / AIF",
            "badge": "Medium-Long Term",
            "highlight": "Equipment & farm infrastructure finance (up to 3% interest subvention under AIF).",
        })

    if app.kharif_crops or app.rabi_crops or (app.pmfby_crop_insurance_consent and app.pmfby_crop_insurance_consent.lower().startswith("y")):
        schemes.append({
            "id": "pmfby",
            "name": "PM Fasal Bima Yojana (PMFBY)",
            "badge": "1.5%–2% Premium",
            "highlight": "Crop loss protection against drought, flood & pests (2% Kharif, 1.5% Rabi).",
        })

    if not schemes:
        schemes.append({
            "id": "kcc-default",
            "name": "Kisan Credit Card (KCC)",
            "badge": "4% w/ Prompt Repayment",
            "highlight": "India's flagship low-interest credit scheme for crop & allied farmers.",
        })
    return schemes


def compute_completion(app: LoanApplication) -> dict[str, Any]:
    data = app.model_dump()
    core_filled = sum(1 for key, _ in CORE_PRIORITY_FIELDS if data.get(key))
    total_filled = sum(1 for v in data.values() if v)
    pct = min(100, round((core_filled / len(CORE_PRIORITY_FIELDS)) * 100))
    return {
        "core_filled": core_filled,
        "core_total": len(CORE_PRIORITY_FIELDS),
        "total_filled": total_filled,
        "total_fields": len(data),
        "percent": pct,
    }


def compute_conversation_stage(
    app: LoanApplication,
    transcript: list[dict[str, Any]],
) -> tuple[str, str]:
    """Return (stage_name, concrete_next_instruction) enforcing the credit-scheme-first flow:
    1. Confirm availability
    2. Farming type & whether they need credit/support
    3. Specific loan purpose
    4. Approximate loan amount
    5. Recommend the best matching scheme(s) clearly, then ask to start application filling
    6. Progressive application filling (one missing field at a time, zero repeats)
    """
    user_turns = [m for m in transcript if m.get("role") == "user"]
    assistant_turns = [m for m in transcript if m.get("role") == "assistant"]

    if len(user_turns) == 0:
        return (
            "Stage 1 — Check Availability",
            "Warmly greet the farmer and ask if they have two minutes to talk about low-interest agricultural loan schemes.",
        )

    has_farming = bool(
        app.kharif_crops or app.rabi_crops or app.other_crops or app.allied_activities
    )
    has_purpose = bool(app.loan_purpose or app.facility_type)
    has_amount = bool(app.amount_required_inr)

    if not has_farming and not has_purpose:
        return (
            "Stage 2 — Farming & Credit Need",
            "Ask what kind of farming or livestock work they do, and whether they currently need any loan or financial support.",
        )

    if not has_purpose:
        return (
            "Stage 3 — Loan Purpose",
            "Move straight to asking the exact purpose of the loan they need (e.g., seeds/fertilizer crop expenses, buying a tractor or pumpset, dairy/fisheries, or farm shed).",
        )

    if not has_amount:
        return (
            "Stage 4 — Loan Amount",
            "Ask approximately how much loan amount (in rupees) they need for this purpose.",
        )

    # Check whether we already gave a detailed scheme recommendation after learning purpose & amount
    recommended = compute_recommended_schemes(app)
    top_schemes_str = "; ".join(
        f"{s['name']} ({s['badge']}: {s['highlight']})" for s in recommended[:2]
    )

    # Heuristic: if none of the identity/location application fields are collected yet and we haven't
    # already pitched the scheme after amount was given, focus deeply on Stage 5 (Scheme Recommendation)
    app_started = bool(
        app.full_name
        or app.village
        or app.district
        or app.total_land_acres
        or app.existing_bank_name
        or app.pm_kisan_beneficiary
    )
    scheme_already_explained = any(
        any(kw in (m.get("text") or "").lower() for kw in ("4%", "चार प्रतिशत", "4 प्रतिशत", "subvention", "सब्सिडी", "aif", "बुनियादी ढांचा", "term loan", "टर्म लोन", "मियादी ऋण", "kisan credit card", "किसान क्रेडिट कार्ड"))
        for m in assistant_turns[1:]
    )

    if not app_started and not scheme_already_explained:
        return (
            "Stage 5 — Recommend Best Credit Scheme",
            f"Focus on explaining the best matching credit scheme clearly in 2–3 simple sentences tailored to their exact purpose ({app.loan_purpose or app.facility_type}) and amount (₹{app.amount_required_inr}): {top_schemes_str}. Explain the key benefit (interest rate/tenure/collateral), then ask if they would like you to prepare their loan application right now so a local agent can help submit it.",
        )

    return (
        "Stage 6 — Application Filling (One Uncollected Field at a Time)",
        "The scheme has been discussed. Now smoothly collect ONLY ONE uncollected field from the Next Missing Fields list below. Do NOT repeat scheme pitches, do NOT re-summarize earlier answers, and NEVER re-ask any field already listed under Already Collected Fields or already answered in the chat history.",
    )


def format_form_for_prompt(app: LoanApplication) -> tuple[str, str]:
    """Return (collected_summary_text, next_priority_missing_text) for dynamic LLM context."""
    data = app.model_dump()
    collected_lines = [
        f"- {FIELD_LABELS.get(k, k)}: {v}"
        for k, v in data.items()
        if v
    ]
    collected_str = "\n".join(collected_lines) if collected_lines else "(No details collected yet.)"

    missing_lines = [
        f"- {FIELD_LABELS.get(k, k)} ({desc})"
        for k, desc in CORE_PRIORITY_FIELDS
        if not data.get(k)
    ]
    next_missing_str = "\n".join(missing_lines[:4]) if missing_lines else "(All core details collected! Give a brief 2-sentence final summary and thank the farmer warmly.)"
    return collected_str, next_missing_str


def format_plain_text_document(app: LoanApplication) -> str:
    """Format the live application as a crisp human-readable loan application text sheet."""
    data = app.model_dump()
    sections = [
        ("1. LOAN & SCHEME REQUEST", ["facility_type", "loan_purpose", "amount_required_inr"]),
        ("2. APPLICANT IDENTITY", ["full_name", "father_or_spouse_name", "age", "gender", "mobile_number", "education_level", "requires_thumb_impression_lti", "social_category"]),
        ("3. ADDRESS & LOCATION", ["village", "post_office", "taluka_mandal", "district", "state", "pin_code", "residence_type"]),
        ("4. LAND, CROPS & ALLIED FARMING", ["land_title", "total_land_acres", "irrigated_acres", "irrigation_source", "survey_khasra_no", "kharif_crops", "rabi_crops", "other_crops", "allied_activities", "farm_machinery"]),
        ("5. BANKING, KYC & INCOME", ["pm_kisan_beneficiary", "existing_bank_name", "has_savings_or_pmjdy_account", "annual_agri_income_inr", "annual_other_income_inr", "available_kyc_docs", "existing_loans_summary"]),
        ("6. INSURANCE & FIELD AGENT HANDOFF", ["pmfby_crop_insurance_consent", "pmsby_pmjjby_consent", "preferred_language", "verbal_consent_for_agent_callback", "field_agent_visit_notes"]),
    ]
    lines = ["UNIFIED AGRICULTURAL CREDIT APPLICATION (PRE-FILING PROFILE)", "=" * 58, ""]
    for heading, keys in sections:
        lines.append(heading)
        lines.append("-" * len(heading))
        for k in keys:
            val = data.get(k) or "—"
            lines.append(f"  {FIELD_LABELS.get(k, k):<30}: {val}")
        lines.append("")
    schemes = compute_recommended_schemes(app)
    lines.append("RECOMMENDED SCHEMES")
    lines.append("-------------------")
    for s in schemes:
        lines.append(f"  • {s['name']} [{s['badge']}] — {s['highlight']}")
    return "\n".join(lines)
