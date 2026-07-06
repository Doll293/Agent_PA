from mail_manager.privacy import anonymize_mail
from mail_manager.processors import analyze_mails_batch


class Workflow:
    def run_for_batch(self, emails: list[dict[str, str]], preferences: str = "") -> list[dict]:
        if not emails:
            return []

        anonymized_list = [
            anonymize_mail(
                subject=e.get("subject", ""),
                snippet=e.get("snippet", ""),
                sender=e.get("from", ""),
                body=e.get("body_text", ""),
            )
            for e in emails
        ]

        analyses = analyze_mails_batch(anonymized_list, preferences)

        return [
            {
                **email,
                "anonymized_sender": anon["sender"],
                "anonymized_subject": anon["subject"],
                "anonymized_snippet": anon["snippet"],
                **analysis,
            }
            for email, anon, analysis in zip(emails, anonymized_list, analyses)
        ]
