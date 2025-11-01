"""
Email notification service for DCA Bot SaaS
Sends password reset emails, welcome emails, etc.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Email service using SMTP"""

    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_username)
        self.from_name = os.getenv('FROM_NAME', 'DCA Bot SaaS')

        self.enabled = bool(self.smtp_username and self.smtp_password)

        if not self.enabled:
            logger.warning("Email service disabled: SMTP credentials not configured")
        else:
            logger.info(f"Email service enabled: {self.from_email}")

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
        """
        Send an email

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML version of email body
            text_body: Plain text version (optional, will strip HTML if not provided)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email not sent (service disabled): {subject} to {to_email}")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add plain text version
            if text_body:
                part1 = MIMEText(text_body, 'plain')
                msg.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_body, 'html')
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully: {subject} to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_password_reset_email(self, to_email: str, reset_link: str, expires_minutes: int = 60) -> bool:
        """
        Send password reset email

        Args:
            to_email: User's email address
            reset_link: Full URL to reset password page
            expires_minutes: Token expiration time in minutes

        Returns:
            True if sent successfully
        """
        subject = "Reset Your Password - DCA Bot SaaS"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background-color: #0B0E11;
            color: #EAECEF;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: #1E2329;
            border-radius: 12px;
            border: 1px solid #2B3139;
            padding: 40px;
        }}
        .logo {{
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, #0ECB81, #F0B90B);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 24px;
        }}
        h1 {{
            color: #EAECEF;
            font-size: 24px;
            margin-bottom: 16px;
        }}
        p {{
            color: #848E9C;
            line-height: 1.6;
            margin-bottom: 16px;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #0ECB81, #10d98d);
            color: #1E2329;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 24px 0;
        }}
        .warning {{
            background: rgba(246, 70, 93, 0.1);
            border: 1px solid rgba(246, 70, 93, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
            margin-top: 24px;
            color: #F6465D;
        }}
        .footer {{
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid #2B3139;
            color: #5E6673;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🤖 DCA Bot</div>

        <h1>Reset Your Password</h1>

        <p>We received a request to reset your password for your DCA Bot SaaS account.</p>

        <p>Click the button below to reset your password:</p>

        <a href="{reset_link}" class="button">Reset Password</a>

        <p>This link will expire in {expires_minutes} minutes.</p>

        <div class="warning">
            <strong>⚠️ Security Notice:</strong> If you didn't request this password reset, please ignore this email. Your password will remain unchanged.
        </div>

        <p>If the button doesn't work, copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #0ECB81;">{reset_link}</p>

        <div class="footer">
            <p>This is an automated email from DCA Bot SaaS. Please do not reply to this email.</p>
            <p>&copy; 2025 DCA Bot SaaS. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """

        text_body = f"""
DCA Bot SaaS - Reset Your Password

We received a request to reset your password for your DCA Bot SaaS account.

Click this link to reset your password:
{reset_link}

This link will expire in {expires_minutes} minutes.

If you didn't request this password reset, please ignore this email. Your password will remain unchanged.

---
This is an automated email from DCA Bot SaaS. Please do not reply.
© 2025 DCA Bot SaaS. All rights reserved.
        """

        return self.send_email(to_email, subject, html_body, text_body)


# Global email service instance
email_service = EmailService()
