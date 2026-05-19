import logging

from mail_manager.config import settings

logger = logging.getLogger(__name__)

CATEGORIES = [
    "urgent",
    "important",
    "administratif",
    "ecole",
    "personnel",
    "faible priorite",
]

CATEGORY_LABELS = {
    "urgent": "urgent, action immediate ou deadline proche",
    "important": "important, securite, verification, connexion, code ou compte",
    "administratif": "administratif, facture, document, contrat, paiement ou service",
    "ecole": "ecole, cours, devoir, projet, universite ou examen",
    "personnel": "personnel, famille, amis, reseaux sociaux ou vie privee",
    "faible priorite": "faible priorite, newsletter, publicite, information mineure ou rappel leger",
}

CLASSIFIER = None


def suggest_action(category: str) -> str:
    if category == "urgent":
        return "lire maintenant"
    if category in {"important", "administratif", "ecole"}:
        return "verifier manuellement"
    if category == "personnel":
        return "repondre plus tard"
    return "ignorer pour le moment"


def classify_with_rules(subject: str, snippet: str) -> str:
    text = f"{subject} {snippet}".lower()

    if any(word in text for word in ["code", "connexion", "security", "securite", "verification", "verify"]):
        return "important"
    if any(word in text for word in ["urgent", "asap", "immediat", "deadline", "alerte"]):
        return "urgent"
    if any(word in text for word in ["facture", "document", "contrat", "administration", "impot", "paiement"]):
        return "administratif"
    if any(word in text for word in ["cours", "projet", "prof", "universite", "ecole", "examen", "devoir"]):
        return "ecole"
    if any(word in text for word in ["famille", "ami", "anniversaire", "instagram", "facebook"]):
        return "personnel"
    if any(word in text for word in ["important", "confirmation", "rappel", "stockage", "gmail"]):
        return "important"
    return "faible priorite"


def load_classifier():
    global CLASSIFIER

    if CLASSIFIER is not None:
        return CLASSIFIER

    try:
        from transformers import pipeline

        logger.info("Loading transformers model: %s", settings.transformers_model)
        CLASSIFIER = pipeline("zero-shot-classification", model=settings.transformers_model)
        return CLASSIFIER
    except Exception:
        logger.exception("Unable to load transformers classifier; local rules will be used.")
        return None


def classify_mail(subject: str, snippet: str, use_model: bool = True) -> str:
    if not use_model:
        return classify_with_rules(subject, snippet)
    classifier = load_classifier()
    if classifier is None:
        return classify_with_rules(subject, snippet)

    text = f"Sujet: {subject[:160]}\nExtrait: {snippet[:320]}"
    try:
        result = classifier(
            text,
            candidate_labels=list(CATEGORY_LABELS.values()),
            hypothesis_template="Ce mail est {}.",
        )
    except Exception:
        logger.exception("Transformers classification failed; local rules will be used.")
        return classify_with_rules(subject, snippet)

    labels = result.get("labels") or []
    if not labels:
        return classify_with_rules(subject, snippet)

    best_label = labels[0]
    for category, label in CATEGORY_LABELS.items():
        if best_label == label:
            return category

    logger.warning("Unknown transformers label: %s", best_label)
    return classify_with_rules(subject, snippet)
