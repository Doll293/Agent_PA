from mail_manager.privacy import anonymize_mail
from mail_manager.processors import classify_mail, suggest_action


class Workflow:
    def run_for_mail(self, email_data: dict[str, str]) -> dict[str, str]:
        anonymized = anonymize_mail(
            email_data.get("subject", ""),
            email_data.get("snippet", ""),
        )
        category = classify_mail(anonymized["subject"], anonymized["snippet"])
        suggestion = suggest_action(category)

        return {
            **email_data,
            "anonymized_subject": anonymized["subject"],
            "anonymized_snippet": anonymized["snippet"],
            "category": category,
            "suggestion": suggestion,
        }
