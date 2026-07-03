import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from database import settings

logger = logging.getLogger(__name__)


def _build_otp_html(name: str, otp_code: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:32px 40px;text-align:center;">
            <h1 style="margin:0;color:#f0a500;font-size:22px;font-weight:700;letter-spacing:0.5px;">
              Atlas Freight Services
            </h1>
            <p style="margin:4px 0 0;color:rgba(255,255,255,0.6);font-size:13px;">
              Your trusted freight partner
            </p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <h2 style="margin:0 0 8px;color:#1a1a2e;font-size:20px;">
              Verify your email address
            </h2>
            <p style="margin:0 0 24px;color:#555;font-size:15px;line-height:1.6;">
              Hi {name}, thanks for signing up! Use the code below to verify your email address.
              This code expires in <strong>10 minutes</strong>.
            </p>

            <!-- OTP Box -->
            <div style="background:#f4f6f9;border:2px dashed #e0e0e0;border-radius:10px;padding:28px;text-align:center;margin:0 0 28px;">
              <p style="margin:0 0 8px;color:#888;font-size:12px;letter-spacing:2px;text-transform:uppercase;">
                Your verification code
              </p>
              <p style="margin:0;color:#1a1a2e;font-size:40px;font-weight:700;letter-spacing:10px;font-family:monospace;">
                {otp_code}
              </p>
            </div>

            <p style="margin:0 0 8px;color:#888;font-size:13px;line-height:1.6;">
              If you didn't create an account, please ignore this email. Your account won't be
              created unless you complete the verification.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f4f6f9;padding:20px 40px;text-align:center;border-top:1px solid #e8e8e8;">
            <p style="margin:0;color:#aaa;font-size:12px;">
              &copy; 2026 Atlas Freight Services &amp; Atlas Freight Services &nbsp;|&nbsp;
              <a href="mailto:info@shippingnibees.com" style="color:#f0a500;text-decoration:none;">
                info@atlasfreight.com
              </a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def send_otp_email(to_email: str, name: str, otp_code: str) -> bool:
    """Send OTP email. Returns True on success, False on failure.
    Falls back to console logging if SMTP is not configured."""

    # Always log to console so dev environments work without SMTP
    logger.info(f"[OTP] Email: {to_email} | Code: {otp_code}")
    print(f"\n{'=' * 50}\nOTP for {to_email}: {otp_code}\n{'=' * 50}\n")

    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP not configured — OTP printed to console only.")
        return True  # Dev mode: treat as success

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Atlas Freight verification code"
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg["To"] = to_email

        text_body = f"Hi {name},\n\nYour verification code is: {otp_code}\n\nIt expires in 10 minutes.\n\nAtlas Freight"
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(_build_otp_html(name, otp_code), "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, to_email, msg.as_string())

        logger.info(f"OTP email sent to {to_email}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {to_email}: {exc}")
        return False
