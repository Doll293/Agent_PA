import json
import logging
from datetime import date

from mail_manager.config import settings

logger = logging.getLogger(__name__)

PROMO_CATEGORIES = ["mode", "voyage", "food", "maison", "sport", "culture", "services", "tech", "beaute", "loisirs"]
ALL_CATEGORIES = PROMO_CATEGORIES + ["autre", "non-promo"]

_CLIENT = None

SYSTEM_PROMPT = (
    "Tu es un assistant specialise dans l'analyse d'emails promotionnels. "
    "Tu reponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans markdown."
)

DEFAULT_ANALYSIS = {
    "is_promo": False,
    "company": "",
    "category": "autre",
    "summary": "",
    "promo_code": "",
    "expiry_date": "",
    "discount": "",
    "is_fake_promo": False,
}


def _get_client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY manquant dans le fichier .env.")
    from groq import Groq
    _CLIENT = Groq(api_key=settings.groq_api_key)
    return _CLIENT


def _build_prompt(mails: list, preferences: str) -> str:
    today = date.today().isoformat()
    mail_blocks = []
    for i, mail in enumerate(mails):
        mail_blocks.append(
            f"--- MAIL {i} ---\n"
            f"Expediteur: {mail['sender']}\n"
            f"Sujet: {mail['subject']}\n"
            f"Contenu: {mail['body'] or mail['snippet']}"
        )
    mails_text = "\n\n".join(mail_blocks)
    preferences_text = preferences.strip() or "aucune preference"

    return f"""Date du jour : {today}
Envies de l'utilisateur : {preferences_text}

Analyse chaque mail et retourne un JSON :
{{
  "mails": [
    {{
      "index": 0,
      "is_promo": true si c'est une offre promotionnelle (reduction, code promo, soldes, offre speciale), sinon false,
      "company": "nom de l'entreprise ou de la marque qui envoie la promo",
      "category": "une valeur parmi {json.dumps(ALL_CATEGORIES)}",
      "summary": "description courte de la promo en 1 phrase en francais (ex: -30% sur toute la collection ete)",
      "promo_code": "code promo exact si present, sinon chaine vide",
      "expiry_date": "date de fin au format YYYY-MM-DD si mentionnee, sinon chaine vide",
      "discount": "montant ou pourcentage de reduction si mentionne (ex: -20%, 5€ offerts), sinon chaine vide",
      "is_fake_promo": true si la promo semble permanente ou trompeuse
    }}
  ]
}}

Regles :
- un objet par mail dans l'ordre avec le bon index
- convertis les dates relatives en date absolue depuis la date du jour
- si ce n'est pas une promo (newsletter, confirmation commande, etc.), mets is_promo: false

{mails_text}"""


def _sanitize(raw: dict) -> dict:
    result = dict(DEFAULT_ANALYSIS)
    if not isinstance(raw, dict):
        return result
    result["is_promo"] = bool(raw.get("is_promo", False))
    result["company"] = str(raw.get("company", "")).strip()
    category = str(raw.get("category", "")).strip().lower()
    result["category"] = category if category in ALL_CATEGORIES else "autre"
    result["summary"] = str(raw.get("summary", "")).strip()
    result["promo_code"] = str(raw.get("promo_code", "")).strip()
    result["expiry_date"] = str(raw.get("expiry_date", "")).strip()
    result["discount"] = str(raw.get("discount", "")).strip()
    result["is_fake_promo"] = bool(raw.get("is_fake_promo", False))
    return result


def analyze_mails_batch(mails: list, preferences: str) -> list:
    if not mails:
        return []

    client = _get_client()
    logger.info("Analyzing %s mails with Groq model %s", len(mails), settings.groq_model)

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(mails, preferences)},
            ],
        )
        content = response.choices[0].message.content or "{}"
    except Exception as exc:
        logger.exception("Groq API call failed.")
        raise RuntimeError(f"L'appel au LLM Groq a echoue : {exc}") from exc

    try:
        parsed = json.loads(content)
        raw_items = parsed.get("mails", [])
    except json.JSONDecodeError:
        logger.error("Groq returned invalid JSON: %s", content[:500])
        raw_items = []

    by_index = {}
    for item in raw_items:
        if isinstance(item, dict) and isinstance(item.get("index"), int):
            by_index[item["index"]] = item

    return [_sanitize(by_index.get(i, {})) for i in range(len(mails))]
