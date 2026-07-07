from mail_manager.privacy import anonymize_mail
from mail_manager.processors import analyze_mails_batch


class Workflow:
    def __init__(self, preferences: str = ""):
        self.preferences = preferences

    def run_for_batch(self, emails: list) -> list:
        anonymized_list = [
            anonymize_mail(e.get("subject", ""), e.get("snippet", ""), e.get("from", ""))
            for e in emails
        ]

        mails_for_analysis = [
            {
                "sender": a["sender"],
                "subject": a["subject"],
                "snippet": a["snippet"],
                "body": "",
            }
            for a in anonymized_list
        ]

        analyses = analyze_mails_batch(mails_for_analysis, self.preferences)

        return [
            {
                **email,
                "is_promo": analysis["is_promo"],
                "company": analysis["company"],
                "category": analysis["category"],
                "summary": analysis["summary"],
                "promo_code": analysis["promo_code"],
                "expiry_date": analysis["expiry_date"],
                "discount": analysis["discount"],
                "is_fake_promo": analysis["is_fake_promo"],
            }
            for email, anon, analysis in zip(emails, anonymized_list, analyses)
        ]
