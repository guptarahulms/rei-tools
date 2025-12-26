"""
Test script for Email Service

Run this file directly to send a test email with "Hello" message.
Usage: python test_email.py
"""

import sys
import logging
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from property_report.config_manager import ConfigManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def send_test_email(
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    sender_password: str,
    recipient_emails: list[str],
    message: str = "Hello"
) -> bool:
    """
    Send a simple test email.
    
    Args:
        smtp_server: SMTP server hostname.
        smtp_port: SMTP server port.
        sender_email: Email address to send from.
        sender_password: Password or app password for sender.
        recipient_emails: List of recipient email addresses.
        message: The message to send (default: "Hello").
        
    Returns:
        True if email was sent successfully.
    """
    subject = f"Test Email - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Create the email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipient_emails)
    
    # Plain text version
    plain_text = message
    
    # Simple HTML version
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Test Email</h1>
    <p>{message}</p>
    <p><small>Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
</body>
</html>
"""
    
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))
    
    logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}")
    
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_emails, msg.as_string())
    
    logger.info(f"Test email sent successfully to {recipient_emails}")
    return True


def main():
    """Main function to run the test."""
    print("=" * 50)
    print("Email Service Test")
    print("=" * 50)
    
    try:
        # Load config
        config_manager = ConfigManager()
        email_config = config_manager.get_email_config()
        
        print(f"SMTP Server: {email_config.smtp_server}:{email_config.smtp_port}")
        print(f"Sender: {email_config.sender_email}")
        print(f"Recipients: {email_config.recipient_emails}")
        print("=" * 50)
        
        # Send test email
        print("\nSending test email with message: 'Hello'...")
        
        send_test_email(
            smtp_server=email_config.smtp_server,
            smtp_port=email_config.smtp_port,
            sender_email=email_config.sender_email,
            sender_password=email_config.sender_password,
            recipient_emails=email_config.recipient_emails,
            message="Hello"
        )
        
        print("\n✅ Test email sent successfully!")
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ SMTP Authentication Error: {e}")
        print("Tip: For Gmail, make sure you're using an App Password, not your regular password.")
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"\n❌ SMTP Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
