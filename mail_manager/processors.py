import logging

from mail_manager.config import settings

logger = logging.getLogger(__name__)

CATEGORIES = [
    "urgent",
    "important",
    "administratif",
    "opportunite pro",
    "ecole",
    "personnel",
    "faible priorite",
]

CATEGORY_LABELS = {
    "urgent": "action requise immediatement, deadline aujourd'hui, alerte critique",
    "important": "securite du compte, code de verification, connexion suspecte, mot de passe",
    "administratif": "facture, contrat, document officiel, paiement, administration",
    "opportunite pro": "offre d'emploi, recrutement, mission freelance, prospection b2b, webinar metier, partenariat entreprise",
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
    if category == "opportunite pro":
        return "evaluer si pertinent pour le travail"
    if category == "personnel":
        return "repondre plus tard"
    return "ignorer pour le moment"


def load_classifier():
    global CLASSIFIER, _CLASSIFIER_LOAD_FAILED

    if CLASSIFIER is not None:
        return CLASSIFIER
    if _CLASSIFIER_LOAD_FAILED:
        raise RuntimeError("Le modele IA est indisponible pour cette session.")

    try:
        from transformers import pipeline

        logger.info("Loading transformers model: %s", settings.transformers_model)
        CLASSIFIER = pipeline("zero-shot-classification", model=settings.transformers_model)
        return CLASSIFIER
    except Exception as exc:
        _CLASSIFIER_LOAD_FAILED = True
        logger.exception("Unable to load transformers classifier.")
        raise RuntimeError(
            "Impossible de charger le modele IA. Verifie les dependances et le telechargement du modele."
        ) from exc


def _label_to_category(best_label: str) -> str:
    for category, label in CATEGORY_LABELS.items():
        if best_label == label:
            return category
    logger.warning("Unknown transformers label: %s", best_label)
    return "faible priorite"


def classify_mail(subject: str, snippet: str) -> str:
    return classify_mails_batch([(subject, snippet)])[0]


def classify_mails_batch(pairs: list[tuple[str, str]]) -> list[str]:
    classifier = load_classifier()
    texts = [f"Sujet: {subject[:160]}\nExtrait: {snippet[:320]}" for subject, snippet in pairs]

    try:
        results = classifier(
            texts,
            candidate_labels=list(CATEGORY_LABELS.values()),
            hypothesis_template="Ce mail est {}.",
        )
    except Exception as exc:
        logger.exception("Transformers batch classification failed.")
        raise RuntimeError("La classification IA a echoue pour ce lot de mails.") from exc

    if isinstance(results, dict):
        results = [results]

    categories = []
    for result in results:
        labels = result.get("labels") or []
        categories.append(_label_to_category(labels[0]) if labels else "faible priorite")
    return categories
