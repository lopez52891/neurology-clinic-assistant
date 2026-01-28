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

    return {"answer": response.choices[0].message.content.strip()}
