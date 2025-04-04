import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()
def send_email(subject, body, recipients):
    """Generate and send an email to multiple recipients."""
    
    # Fetching credentials from environment variables
    sender_email = os.getenv('EMAIL_ADDRESS')
    sender_password = os.getenv('EMAIL_PASSWORD')

    # Set up the MIME
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['Subject'] = subject
    
    # Attach the body with the msg instance
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)

        for recipient in recipients:
            try:
                msg['To'] = recipient
                text = msg.as_string()
                server.sendmail(sender_email, recipient, text)
                print(f"Email sent successfully to {recipient}")
            except Exception as e:
                print(f"Failed to send email to {recipient}. Error: {e}")
        
        server.quit()

    except Exception as e:
        print(f"Failed to connect to the email server. Error: {e}")

# Example usage:
# recipients_list = ["nopenah100@gmail.com"]
# send_email("Watchdog Alert", "Your microservice is down!", recipients_list)
