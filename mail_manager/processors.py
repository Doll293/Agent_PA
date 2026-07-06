import json
import logging
from datetime import date

from mail_manager.config import settings

logger = logging.getLogger(__name__)

CATEGORIES = [
    "tech",
    "mode",
    "voyage",
    "food",
    "maison",
    "sport",
    "culture",
    "services",
    "autre",
]

_CLIENT = None

SYSTEM_PROMPT = (
    "Tu es un assistant qui analyse des emails promotionnels anonymises. "
    "Tu reponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans markdown."
)

DEFAULT_ANALYSIS = {
    "category": "autre",
    "summary": "Resume indisponible.",
    "relevance_score": 0,
    "promo_code": "",
    "expiry_date": "",
    "is_fake_promo": False,
}


def _get_client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY manquant dans le fichier .env. "
            "Cree une cle gratuite sur https://console.groq.com/keys"
        )
    from groq import Groq

    _CLIENT = Groq(api_key=settings.groq_api_key)
    return _CLIENT


def _build_prompt(mails: list[dict[str, str]], preferences: str) -> str:
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
    preferences_text = preferences.strip() or "aucune preference exprimee"

    return f"""Date du jour : {today}
Envies de l'utilisateur : {preferences_text}

Analyse chacun des mails promotionnels ci-dessous et retourne un objet JSON de la forme :
{{
  "mails": [
    {{
      "index": 0,
      "category": "une valeur parmi {json.dumps(CATEGORIES)}",
      "summary": "resume de l'offre en 1 ou 2 phrases en francais",
      "relevance_score": 0 a 10 selon la correspondance avec les envies de l'utilisateur (0 si aucune preference exprimee ne correspond, 5 si preference absente),
      "promo_code": "code promo exact trouve dans le mail, sinon chaine vide",
      "expiry_date": "date de fin de l'offre au format YYYY-MM-DD si mentionnee, sinon chaine vide",
      "is_fake_promo": true si l'offre semble etre une promo permanente ou trompeuse, sinon false
    }}
  ]
}}

Regles :
- un objet par mail, dans l'ordre, avec le bon index
- convertis les dates relatives ("jusqu'a dimanche", "encore 48h") en date absolue a partir de la date du jour
- ne recopie jamais de donnees personnelles dans le resume

{mails_text}"""


def _sanitize_analysis(raw: dict) -> dict:
    result = dict(DEFAULT_ANALYSIS)
    if not isinstance(raw, dict):
        return result

    category = str(raw.get("category", "")).strip().lower()
    result["category"] = category if category in CATEGORIES else "autre"

    result["summary"] = str(raw.get("summary", "")).strip() or DEFAULT_ANALYSIS["summary"]

    try:
        score = int(raw.get("relevance_score", 0))
    except (TypeError, ValueError):
        score = 0
    result["relevance_score"] = max(0, min(10, score))

    result["promo_code"] = str(raw.get("promo_code", "")).strip()
    result["expiry_date"] = str(raw.get("expiry_date", "")).strip()
    result["is_fake_promo"] = bool(raw.get("is_fake_promo", False))
    return result


def analyze_mails_batch(mails: list[dict[str, str]], preferences: str) -> list[dict]:
    """Analyse tout le lot de mails anonymises en UN SEUL appel LLM.

    `mails` : liste de dicts avec les cles sender/subject/snippet/body (anonymises).
    Retourne une liste d'analyses alignee sur l'ordre d'entree.
    """
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

    # Realigne par index, avec valeurs par defaut si un mail manque.
    by_index: dict[int, dict] = {}
    for item in raw_items:
        if isinstance(item, dict) and isinstance(item.get("index"), int):
            by_index[item["index"]] = item

    return [_sanitize_analysis(by_index.get(i, {})) for i in range(len(mails))]
