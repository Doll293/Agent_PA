from mail_manager.privacy import anonymize_mail
from mail_manager.processors import classify_mails_batch, suggest_action


class Workflow:
    def run_for_batch(self, emails: list[dict[str, str]], use_model: bool = True) -> list[dict[str, str]]:
        anonymized_list = [
            anonymize_mail(e.get("subject", ""), e.get("snippet", ""))
            for e in emails
        ]
        pairs = [(a["subject"], a["snippet"]) for a in anonymized_list]
        categories = classify_mails_batch(pairs, use_model=use_model)

        return [
            {
                **email,
                "anonymized_subject": anon["subject"],
                "anonymized_snippet": anon["snippet"],
                "category": category,
                "suggestion": suggest_action(category),
            }
            for email, anon, category in zip(emails, anonymized_list, categories)
        ]
