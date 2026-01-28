from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
import os
import re
from dotenv import load_dotenv

# =============================
# App Setup
# =============================
load_dotenv()
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    return open("static/index.html", encoding="utf-8").read()

@app.get("/info", response_class=HTMLResponse)
async def info():
    return open("static/info.html", encoding="utf-8").read()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================
# Models
# =============================
class Query(BaseModel):
    question: str
    language: str = "en"

# =============================
# Bilingual Helper
# =============================
def pick(lang, en, es):
    return es if lang == "es" else en

# =============================
# HARD CODED FAQ (ADMIN ONLY)
# =============================
FAQ = [

    # ================= CONTACT =================
    {
        "triggers": ["contact", "phone", "call", "clinic number", "reach you", "contact clinic"],
        "en": "You can contact UT Health Austin at 1-833-UT-CARES (1-833-882-2737).",
        "es": "Puede comunicarse con UT Health Austin al 1-833-UT-CARES (1-833-882-2737)."
    },

    {
  "triggers": [
    "help",
    "what can you do",
    "what can you help with",
    "i'm new",
    "new patient",
    "first time",
    "how does this work"
  ],
  "en": (
    "I can help with:\n\n"
    "- Scheduling appointments\n"
    "- Directions and parking\n"
    "- Insurance accepted\n"
    "- Billing and payments\n"
    "- Patient portal access\n"
    "- Clinic services and specialties\n"
    "- Memory and cognitive care resources\n"
    "- Caregiver support information\n\n"
    "Tell me what you need help with."
  ),
  "es": (
    "Puedo ayudar con:\n\n"
    "- Programar citas\n"
    "- Direcciones y estacionamiento\n"
    "- Seguros aceptados\n"
    "- Pagos y facturación\n"
    "- Acceso al portal del paciente\n"
    "- Servicios y especialidades\n"
    "- Recursos de memoria y cognición\n"
    "- Apoyo para cuidadores\n\n"
    "Dígame cómo puedo ayudarle."
    )
    },


    # ================= APPOINTMENTS =================
    {
        "triggers": ["appointment", "schedule", "make appointment", "book appointment", "request appointment", "cita", "agendar"],
        "en": "You can request an appointment online here: https://myuthasecure.org/ or call 1-833-UT-CARES.",
        "es": "Puede solicitar una cita en línea aquí: https://myuthasecure.org/ o llamar al 1-833-UT-CARES."
    },

    # ================= DIRECTIONS =================
    {
        "triggers": ["directions", "location", "address", "where are you", "map", "how do i get there"],
        "en": "The clinic is located at the Health Transformation Building, 1601 Trinity Street, Building A, Austin, TX 78712. Map: https://www.google.com/maps/place/UT+Health+Austin/@30.2769977,-97.7360977,17.67z",
        "es": "La clínica está ubicada en el Health Transformation Building, 1601 Trinity Street, Building A, Austin, TX 78712. Mapa: https://www.google.com/maps/place/UT+Health+Austin/@30.2769977,-97.7360977,17.67z"
    },

    # ================= REFERRALS =================
    {
        "triggers": ["refer a patient", "provider referral", "doctor referral", "send referral"],
        "en": "Providers can refer a patient here: https://refer.myuthasecure.org/",
        "es": "Los proveedores pueden enviar una referencia aquí: https://refer.myuthasecure.org/"
    },

    # ================= BILLING =================
    {
        "triggers": ["pay bill", "billing", "payment", "bill", "pay my bill"],
        "en": "You can pay your bill online here: https://16041-1.portal.athenahealth.com/",
        "es": "Puede pagar su factura en línea aquí: https://16041-1.portal.athenahealth.com/"
    },

    {
    "triggers": [
        "insurance",
        "insurances",
        "insurance accepted",
        "accepted insurance",
        "what insurance do you take",
        "do you take insurance",
        "insurance plans",
        "health insurance",
        "coverage"
    ],
    "en": (
        "Insurance Accepted:\n\n"
        "- AARP Medicare Complete Focus Essential HMO\n"
        "- AARP Medicare Complete Focus HMO\n"
        "- Accountable Health Plan / Interplan (SPHN)\n"
        "- Aetna Medicare Advantage\n"
        "- Aetna PPO / HMO (All HMO plans require a referral)\n"
        "- Aetna Seton Health Alliance\n"
        "- Aetna Whole Health\n"
        "- Ambetter–Superior Health Plan (Exchange Plan)\n"
        "- Amerigroup / Amerivantage Classic\n"
        "- Beech Street PPO (SPHN)\n"
        "- Blue Cross Blue Shield Blue Advantage HMO / Health Select (Referral required)\n"
        "- Blue Cross Blue Shield Blue Choice PPO / UT Select\n"
        "- Blue Cross Blue Shield Blue Essentials / Blue Essentials Access (Exchange)\n"
        "- Blue Cross Blue Shield PAR Plan\n"
        "- Cigna – All plans\n"
        "- Cigna Behavioral Health\n"
        "- Coventry (SPHN)\n"
        "- Dell Children’s Health Plan STAR / CHIP\n"
        "- EHN / WEB TPA (Whole Foods)\n"
        "- First Care Access PPO Network (SPHN)\n"
        "- First Health (SPHN)\n"
        "- FirstCare HMO (SPHN) (Referral required)\n"
        "- Galaxy (SPHN)\n"
        "- Health Payors Organization (SPHN)\n"
        "- HealthSmart (SPHN)\n"
        "- Humana HMOx\n"
        "- Humana Medicare Advantage (except Humana Gold Plus)\n"
        "- Humana PPO / HMO / Choice Care (Referral required)\n"
        "- Integrated Medical Systems PPO (SPHN)\n"
        "- Medicaid / TMHP (Not accepted in Walk-In Clinic)\n"
        "- Medicare Part B (Traditional fee-for-service – Novitas)\n"
        "- Multiplan (SPHN) (PHCS out of network)\n"
        "- Optum\n"
        "- Oscar Healthcare (SPHN)\n"
        "- Seton Health Plan\n"
        "- SmartHealth\n"
        "- Superior Health Plan STAR / CHIP / STAR Kids\n"
        "- UnitedHealthcare AARP PPO\n"
        "- UnitedHealthcare All Savers / Choice / Choice Plus / PPO / HMO (Referral required)\n"
        "- UnitedHealthcare Community Plan – Medicaid\n"
        "- UnitedHealthcare Dual Complete Focus HMO\n"
        "- UnitedHealthcare Medicare\n"
        "- UnitedHealthcare One\n"
        "- United Student Resources PPO (SPHN)\n"
        "- USA Managed Care (SPHN)\n\n"
        "If you do not see your plan listed, please call 1-833-UT-CARES to confirm coverage."
    ),
    "es": (
        "Seguros aceptados:\n\n"
        "- AARP Medicare Complete Focus Essential HMO\n"
        "- AARP Medicare Complete Focus HMO\n"
        "- Accountable Health Plan / Interplan (SPHN)\n"
        "- Aetna Medicare Advantage\n"
        "- Aetna PPO / HMO (Los planes HMO requieren referencia)\n"
        "- Aetna Seton Health Alliance\n"
        "- Aetna Whole Health\n"
        "- Ambetter–Superior Health Plan (Plan de intercambio)\n"
        "- Amerigroup / Amerivantage Classic\n"
        "- Beech Street PPO (SPHN)\n"
        "- Blue Cross Blue Shield Blue Advantage HMO / Health Select (Referencia requerida)\n"
        "- Blue Cross Blue Shield Blue Choice PPO / UT Select\n"
        "- Blue Cross Blue Shield Blue Essentials / Blue Essentials Access (Intercambio)\n"
        "- Blue Cross Blue Shield PAR Plan\n"
        "- Cigna – Todos los planes\n"
        "- Cigna Behavioral Health\n"
        "- Coventry (SPHN)\n"
        "- Dell Children’s Health Plan STAR / CHIP\n"
        "- EHN / WEB TPA (Whole Foods)\n"
        "- First Care Access PPO Network (SPHN)\n"
        "- First Health (SPHN)\n"
        "- FirstCare HMO (SPHN) (Referencia requerida)\n"
        "- Galaxy (SPHN)\n"
        "- Health Payors Organization (SPHN)\n"
        "- HealthSmart (SPHN)\n"
        "- Humana HMOx\n"
        "- Humana Medicare Advantage (excepto Humana Gold Plus)\n"
        "- Humana PPO / HMO / Choice Care (Referencia requerida)\n"
        "- Integrated Medical Systems PPO (SPHN)\n"
        "- Medicaid / TMHP (No aceptado en la clínica sin cita)\n"
        "- Medicare Parte B (Servicio tradicional – Novitas)\n"
        "- Multiplan (SPHN) (PHCS fuera de red)\n"
        "- Optum\n"
        "- Oscar Healthcare (SPHN)\n"
        "- Seton Health Plan\n"
        "- SmartHealth\n"
        "- Superior Health Plan STAR / CHIP / STAR Kids\n"
        "- UnitedHealthcare AARP PPO\n"
        "- UnitedHealthcare All Savers / Choice / Choice Plus / PPO / HMO (Referencia requerida)\n"
        "- UnitedHealthcare Community Plan – Medicaid\n"
        "- UnitedHealthcare Dual Complete Focus HMO\n"
        "- UnitedHealthcare Medicare\n"
        "- UnitedHealthcare One\n"
        "- United Student Resources PPO (SPHN)\n"
        "- USA Managed Care (SPHN)\n\n"
        "Si no ve su plan en la lista, llame al 1-833-UT-CARES para confirmar cobertura."
         )
    },


    # ================= PATIENT PORTAL =================
    {
        "triggers": ["patient portal", "portal", "mychart", "messages", "login"],
        "en": "Access the patient portal here: https://pxppapp.px.athena.io/login",
        "es": "Acceda al portal del paciente aquí: https://pxppapp.px.athena.io/login"
    },

    # ================= CARE TEAM =================
    {
        "triggers": ["care team", "doctors", "providers", "neurologists", "who works here"],
        "en": "View the Mulva Clinic for the Neurosciences care team here: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/care-team",
        "es": "Puede ver el equipo de atención de la Clínica de Neurociencias aquí: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/care-team"
    },

    # ================= CONDITIONS =================
    {
        "triggers": ["conditions", "what do you treat", "neurological conditions", "memory clinic"],
        "en": "A full list of conditions treated is available here: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/conditions",
        "es": "La lista completa de condiciones tratadas está disponible aquí: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/conditions"
    },

    # ================= SERVICES =================
    {
        "triggers": ["services", "clinic services", "what services do you provide"],
        "en": "View services offered here: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/services",
        "es": "Puede ver los servicios ofrecidos aquí: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/services"
    },

    {
        "triggers": [
            "memory center",
            "comprehensive memory center",
            "memory clinic",
            "memory program"],
        "en": "Learn about the Comprehensive Memory Center here: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/cognitive-disorders",
        "es": "Obtenga información sobre el Centro Integral de Memoria aquí: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/cognitive-disorders"
    },


    # ================= SPECIALTIES =================
    {
        "triggers": ["specialties", "specialty care", "neurology specialties"],
        "en": "Clinic specialties are listed here: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/specialties",
        "es": "Las especialidades de la clínica están listadas aquí: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/specialties"
    },

    # ================= BLOG =================
    {
        "triggers": ["blog", "news", "articles", "education", "learn more"],
        "en": "Read neuroscience blog posts here: https://uthealthaustin.org/allblogs?category_slug=neurosciences",
        "es": "Lea artículos del blog de neurociencias aquí: https://uthealthaustin.org/allblogs?category_slug=neurosciences"
    },

    # ================= VIRTUAL TOUR =================
    {
        "triggers": ["virtual tour", "clinic tour", "see the clinic", "what does it look like"],
        "en": "Take a virtual tour of the clinic here: https://www.youtube.com/watch?v=IOJPMvBffbQ",
        "es": "Puede ver un recorrido virtual de la clínica aquí: https://www.youtube.com/watch?v=IOJPMvBffbQ"
    },

    # ================= MEMORY CONDITIONS =================
    {
        "triggers": ["alzheimer", "alzheimers", "memory loss alzheimers"],
        "en": "Learn about Alzheimer’s disease care here: https://uthealthaustin.org/conditions/alzheimers-disease",
        "es": "Información sobre la enfermedad de Alzheimer aquí: https://uthealthaustin.org/conditions/alzheimers-disease"
    },

    {
        "triggers": ["dementia", "memory disease", "cognitive decline"],
        "en": "Learn about dementia care here: https://uthealthaustin.org/conditions/dementia",
        "es": "Información sobre la demencia aquí: https://uthealthaustin.org/conditions/dementia"
    },

    {
        "triggers": ["frontotemporal dementia", "ftd"],
        "en": "Frontotemporal dementia information: https://uthealthaustin.org/conditions/frontotemporal-lobar-degeneration",
        "es": "Información sobre demencia frontotemporal: https://uthealthaustin.org/conditions/frontotemporal-lobar-degeneration"
    },

    {
        "triggers": ["lewy body dementia", "lbd"],
        "en": "Lewy body dementia care: https://uthealthaustin.org/conditions/lewy-body-dementia",
        "es": "Información sobre demencia con cuerpos de Lewy: https://uthealthaustin.org/conditions/lewy-body-dementia"
    },

    {
        "triggers": ["mci", "mild cognitive impairment"],
        "en": "Mild cognitive impairment info: https://uthealthaustin.org/conditions/mild-cognitive-impairment",
        "es": "Información sobre deterioro cognitivo leve: https://uthealthaustin.org/conditions/mild-cognitive-impairment"
    },

    {
        "triggers": ["primary progressive aphasia", "ppa", "language loss"],
        "en": "Primary progressive aphasia info: https://uthealthaustin.org/conditions/primary-progressive-aphasia",
        "es": "Información sobre afasia progresiva primaria: https://uthealthaustin.org/conditions/primary-progressive-aphasia"
    },

    {
        "triggers": ["vascular dementia", "stroke dementia"],
        "en": "Vascular dementia info: https://uthealthaustin.org/conditions/vascular-dementia",
        "es": "Información sobre demencia vascular: https://uthealthaustin.org/conditions/vascular-dementia"
    },

    # ================= CAREGIVER SUPPORT =================
    {
        "triggers": ["caregiver support", "caregiver help", "support for family"],
        "en": "Dementia caregiver support services: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/cognitive-disorders/dementia-caregiver-support",
        "es": "Servicios de apoyo para cuidadores: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/cognitive-disorders/dementia-caregiver-support"
    },

    # ================= FAMILY RESOURCES =================
    {
        "triggers": ["treatment approach", "approach to care", "how dementia is treated"],
        "en": "Learn about the clinic’s approach to dementia care: https://uthealthaustin.org/blog/alzheimers-innovators-in-aging-video",
        "es": "Aprenda sobre el enfoque de atención para demencia: https://uthealthaustin.org/blog/alzheimers-innovators-in-aging-video"
    },

    {
        "triggers": ["caregiver stress", "burnout", "warning signs"],
        "en": "Caregiver stress warning signs: https://uthealthaustin.org/blog/caring-for-caregivers",
        "es": "Señales de estrés del cuidador: https://uthealthaustin.org/blog/caring-for-caregivers"
    },

    {
        "triggers": ["faq", "frequently asked questions", "questions"],
        "en": "Frequently asked questions: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/cognitive-disorders/faqs",
        "es": "Preguntas frecuentes: https://uthealthaustin.org/clinics/mulva-clinic-for-the-neurosciences/cognitive-disorders/faqs"
    },

    {
        "triggers": ["hearing evaluation", "hearing loss", "hearing test"],
        "en": "Hearing evaluation recommendation: https://stmdscuthprdcraft.blob.core.windows.net/stblcmdscuthprdcraft/downloads/UTHA-Mulva_Hearing-loss.pdf",
        "es": "Recomendación de evaluación auditiva: https://stmdscuthprdcraft.blob.core.windows.net/stblcmdscuthprdcraft/downloads/UTHA-Mulva_Hearing-loss.pdf"
    },

    {
        "triggers": ["speech therapy", "language therapy", "speech pathologist"],
        "en": "Speech and language therapy info: https://uthealthaustin.org/blog/speech-language-pathology",
        "es": "Información sobre terapia del habla y lenguaje: https://uthealthaustin.org/blog/speech-language-pathology"
    }
]

MEDICAL_KEYWORDS = [
    "stroke", "seizure", "alzheimer", "alzheimers", "dementia",
    "memory", "brain", "symptom", "diagnosis", "treatment",
    "medication", "disease", "condition"
]


# =============================
# Router
# =============================
def keyword_router(text, lang):
    t = (text or "").lower()
    for item in FAQ:
        if any(trig in t for trig in item["triggers"]):
            return pick(lang, item["en"], item["es"])
    return None

# =============================
# Ask Endpoint (NO GATE)
# =============================
@app.post("/ask")
async def ask(q: Query):

    # detect medical questions
    is_medical = any(
        word in q.question.lower()
        for word in MEDICAL_KEYWORDS
)

    # 1️⃣ Hardcoded admin first
    routed = keyword_router(q.question, q.language)
    if routed:
        return {"answer": routed}

    # 2️⃣ LLM fallback
    if is_medical:
        system_prompt = pick(
            q.language,
            "You are a neurology clinic educational assistant for a demo. "
            "Before answering, include a brief disclaimer that you are not providing medical advice. "
            "Then provide a high-level, general educational explanation only. "
            "Do not give diagnosis, treatment, or personal guidance. "
            "End by encouraging the user to contact the clinic.",
            "Eres un asistente educativo de neurología para una demostración. "
            "Antes de responder, incluye un aviso de que no das consejos médicos. "
            "Luego da una explicación general. "
            "No des diagnósticos ni tratamientos. "
            "Termina recomendando contactar a la clínica."
        )
    else:
        system_prompt = pick(
            q.language,
            "You are a neurology clinic logistics assistant. Provide non-medical, administrative information only.",
            "Eres un asistente de logística de una clínica de neurología. Proporciona solo información administrativa."
        )

    # 3️⃣ ACTUAL OpenAI CALL (this was missing)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": q.question}
        ],
        temperature=0.2
    )

    return {"answer": response.choices[0].message.content.strip()}