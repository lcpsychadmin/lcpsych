from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = "Send a test email using the configured Django email settings."

    def add_arguments(self, parser):
        parser.add_argument("to", nargs=1, help="Recipient email address")
        parser.add_argument(
            "--subject",
            default="L+C Psych email configuration test",
            help="Subject line for the test email",
        )
        parser.add_argument(
            "--body",
            default=(
                "This is a test message sent by Django using your current EMAIL_* settings.\n\n"
                "If you received this, SMTP is working."
            ),
            help="Body for the test email",
        )

    def handle(self, *args, **options):
        to = options["to"][0]
        subject = options["subject"]
        body = options["body"]
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "webmaster@localhost"
        self.stdout.write(
            self.style.NOTICE(
                f"Sending test email to {to} via {getattr(settings, 'EMAIL_HOST', 'unknown host')}:{getattr(settings, 'EMAIL_PORT', 'unknown')}"
            )
        )
        try:
            sent = send_mail(subject, body, from_email, [to], fail_silently=False)
        except Exception as e:
            raise CommandError(f"Failed to send email: {e}")

        if sent:
            self.stdout.write(self.style.SUCCESS("Email sent successfully."))
        else:
            raise CommandError("send_mail returned 0 (no messages sent)")
