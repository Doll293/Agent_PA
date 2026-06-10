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
    "urgent": "action requise immediatement, deadline aujourd'hui, alerte critique",
    "important": "securite du compte, code de verification, connexion suspecte, mot de passe",
    "administratif": "facture, contrat, document officiel, paiement, administration",
    "ecole": "cours, devoir, examen, universite, professeur, projet scolaire",
    "personnel": "message d'un ami ou de la famille, invitation, anniversaire, reseaux sociaux",
    "faible priorite": "newsletter, publicite, promotion, notification automatique",
}

CLASSIFIER = None
_CLASSIFIER_LOAD_FAILED = False


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
    global CLASSIFIER, _CLASSIFIER_LOAD_FAILED

    if CLASSIFIER is not None:
        return CLASSIFIER
    if _CLASSIFIER_LOAD_FAILED:
        return None

    try:
        from transformers import pipeline

        logger.info("Loading transformers model: %s", settings.transformers_model)
        CLASSIFIER = pipeline("zero-shot-classification", model=settings.transformers_model)
        return CLASSIFIER
    except Exception:
        _CLASSIFIER_LOAD_FAILED = True
        logger.exception("Unable to load transformers classifier; local rules will be used.")
        return None


def _label_to_category(best_label: str, subject: str, snippet: str) -> str:
    for category, label in CATEGORY_LABELS.items():
        if best_label == label:
            return category
    logger.warning("Unknown transformers label: %s", best_label)
    return classify_with_rules(subject, snippet)


def classify_mail(subject: str, snippet: str, use_model: bool = True) -> str:
    return classify_mails_batch([(subject, snippet)], use_model=use_model)[0]


def classify_mails_batch(pairs: list[tuple[str, str]], use_model: bool = True) -> list[str]:
    if not use_model:
        return [classify_with_rules(s, sn) for s, sn in pairs]

    classifier = load_classifier()
    if classifier is None:
        return [classify_with_rules(s, sn) for s, sn in pairs]

    texts = [f"Sujet: {s[:160]}\nExtrait: {sn[:320]}" for s, sn in pairs]
    try:
        results = classifier(
            texts,
            candidate_labels=list(CATEGORY_LABELS.values()),
            hypothesis_template="Ce mail est {}.",
        )
    except Exception:
        logger.exception("Transformers batch classification failed; local rules will be used.")
        return [classify_with_rules(s, sn) for s, sn in pairs]

    if isinstance(results, dict):
        results = [results]

    categories = []
    for result, (subject, snippet) in zip(results, pairs):
        labels = result.get("labels") or []
        if not labels:
            categories.append(classify_with_rules(subject, snippet))
        else:
            categories.append(_label_to_category(labels[0], subject, snippet))
    return categories
