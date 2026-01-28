from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
import os
import re
import threading
import sqlite3
import time
from pathlib import Path
from dotenv import load_dotenv

# -----------------------------
# Environment & App Bootstrapping
# -----------------------------
load_dotenv()
app = FastAPI()

# Serve static files (expects /static/index.html and /static/info.html)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, status_code=200)

@app.get("/info", response_class=HTMLResponse)
async def read_info():
    with open("static/info.html", "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, status_code=200)

# -----------------------------
# OpenAI Client (kept but sandboxed to logistics-only)
# -----------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_TOGGLE_PREFIX = "beyond this,"

# -----------------------------
# Telemetry (in-memory counters)
# -----------------------------
intent_counts = {
    "emergency": 0,
    "help": 0,
    "no_insurance": 0,
    "doctor": 0,
    "missed_appt": 0,
    "fallback_llm": 0,
    "medical_block": 0,
}
_intent_lock = threading.Lock()

# -----------------------------
# SQLite persistence (durable telemetry)
# -----------------------------
DB_PATH = Path("telemetry.sqlite3")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,          -- unix epoch seconds
            route TEXT NOT NULL,          -- e.g., 'emergency', 'help', 'fallback_llm'
            language TEXT NOT NULL        -- 'en' or 'es'
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_route_ts ON intent_events(route, ts);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_lang_ts ON intent_events(language, ts);")
    conn.commit()
    conn.close()

def log_event(route: str, language: str):
    """Persist a single intent event. Fail-quietly to avoid interrupting UX."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO intent_events (ts, route, language) VALUES (?, ?, ?);",
            (int(time.time()), route, language or "en")
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # telemetry should never break the app flow

def _bump_intent(key: str, language: str = "en"):
    """Increment in-memory counter and persist to SQLite."""
    if key in intent_counts:
        with _intent_lock:
            intent_counts[key] += 1
    log_event(key, language)

init_db()

# -----------------------------
# Non-medical FAQ content (HTML snippets)
# -----------------------------
FAQ_HTML = """
<b>Mitchel and Shannon Wong Eye Institute — Quick Answers</b><br/><br/>
<b>Where is the clinic located?</b><br/>
Health Transformation Building, 1601 Trinity St, Building A, Austin, TX 78712<br/><br/>

<b>Where do I park?</b><br/>
There is a parking garage attached to the Health Transformation Building (shows as “Health Center Garage” on Google).<br/><br/>

<b>Is parking free or validated?</b><br/>
Parking is not free. Current garage rates are posted here:
<a href="https://parking.utexas.edu/parking/garages/garage-daily-parking-rates" target="_blank" rel="noopener noreferrer">UT Austin Garage Daily Rates</a>.<br/><br/>

<b>Which entrance or elevator should I use?</b><br/>
Use the main entrance near 17th St & Trinity, or take the parking garage elevators to the 1st floor of the Health Transformation Building.<br/><br/>

<b>I can’t find the clinic once inside — where should I go?</b><br/>
The clinic is on the <b>first floor</b>, across from the H-E-B Pharmacy. From the street entrance, walk past the front desk — the clinic will be on your left. If you parked on another level, use the elevators to the first floor. Staff at the front desks can help with directions.<br/><br/>

<b>Are wheelchairs or assistance available at check-in?</b><br/>
Availability may vary. Please call ahead so staff can arrange assistance or a wheelchair on arrival.<br/><br/>

<b>How should I contact the clinic?</b><br/>
<b>1-833-UT-CARES (1-833-882-2737)</b><br/><br/>

<hr style="border:none;border-top:1px solid #eee;margin:1rem 0;" />

<b>APPOINTMENT & SCHEDULING</b><br/><br/>

<b>How can I access my patient portal?</b><br/>
Use your UT Health Austin (UTHA) account to sign in to the patient portal.<br/><br/>

<b>How can I make an appointment?</b><br/>
• <i>Self-schedule</i>: For <b>follow-up</b> visits by established patients through your UTHA account.<br/>
• <i>New patient</i>: Call the UT Health Austin Access Center at <b>1-833-UT-CARES</b> to register and schedule. You may also request an appointment online via the clinic website.<br/><br/>

<b>How early should I arrive?</b><br/>
Plan to arrive <b>15 minutes</b> before your appointment to allow time for parking and wayfinding.<br/><br/>

<b>How long will my appointment take?</b><br/>
Most visits take <b>1–2 hours</b> depending on testing, imaging, and whether dilation is needed. As a teaching clinic, you may see a resident or fellow along with the supervising attending physician.<br/><br/>

<b>Do I need a referral?</b><br/>
No referral is needed for a cataract evaluation or general eye exam, but some conditions or insurance plans may require one. If you need help obtaining a referral, call <b>1-833-UT-CARES</b>.<br/><br/>

<b>Clinic FAQ:</b>
<a href="https://uthealthaustin.org/clinics/ophthalmology/faqs" target="_blank" rel="noopener noreferrer">uthealthaustin.org/clinics/ophthalmology/faqs</a>
"""

WHEELHOUSE_MSG_EN = (
    "That’s out of my wheelhouse. I only handle non-medical clinic info (scheduling, directions, parking, etc.). "
    "For medical questions, please call the clinic at <b>1-833-UT-CARES (1-833-882-2737)</b>."
)
WHEELHOUSE_MSG_ES = (
    "Eso está fuera de mi alcance. Solo manejo información administrativa (citas, direcciones, estacionamiento, etc.). "
    "Para preguntas médicas, por favor llama a la clínica al <b>1-833-UT-CARES (1-833-882-2737)</b>."
)

# ------------------------------------------------------------------
# START: Inserted triggers / JSON-like structure (DO NOT MODIFY BELOW)
# ------------------------------------------------------------------

FAQ_TRIGGERS = {
    "match_case_insensitive": True,
    "strip_punctuation": True,
    "faq": [

        # ---------------- LOCATION ----------------
        {
            "triggers": [
                "Where is the clinic located?",
                "where is the clinic located",
                "location",
                "clinic location",
                "where is the clinic",
                "where is",
                "how do I get there",
                "how do I get there?",
                "how do I get to the clinic",
                "how do I get to",
                "how to get there",
                "how to get to",
                "directions",
                "direction",
                "directions to",
                "how do I find the clinic",
                "find clinic",
                "clinic address",
                "address",
                "what is the address",
                "what's the address",
                "what is the clinic address",
                "what's the clinic address",
                "1601 Trinity",
                "1601 Trinity St",
                "Health Transformation Building",
                "Health Transformation Building address",
                "Building A",
                "Trinity St",
                "Austin address",
                "Austin TX address",
                "GPS",
                "gps",
                "map",
                "maps",
                "google maps",
                "waze",
                "google maps directions",
                "waze directions",
                "location please",
                "clinic location please",
                "\"Where is the clinic located?\"",
                "\"location\"",
                "\"how do I get there\"",
                "\"gps\"",
                "\"address\""
            ],
            "required_terms": [
                "clinic",
                "building",
                "health",
                "trinity",
                "1601",
                "map",
                "directions",
                "address",
                "gps",
                "location"
            ],
            "exclude_terms": [
                "parking",
                "park",
                "garage",
                "free",
                "validated",
                "validation",
                "cost",
                "fees",
                "price",
                "rates",
                "elevator",
                "entrance"
            ],
            "response": """Health Transformation Building, 1601 Trinity St Building A, Austin, TX 78712

*Do not use Google Maps or WAZE for directions, this sometimes sends you to the wrong location*"""
        },

        # ---------------- PARKING (WHERE) ----------------
        {
            "triggers": [
                "Where do I park?",
                "Parking",
                "park",
                "parking",
                "garage"
            ],
            "required_terms": [
                "park",
                "parking",
                "garage"
            ],
            "exclude_terms": [
                "free",
                "validated",
                "validation",
                "cost",
                "fees",
                "price",
                "rates"
            ],
            "response": "There is a parking garage attached to the Health Transformation Building, referred to “Health Center Garage” on Google."
        },

        # ---------------- PARKING (FREE / VALIDATED) ----------------
        {
            "triggers": [
                "Is parking free or validated?",
                "free parking",
                "parking cost",
                "parking fees",
                "pay for parking",
                "do i have to pay for parking",
                "do we have to pay for parking",
                "is there a charge for parking",
                "is parking paid",
                "paid parking",
                "is it free",
                "is parking free",
                "parking free",
                "is it validated",
                "parking validated",
                "validation",
                "parking rates",
                "parking rate",
                "parking prices",
                "parking price",
                "how much is parking",
                "how much to park"
            ],
            "required_terms": [
                "parking",
                "park",
                "garage",
                "free",
                "validated",
                "pay",
                "cost",
                "fees",
                "paid"
            ],
            "response": """Parking is not free and the prices for the garage are listed below. If you are a MAP patient, we are able to validate parking for you.

https://parking.utexas.edu/parking/garages/garage-daily-parking-rates"""
        },

        # ---------------- ENTRANCE / ELEVATOR ----------------
        {
            "triggers": [
                "Which entrance or elevator should I use?",
                "entrance",
                "elevator"
            ],
            "exclude_terms": [
                "free",
                "validated",
                "validation",
                "cost",
                "fees",
                "price",
                "rates"
            ],
            "response": "You can either use the main entrance located near the entrance of 17th Street and Trinity or use one of the elevators in the parking garage to make it to the first floor of the Health Transformation Building."
        },

        # ---------------- INSIDE BUILDING ----------------
        {
            "triggers": [
                "I can’t find the clinic once inside the Health Transformation Building - where should I go?",
                "lost",
                "can't find"
            ],
            "required_terms": [
                "clinic",
                "inside",
                "building",
                "find",
                "lost"
            ],
            "response": """The Mitchel and Shannon Wong Eye Institute is located on the first floor. You can use the elevators to go to the first floor if you’ve parked on a different level. Once on the first floor, the clinic is located across from the HEB pharmacy. If you are entering from the street entrance, walk past the front desk and the clinic should be located on your left hand side. If you have any questions, feel free to ask anyone at the front desks."""
        },

        # ---------------- EVERYTHING ELSE ----------------
        {
            "triggers": [
                "Are wheelchairs or assistance available at check-in?",
                "wheelchairs",
                "assistance"
            ],
            "response": "Patients should call upon arrival to let us know they’re here and which floor they’re on. We recommend parking in a handicap-accessible spot near the sliding glass doors in the garage for easier access."
        },
        {
            "triggers": [
                "How should I contact the clinic?",
                "contact",
                "phone"
            ],
            "response": "1-833-UT-CARES (1-833-882-2737)"
        },
        {
            "triggers": [
                "How can I access my patient portal?",
                "patient portal"
            ],
            "response": "Patient Portal"
        },
        {
            "triggers": [
                "How can I make an appointment?",
                "make appointment",
                "schedule",
                "self-schedule",
                "new patient"
            ],
            "response": """Self-schedule: Self-scheduling is now available only for follow-up appointments for established patients. If you’ve previously been seen by the clinic, you can make an appointment via your UTHA account. More information can be found here.

New patient: New patients should call the UT Health Austin Access Center at 1-833-UT-CARES(1-833-882-2737) to register and schedule an initial appointment or, you may REQUEST an appointment here."""
        },
        {
            "triggers": [
                "How early should I arrive before my appointment?",
                "how early",
                "arrival time"
            ],
            "response": "It is important to allow enough time to find parking and locate the clinic. Please show up 15-20 minutes prior to your appointment time.  Please allow time for traffic. If you are past 15 minutes, you will need to be rescheduled."
        },
        {
            "triggers": [
                "How long will my appointment take?",
                "appointment length",
                "how long"
            ],
            "response": """Most appointments take about 1–2 hours. The exact length depends on whether you are a new or returning patient and what kind of testing, imaging, or dilation is needed that day.

Because this is a university teaching clinic, your visit may involve:

Vision screening and imaging by a technician

Medical history review

Possible pupil dilation (which adds about 20–30 minutes for the drops to work)

Evaluation by both a resident or fellow and the supervising attending physician

To be safe, we recommend planning to be here for at least 2 hours, especially for first-time or complex visits."""
        },
        {
            "triggers": [
                "What do I need to bring with me?",
                "bring",
                "what to bring",
                "med list",
                "glasses"
            ],
            "response": """Please bring the following items with you:

A valid photo ID (multiple secondary IDs are acceptable if needed)

Your insurance card

A payment method for any co-pay

A current list of your medications

Your most recent pair of glasses

For your first visit, you or your family member/caregiver will also need to sign consent forms, including the Notice of Privacy Practices and Assignment of Benefits."""
        },
        {
            "triggers": [
                "Can I bring a family member or interpreter?",
                "family member",
                "interpreter"
            ],
            "response": "Yes. Due to limited space, only one family member will be able to accompany you during the exam."
        },
        {
            "triggers": [
                "Do I need a referral to be seen here?",
                "referral"
            ],
            "response": """Referral: You do not need a referral for a cataract evaluation or general eye exam. However, some conditions or insurance plans may require one.

If you need assistance obtaining a referral, please call the Mitchel and Shannon Wong Eye Institute at 1-833-UT-CARES(1-833-882-2737)."""
        },
        {
            "triggers": [
                "What if I’m running late?",
                "running late",
                "late"
            ],
            "response": "Our clinic allows a 15-minute grace period for late arrivals. If you arrive more than 15 minutes after your scheduled appointment time, you’ll need to reschedule."
        },
        {
            "triggers": [
                "How do I reschedule or cancel my appointment?",
                "reschedule",
                "cancel appointment"
            ],
            "response": """You will receive an additional email confirmation with a button allowing you to reschedule your appointment and a button allowing you to upload the appointment information to an electronic calendar of your choice. If you need to reschedule your appointment, you can click on the Reschedule button in your confirmation email or call UT Health Austin’s Access Center at 1-833-UT-CARES (1-833-882-2737).

Please note: If your appointment was scheduled within 72 hours (3 days) of the appointment date and time, your additional email confirmation will not include a button allowing you to reschedule your appointment. If you need to reschedule your appointment, please contact UT Health Austin’s Access Center at 1-833-UT-CARES (1-833-882-2737)"""
        },
        {
            "triggers": [
                "Will my eyes be dilated today?",
                "will i be dilated",
                "dilated",
                "dilation"
            ],
            "response": """Whether or not your eyes will be dilated depends on your specific clinic visit. Your provider will discuss with you if dilation is necessary.

All first time patients will be dilated to ensure that we are providing comprehensive care. If you cannot be dilated at your visit, you may be asked to reschedule your appointment to a different day that is more convenient for you."""
        },
        {
            "triggers": [
                "How long will dilation last?",
                "how long dilation"
            ],
            "response": "Dilation usually lasts about 4–6 hours, but it varies from person to person. During that time, your vision may be blurry up close and you may be sensitive to bright light.The dilation will wear off gradually and your vision will return to normal on its own. We recommend bringing sunglasses, which we can also provide if needed."
        },
        {
            "triggers": [
                "Can I drive after being dilated?",
                "drive after dilation"
            ],
            "response": "Most patients can still drive safely, especially if it’s daytime and light prescription — but if you’re unsure, it’s safest to arrange a driver."
        },
        {
            "triggers": [
                "Can my child go to school if they had their eyes dilated?",
                "child school dilation"
            ],
            "response": "Yes, most children can still go to school after dilation. Their near vision may be a little blurry and they may be sensitive to light, so we recommend bringing sunglasses or a hat. Some children have no issues at all. If your child is very light-sensitive or needs to do a lot of reading immediately afterward, you may want to let the teacher know ahead of time."
        },
        {
            "triggers": [
                "Will there be additional testing or imaging today?",
                "OCT",
                "visual field",
                "imaging"
            ],
            "response": "Possibly. It depends on the reason for your visit and what the doctor determines is needed. Many patients have imaging or tests done at the same visit to avoid coming back again - such as OCT scans, visual field testing, or retinal photos. If additional testing is required, we'll explain it to you before proceeding."
        },
        {
            "triggers": [
                "Do I need to fast or prepare in any way before the appointment?",
                "fast",
                "prepare"
            ],
            "response": "No fasting is required for regular eye appointments. You can eat and take your normal medications as usual. Please bring a list of your medications and your current glasses or contact lens prescription. If you're a new patient, we recommend arriving a little early to complete paperwork."
        },
        {
            "triggers": [
                "Do you take my insurance",
                "what insurance",
                "insurances",
                "what insurance do you take",
                "insurance",
                "billing"
            ],
            "response": """We accept most major insurance plans. Please note:

TRICARE: Requires a referral

MAP: Requires a referral from your primary care provider (PCP) or community care

A list of accepted insurance plans includes:

Accountable Health Plan/Interplan (SPHN)

Aetna Whole Health

Aetna Medicare Advantage

Aetna PPO/HMO*** (Be aware of Aetna HMO CVS Plans)

Aetna Seton Health Alliance

Allied (PPO)

Ambetter-Superior Health Plan - CORE Exchange Plan

AARP Medicare Advantage Walgreens PPO (United Healthcare Plan)

Anthem BCBS of California (PPO)

Angle Health Cigna PPO

Assured Benefits Administrators (PPO)

Beech Street PPO (SPHN)

Blue Cross Blue Shield Blue Essentials/Blue Essentials Access - Exchange Plan

Blue Cross Blue Shield Blue Choice PPO/UT Select

Blue Cross Blue Shield Blue Advantage HMO***/Health Select***

Blue Cross Blue Shield PAR Plan

Blue Cross Blue Shield Medicaid - STAR/CHIP

Blue Cross Blue Shield - Blue Horizon (EPO/PPO - The Plan acts as a PPO)

MAP/MAP Basic

Cigna - All plans

Cigna Behavioral Health

Coventry (SPHN)

Curative POS/PPO

Dell Children's Health Plan STAR/CHIP

EHN/WEB TPA - (Whole Foods - Only)

First Health (SPHN)

Galaxy (SPHN)

Group & Pension Administrators (Aetna Signature Plan)

Health Payors Organization (SPHN)

Healthsmart (SPHN)

Humana Medicare Advantage

Humana HMOx

Humana PPO/HMO***/Choice Care

Humana Gold Plus (WellMed)

Integrated Medical Systems PPO (SPHN)

Magellan (Behavioral Health)

Medicaid/TMHP

Medicare - Part B (Traditional)

Multiplan (SPHN) (***PHCS is out of network)

Oscar Healthcare (SPHN)

Optum (Behavioral Health) - Please view credentialing sheet for in network/Pending Providers

Sendero Idealcare  

Seton Health Plan Smarthealth  

Superior Health Plan STAR/CHIP/STAR KIDS

Tricare Select - Retired Spouse/Family (Considered Non-Network Providers)

Tricare for Life (Medicare Supplement)

United Healthcare Dual Complete Focus HMO (Community Plan)

United Healthcare Community Plan - Medicaid

United One Healthcare

Golden Rule United Healthcare

UMR - US Health Group

United Healthcare Medicare Replacement/Advantage

United Healthcare All Savers/Choice/Choice Plus/HMO***/PPO

United Healthcare Shared Services

United Student Resources PPO (SPHN)

USA Managed Care (SPHN)

WellCare Medicare Advantage/Medicaid Plans"""
        },
        {
            "triggers": [
                "Which plans require a PCP referral before scheduling?",
                "PCP referral",
                "referral required"
            ],
            "response": "Plans that: Require a PCP Referral Before Scheduling\n\nBCBS (ALL HMO)\n\nBCBS - Health Select POS (Referral Exclusions for Ophthalmology, Mental Health Providers, Chiropractic, Physical Therapy, Speech Therapy, OB Gyn MDs, Walk In)\n\nHumana Gold Plus HMO (Lexington Address)\n\nUnited Healthcare Navigate\n\nUnited Healthcare Compass EPO"
        },
        {
            "triggers": [
                "Will I need to pay anything today?",
                "pay today",
                "copay"
            ],
            "response": "It will depend on your insurance. Please ask the front desk if you have any questions or concerns."
        },
        {
            "triggers": [
                "Do you offer payment plans?",
                "payment plan",
                "self-pay"
            ],
            "response": """We accept most commercial insurance plans, as well as MAP and TRICARE (with a referral). For patients without insurance, we offer a self-pay option with discounts:

38% discount if paid in full on the day of your appointment

25% discount if using a payment plan"""
        },
        {
            "triggers": [
                "Who do I contact if I have billing questions later?",
                "billing questions",
                "billing contact"
            ],
            "response": "The phone number for the billing department is 512-495-5910"
        },
        {
            "triggers": [
                "If I need surgery, how soon could it be scheduled?",
                "surgery",
                "schedule surgery"
            ],
            "response": "Surgery scheduling depends on the doctor’s availability, but it typically takes 6–8 weeks to secure a date."
        },
        {
            "triggers": [
                "Where will the surgery take place?",
                "surgery location"
            ],
            "response": "Surgeries are performed in the suite next door, located down the hall to the left of H-E-B."
        },
        {
            "triggers": [
                "Do I need someone to drive me home afterward?",
                "drive home",
                "someone drive"
            ],
            "response": "Yes, you will need a responsible adult companion to drive you home afterward. This cannot be an Uber, Waymo, etc."
        },
        {
            "triggers": [
                "How soon will I be able to return to work or school?",
                "return to work",
                "return to school"
            ],
            "response": "You should expect to resting the day of surgery and the day immediately following surgery. Physical restrictions will be given to you at your day one post op visit as well as when you can return to work. Most surgeries could expect to be back to work by day 2 with restrictions."
        },
        {
            "triggers": [
                "If you prescribe eye drops, where do I pick them up?",
                "prescription",
                "eye drops"
            ],
            "response": "Prescriptions are sent electronically to the pharmacy you share with your technician or doctor. You won’t receive a paper prescription—your medication will be ready for pickup at your chosen pharmacy."
        },
        {
            "triggers": [
                "What if my pharmacy doesn’t have the medication?",
                "pharmacy doesn't have",
                "pharmacy"
            ],
            "response": "First ask the pharmacy if they can request the medication be ordered or if another pharmacy has it. If neither can be done, then call the clinic. \n\n1-833-UT-CARES (1-833-882-2737)"
        },
        {
            "triggers": [
                "Can you send prescriptions electronically?",
                "electronic prescriptions"
            ],
            "response": "All prescriptions are sent electronically."
        },
        {
            "triggers": [
                "Will I get appointment reminders?",
                "reminders",
                "appointment reminders"
            ],
            "response": "You should be getting automated text and email reminders."
        },
        {
            "triggers": [
                "How do I contact the clinic with questions after my visit?",
                "after visit",
                "follow up questions"
            ],
            "response": "The most efficient method of communicating with the clinic is via the EMR Portal, otherwise you can call the clinic.\n\n1-833-UT-CARES(1-833-882-2737).\nOperators are on queue from 8-5pm."
        },
        {
            "triggers": [
                "What symptoms should make me call immediately?",
                "emergency symptoms",
                "call immediately",
                "urgent"
            ],
            "response": "Some symptoms should prompt you to call and schedule a visit immediately include; but not limited to: Persistent flashes of light, a shower of floaters in your vision, sudden loss of vision, a dark curtain covering your vision, and severe pain in the eye (with or without touching)."
        }
    ]
}

# ------------------------------------------------------------------
# END: Inserted triggers / JSON-like structure
# ------------------------------------------------------------------

# -----------------------------
# Keyword Router (deterministic, non-medical only)
# -----------------------------
def keyword_router(text: str, language: str = "en"):
    """
    Deterministic router for non-medical clinic assistance.
    Priority: emergencies → explicit medical → FAQ_TRIGGERS → logistics/intake helpers.

    IMPORTANT for your use case:
    - We collect ALL best-matching FAQ responses so overlapping buzzwords
      will show the most relevant answers instead of just the first.
    """
    t = (text or "").lower().strip()
    is_es = (language == "es")

    # Helper: normalize by lowercasing and stripping punctuation (used for trigger matching)
    def _normalize_for_matching(s: str):
        if s is None:
            return ""
        normalized = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
        normalized = re.sub(r"\s+", " ", normalized).strip().lower()
        return normalized

    # auto-link raw URLs at render time
    def linkify_urls(txt: str) -> str:
        if not txt:
            return txt
        url_pattern = r'(https?://[^\s<>"\']+)'
        return re.sub(
            url_pattern,
            r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
            txt
        )

    # Emergency-like phrases → do NOT answer medically; redirect
    emergency_patterns = [
        r"\b(sudden vision loss|lost vision|can'?t see|vision went black|blackout vision|curtain|shadow|veil)\b",
        r"\b(severe eye pain|intense eye pain|worst eye pain)\b",
        r"\b(flashes? (and|&)? floaters?|flashes|floaters)\b",
        r"\b(chemical in (my )?eye|eye burn)\b",
        r"\b(pérdida súbita de visión|no veo|visión negra|cortina|sombra)\b",
        r"\b(dolor ocular intenso|peor dolor ocular)\b",
        r"\b(destellos|moscas volantes)\b",
    ]

    # Medical-topic keywords (conditions, symptoms, meds)
    medical_keywords = [
        r"\b(cataract|glaucoma|dry eye|diabetic|retina|uveitis|pink eye|conjunctivitis|infection|injury|abrasion|ulcer|stye|chalazion|migraine|headache)\b",
        r"\b(dilate|dilation drops|pupil dilation|eye drops?|antibiotic|steroid|prednisone|timolol|latanoprost|restasis|xiidra|injection)\b",
        r"\b(surgery|procedure|lasik|prk|intravitreal|post[- ]?op|pre[- ]?op)\b",
        r"\b(vision blurry|blurry vision|double vision|photophobia|light sensitive|pain|redness|itching|tearing)\b",
        r"\b(ojo seco|glaucoma|catarata|conjuntivitis|infecci[oó]n|lesi[oó]n|cirug[ií]a|gote|gotas)\b",
    ]

    def any_match(patterns):
        return any(re.search(p, t) for p in patterns)

    # 1) Emergencies and medical topics → wheelhouse message
    if any_match(emergency_patterns) or any_match(medical_keywords):
        _bump_intent("medical_block", language)
        return {"answer": WHEELHOUSE_MSG_ES if is_es else WHEELHOUSE_MSG_EN}

    # 2) Check FAQ_TRIGGERS with chunking + multi-answer + guardrails
    try:
        def _split_into_chunks(s: str) -> list[str]:
            s = (s or "").strip()
            if not s:
                return []
            s = re.sub(r"\s+", " ", s)
            parts = re.split(
                r"\b(?:and|also|plus|then)\b|[/?;]|(?:\s-\s)|(?:\s&\s)",
                s,
                flags=re.IGNORECASE
            )
            chunks = [p.strip() for p in parts if p and p.strip()]
            return chunks[:8]

        def _passes_guardrails(text_norm: str, faq_item: dict, full_text_norm: str) -> bool:
            """
            Guardrails:
            - exclude_terms: ONLY apply to the CURRENT CHUNK (text_norm)
              so multi-part queries can match different FAQs.
            - required_terms: can appear in chunk OR full text.
            """
            # Exclude terms (chunk-only)
            for term in (faq_item.get("exclude_terms", []) or []):
                nt = _normalize_for_matching(term)
                if nt and nt in text_norm:
                    return False

            # Required terms (chunk OR full)
            required = (faq_item.get("required_terms", []) or [])
            if required:
                ok = False
                for term in required:
                    nt = _normalize_for_matching(term)
                    if nt and (nt in text_norm or nt in full_text_norm):
                        ok = True
                        break
                if not ok:
                    return False

            return True

        def _score_text_against_faq(text_norm: str, full_text_norm: str) -> dict[str, int]:
            words_local = set(text_norm.split())
            scores: dict[str, int] = {}

            for faq_item in FAQ_TRIGGERS.get("faq", []):
                if not _passes_guardrails(text_norm, faq_item, full_text_norm):
                    continue

                triggers = faq_item.get("triggers", []) or []
                score = 0

                for trig in triggers:
                    norm_trig = _normalize_for_matching(trig)
                    if not norm_trig:
                        continue
                    if " " in norm_trig:
                        if norm_trig in text_norm:
                            score += 2 * len(norm_trig.split())
                    else:
                        if norm_trig in words_local:
                            score += 2

                if score > 0:
                    resp = faq_item.get("response")
                    if resp:
                        prev = scores.get(resp, 0)
                        if score > prev:
                            scores[resp] = score

            return scores

        chunks = _split_into_chunks(text)
        chunk_norms = [_normalize_for_matching(text)] + [_normalize_for_matching(c) for c in chunks]
        chunk_norms = [c for c in chunk_norms if c]

        full_norm = _normalize_for_matching(text)

        MAX_ANSWERS = 5
        chosen: list[str] = []
        seen: set[str] = set()

        SHORT_QUERY_WORDS = 2
        for c_norm in chunk_norms:
            chunk_scores = _score_text_against_faq(c_norm, full_norm)
            if not chunk_scores:
                continue

            ranked = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)

            word_count = len(c_norm.split())
            is_short = word_count <= SHORT_QUERY_WORDS

            best_score = ranked[0][1]
            # If the best match is weak (score 1), allow it; otherwise keep stricter behavior.
            THRESHOLD = 1 if best_score <= 1 else max(2, best_score - 1)

            for i, (resp, sc) in enumerate(ranked):
                if resp in seen:
                    continue

                if is_short:
                    SHORT_THRESHOLD = max(1, best_score - 2)
                    if i < 3 and sc >= SHORT_THRESHOLD:
                        chosen.append(resp)
                        seen.add(resp)
                else:
                    if sc >= THRESHOLD:
                        chosen.append(resp)
                        seen.add(resp)

                if len(chosen) >= MAX_ANSWERS:
                    break

            if len(chosen) >= MAX_ANSWERS:
                break

        if chosen:
            _bump_intent("help", language)
            combined_answer = "\n\n<hr />\n\n".join(chosen)
            combined_answer = linkify_urls(combined_answer)
            return {"answer": combined_answer}

    except Exception:
        pass

    return None

# -----------------------------
# Request Model
# -----------------------------
class Query(BaseModel):
    question: str
    language: str = "en"

# -----------------------------
# Core Q&A Endpoint (LLM fenced to logistics-only)
# -----------------------------
@app.post("/ask")
async def ask_question(query: Query):
    q_raw = (query.question or "").strip()

    # Accept: "beyond this," "beyond this:" "beyond this" (any spacing/case)
    m = re.match(r"^\s*beyond\s+this\s*[:,]?\s*(.*)$", q_raw, flags=re.IGNORECASE)
    beyond_enabled = m is not None
    user_text = (m.group(1).strip() if beyond_enabled else q_raw)

    # 1) Deterministic router first (use cleaned text)
    routed = keyword_router(user_text, query.language)
    if routed is not None:
        return routed

    # 2) If no deterministic match, only allow LLM when opted-in
    if not beyond_enabled:
        return {
            "answer": (
                "I don’t have a clinic-approved answer for that. "
                "Please ask about scheduling, directions, parking, insurance/billing, or clinic logistics. "
                "If you want me to try a guardrailed AI response for a non-medical question, start your message with: "
                "<b>beyond this,</b>"
            )
        }

    if not user_text:
        return {
            "answer": "Please type your question after <b>beyond this,</b> (non-medical clinic logistics only)."
        }

    # 3) Guardrailed LLM (logistics-only)
    try:
        _bump_intent("fallback_llm", query.language)
        is_es = query.language == "es"

        system_prompt = (
            "You are a clinic logistics assistant for the Mitchel and Shannon Wong Eye Institute. "
            "ANSWER ONLY about non-medical topics: scheduling/rescheduling, directions, parking, entrances/elevators, "
            "finding the clinic inside the Health Transformation Building, patient portal access, contact numbers, referrals in general terms. "
            "NEVER discuss symptoms, diagnoses, treatments, medications, tests, or surgeries. "
            "If a question is medical, reply EXACTLY with: "
            f"'{WHEELHOUSE_MSG_ES if is_es else WHEELHOUSE_MSG_EN}'. "
            "Be concise."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        )
        return {"answer": response.choices[0].message.content.strip()}
    except Exception:
        return {"answer": FAQ_HTML}

# -----------------------------
# Telemetry Endpoints
# -----------------------------
@app.get("/telemetry", response_model=dict)
async def get_telemetry():
    """Aggregate in-memory counters (since last restart)."""
    with _intent_lock:
        return dict(intent_counts)

@app.get("/telemetry/monthly")
async def telemetry_monthly():
    """
    Returns counts per month (YYYY-MM) by route for the whole dataset.
    Example: [{"month":"2025-01","route":"emergency","count":12}, ...]
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT strftime('%Y-%m', datetime(ts, 'unixepoch')) AS month,
               route,
               COUNT(*) AS count
        FROM intent_events
        GROUP BY month, route
        ORDER BY month, route;
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"month": m, "route": r, "count": c} for (m, r, c) in rows]

@app.get("/telemetry/export.csv")
async def telemetry_export_csv():
    """
    Raw CSV export with ts (epoch), route, language.
    Useful for offline analysis in R/Python/Excel.
    """
    import io, csv
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT ts, route, language FROM intent_events ORDER BY ts;")
    rows = cur.fetchall()
    conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ts", "route", "language"])
    w.writerows(rows)
    csv_data = buf.getvalue()
    buf.close()
    return HTMLResponse(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=telemetry_export.csv"}
    )
