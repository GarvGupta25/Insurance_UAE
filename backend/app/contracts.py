from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Short = Annotated[str, Field(max_length=250)]
Answer = Literal["yes", "no", "unknown", "declined"]


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    legal_name: Short | None = None
    date_of_birth: date | None = None
    nationality: Short | None = None
    residency: Literal["citizen", "resident", "visitor", "pending"] | None = None
    emirate: (
        Literal["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Fujairah", "Ras Al Khaimah", "Umm Al Quwain"]
        | None
    ) = None
    area: Short | None = None
    mobile: Short | None = None
    address: Short | None = None
    emirates_id: Short | None = None
    passport_number: Short | None = None
    identity_expiry: date | None = None
    existing_cover: Answer | None = None
    current_insurer: Short | None = None
    current_cover_end: date | None = None
    start_date: date | None = None
    diagnosed_conditions: Answer | None = None
    conditions: list[Short] = Field(default_factory=list, max_length=30)
    medications: list[Short] = Field(default_factory=list, max_length=30)
    upcoming_care: Short | None = None
    immediate_chronic_cover: bool | None = None
    smoker: Answer | None = None
    maternity: bool | None = None
    maximum_maternity_wait: int | None = Field(default=None, ge=0, le=24)
    dental: Literal["none", "basic", "full"] | None = None
    preferred_network: Literal["restricted", "standard", "wide"] | None = None
    preferred_provider: Short | None = None
    geography: Literal["UAE", "international", "unsure"] | None = None
    cost_sharing: Literal["lower_premium", "lower_member_cost", "balanced"] | None = None
    payer: Literal["self", "employer", "sponsor"] | None = None
    annual_budget: int | None = Field(default=None, ge=0, le=1000000)
    strict_budget: bool | None = None
    payment_frequency: Literal["annual", "monthly"] | None = None
    company_name: Short | None = None
    sponsor_name: Short | None = None
    sponsor_relationship: Short | None = None
    funding_contact: Short | None = None
    contribution_aed: int | None = Field(default=None, ge=0, le=1000000)
    priorities: list[Short] = Field(default_factory=list, max_length=10)

    @field_validator("date_of_birth")
    @classmethod
    def past_birth(cls, value):
        if value and (value >= date.today() or value.year < 1900):
            raise ValueError("Enter a valid date of birth in the past.")
        return value

    @model_validator(mode="after")
    def consistent_health(self):
        if self.diagnosed_conditions == "no" and self.conditions:
            raise ValueError("A 'no diagnosed conditions' answer conflicts with the listed conditions.")
        if self.diagnosed_conditions == "yes" and not self.conditions:
            raise ValueError("Name the diagnosed condition, or choose unknown/declined.")
        return self


QUESTION_GROUPS = {
    "About you": ["legal_name", "date_of_birth", "nationality", "residency", "emirate"],
    "Health and cover": ["diagnosed_conditions", "smoker", "maternity", "geography", "start_date"],
    "Funding and preferences": ["payer", "annual_budget", "strict_budget", "payment_frequency"],
}
PROMPTS = {
    "legal_name": "What name should we use for your insurance profile?",
    "date_of_birth": "What is your date of birth?",
    "nationality": "What is your nationality?",
    "residency": "Are you a UAE citizen, resident, visitor, or awaiting residency?",
    "emirate": "Which emirate do you live in?",
    "diagnosed_conditions": "Do you have any diagnosed conditions you need covered?",
    "smoker": "Do you currently smoke? You can also say unknown or prefer not to answer.",
    "maternity": "Would you like maternity benefits included?",
    "geography": "Do you need cover within the UAE or internationally?",
    "start_date": "When would you like the policy to begin?",
    "payer": "Who will pay: you, an employer, or another sponsor?",
    "annual_budget": "What is your annual budget in AED?",
    "strict_budget": "Is that a strict maximum, or a flexible preference?",
    "payment_frequency": "Do you prefer an annual payment or monthly budgeting?",
    "company_name": "What is the employer's company name?",
    "sponsor_name": "What is the sponsor's name?",
    "contribution_aed": "How much will the employer or sponsor contribute in AED?",
    "maximum_maternity_wait": "How many months could you wait before maternity cover becomes usable?",
    "immediate_chronic_cover": "Do your existing conditions need insurance-funded care from the first day?",
}


def readiness(facts: dict):
    groups = {key: list(value) for key, value in QUESTION_GROUPS.items()}
    if facts.get("maternity"):
        groups["Health and cover"].append("maximum_maternity_wait")
    if facts.get("diagnosed_conditions") == "yes":
        groups["Health and cover"].append("immediate_chronic_cover")
    if facts.get("payer") == "employer":
        groups["Funding and preferences"] += ["company_name", "contribution_aed"]
    if facts.get("payer") == "sponsor":
        groups["Funding and preferences"] += ["sponsor_name", "contribution_aed"]
    missing = [
        key for values in groups.values() for key in values if facts.get(key) is None or facts.get(key) == ""
    ]
    return {
        "groups": groups,
        "missing": missing,
        "ready": not missing,
        "question": PROMPTS[missing[0]]
        if missing
        else "Your profile is ready. Get a quotation to compare your options.",
    }


class PatchRequest(BaseModel):
    expected_version: int
    changes: dict
    source_message_id: str | None = None


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    modality: Literal["text", "voice"] = "text"
    policy_id: str | None = None


class PrepareRequest(BaseModel):
    quote_id: str
    plan_id: str


class ConfirmRequest(BaseModel):
    payload_hash: str
    declarations_confirmed: bool


class SimulateRequest(BaseModel):
    result: Literal["captured", "failed", "cancelled"]


class VerifyPayment(BaseModel):
    order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
