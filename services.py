"""Catalog of services offered. Single source of truth used by the agent and emails.

Codes follow the egynaecologist Secure Booking Email Protocol where applicable; new
website-only bundles are given new codes prefixed BDL- to keep the front-desk mapping
sheet consistent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Service:
    code: str
    name: str
    price_pence: int
    duration_minutes: int
    category: str  # consultation | bundle
    triage_keywords: tuple[str, ...] = ()
    description: str = ""


SERVICES: tuple[Service, ...] = (
    # Consultations
    Service(
        code="INP-STD",
        name="First Consultation (In-Person)",
        price_pence=27500,
        duration_minutes=30,
        category="consultation",
        description="In-person first consultation at Harley Street.",
    ),
    Service(
        code="REM-STD",
        name="First Consultation Remote (Video)",
        price_pence=25000,
        duration_minutes=30,
        category="consultation",
        description="Video consultation from anywhere.",
    ),
    Service(
        code="INP-FU",
        name="Follow-up Consultation In-Person",
        price_pence=22500,
        duration_minutes=30,
        category="consultation",
    ),
    Service(
        code="REM-FU",
        name="Follow-up Consultation Remote",
        price_pence=20000,
        duration_minutes=30,
        category="consultation",
    ),
    Service(
        code="TEL-FU",
        name="Follow-up Consultation Telephone",
        price_pence=20000,
        duration_minutes=30,
        category="consultation",
    ),
    Service(
        code="SHORT-FU",
        name="Follow-up Short Call",
        price_pence=12000,
        duration_minutes=30,
        category="consultation",
    ),
    Service(
        code="REPEAT-RX",
        name="Repeat Prescription",
        price_pence=2500,
        duration_minutes=30,
        category="consultation",
    ),
    # Bundles (codes from the PDF where they exist)
    Service(
        code="BDL-PCOS",
        name="PCOS Care Bundle",
        price_pence=91000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("pcos", "polycystic", "irregular periods", "facial hair", "acne", "weight gain"),
    ),
    Service(
        code="BDL-MEN",
        name="Menopause / HRT Bundle",
        price_pence=89000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("menopause", "hrt", "hot flush", "hot flushes", "night sweat", "perimenopause", "hormone"),
    ),
    Service(
        code="BDL-FERT",
        name="Fertility Check Bundle",
        price_pence=95000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("fertility", "trying to conceive", "ttc", "cant conceive", "can't conceive", "ivf", "egg count", "amh"),
    ),
    Service(
        code="BDL-WW",
        name="Well Woman Care Bundle",
        price_pence=85000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("well woman", "annual check", "general check", "check up", "screening"),
    ),
    Service(
        code="BDL-SH",
        name="Sexual Health Bundle",
        price_pence=55000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("sti", "std", "sexual health", "discharge", "itching", "chlamydia", "gonorrhea"),
    ),
    Service(
        code="BDL-ENDO",
        name="Endometriosis Detection Bundle",
        price_pence=139000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("endometriosis", "endo", "painful periods", "pelvic pain", "heavy periods"),
    ),
    Service(
        code="BDL-COIL",
        name="Coil Fitting or Removal Bundle",
        price_pence=56000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("coil", "iud", "mirena", "copper coil", "fitting", "removal"),
    ),
    Service(
        code="BDL-BRCA",
        name="BRCA Gene Testing Bundle",
        price_pence=89000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("brca", "lynch", "family history of cancer", "genetic test", "hereditary"),
    ),
    Service(
        code="BDL-OVCA",
        name="Ovarian Cancer Detection Bundle",
        price_pence=83000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("ovarian cancer", "ca125", "bloating", "pelvic mass"),
    ),
    Service(
        code="BDL-HPV",
        name="HPV Vaccination Bundle",
        price_pence=63000,
        duration_minutes=30,
        category="bundle",
        triage_keywords=("hpv", "cervical vaccine", "gardasil"),
    ),
    Service(
        code="BDL-MISC",
        name="Recurrent Miscarriage Bundle",
        price_pence=0,  # not on website; PDF only — front desk will quote
        duration_minutes=30,
        category="bundle",
        triage_keywords=("miscarriage", "recurrent loss", "lost a baby", "lost pregnancy"),
    ),
    Service(
        code="BDL-FIB",
        name="Fibroid Monitoring Bundle",
        price_pence=0,  # not on website; PDF only — front desk will quote
        duration_minutes=30,
        category="bundle",
        triage_keywords=("fibroid", "fibroids"),
    ),
    Service(
        code="BDL-CS",
        name="Cancer Screening Bundle",
        price_pence=0,  # not on website; PDF only — front desk will quote
        duration_minutes=30,
        category="bundle",
        triage_keywords=("cancer screening", "smear", "cervical screening", "pap smear"),
    ),
)

BY_CODE = {s.code: s for s in SERVICES}
PUBLIC_SERVICES = tuple(s for s in SERVICES if s.price_pence > 0)


def format_price(price_pence: int) -> str:
    if price_pence == 0:
        return "price on request"
    return f"£{price_pence / 100:,.0f}"


def triage(text: str) -> list[Service]:
    """Return services whose triage keywords match the caller's free text. Order preserved."""
    if not text:
        return []
    lower = text.lower()
    hits: list[Service] = []
    for svc in SERVICES:
        for kw in svc.triage_keywords:
            if kw in lower:
                hits.append(svc)
                break
    return hits


def catalog_for_prompt() -> str:
    """Compact catalog the LLM can read inside the system prompt."""
    lines: list[str] = []
    lines.append("CONSULTATIONS:")
    for s in SERVICES:
        if s.category == "consultation":
            lines.append(f"  - {s.code}: {s.name} ({format_price(s.price_pence)})")
    lines.append("")
    lines.append("CARE BUNDLES (recommend based on caller symptoms / concerns):")
    for s in SERVICES:
        if s.category == "bundle":
            kw = ", ".join(s.triage_keywords[:4]) if s.triage_keywords else ""
            lines.append(
                f"  - {s.code}: {s.name} ({format_price(s.price_pence)}) "
                + (f"[match on: {kw}]" if kw else "")
            )
    return "\n".join(lines)
