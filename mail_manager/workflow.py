from mail_manager.privacy import anonymize_mail
from mail_manager.processors import classify_mails_batch, suggest_action


class Workflow:
    def run_for_batch(self, emails: list[dict[str, str]]) -> list[dict[str, str]]:
        anonymized_list = [
            anonymize_mail(e.get("subject", ""), e.get("snippet", ""), e.get("from", ""))
            for e in emails
        ]
        pairs = [(f"{a['sender']} | {a['subject']}".strip(" |"), a["snippet"]) for a in anonymized_list]
        categories = classify_mails_batch(pairs)

        return [
            {
                **email,
                "anonymized_sender": anon["sender"],
                "anonymized_subject": anon["subject"],
                "anonymized_snippet": anon["snippet"],
                "category": category,
                "suggestion": suggest_action(category),
            }
            for email, anon, category in zip(emails, anonymized_list, categories)
        ]
