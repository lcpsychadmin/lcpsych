import os
from django.core.mail.backends.base import BaseEmailBackend
from azure.communication.email import EmailClient


class AzureCommunicationEmailBackend(BaseEmailBackend):
    """Send email via Azure Communication Services Email."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        conn = os.getenv("ACS_EMAIL_CONNECTION_STRING")
        if not conn:
            raise RuntimeError("ACS_EMAIL_CONNECTION_STRING is not set")
        self.sender = os.getenv("ACS_EMAIL_SENDER")
        if not self.sender:
            raise RuntimeError("ACS_EMAIL_SENDER is not set")
        self.client = EmailClient.from_connection_string(conn)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            to_list = [{"address": addr} for addr in message.to]
            payload = {
                "senderAddress": self.sender,
                "recipients": {"to": to_list},
                "content": {
                    "subject": message.subject,
                    "plainText": message.body,
                },
            }
            # Use first HTML alternative if provided
            if message.alternatives:
                html_parts = [body for body, mimetype in message.alternatives if mimetype == "text/html"]
                if html_parts:
                    payload["content"]["html"] = html_parts[0]

            # Begin send and wait for completion to ensure delivery attempt
            poller = self.client.begin_send(payload)
            poller.wait()
            sent += 1
        return sent
