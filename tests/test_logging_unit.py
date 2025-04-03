import logging
import time
import boto3
import os
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
load_dotenv()

# AWS cloudwatch setup
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
print(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)

LOG_GROUP = "watchdog_log_group"
SERVICE_HEALTH_STREAM = "service_health_logs"
SUBSCRIPTION_STREAM = "subscription_logs"

# Initialize CloudWatch client
cloudwatch_client = boto3.client(
    'logs',
    region_name=AWS_DEFAULT_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Create CloudWatch Log Group and Log Stream if they do not exist
def create_log_group_and_stream():
    try:
        cloudwatch_client.create_log_group(logGroupName=LOG_GROUP)
    except cloudwatch_client.exceptions.ResourceAlreadyExistsException:
        pass  # Log group already exists

    try:
        cloudwatch_client.create_log_stream(logGroupName=LOG_GROUP, logStreamName=SERVICE_HEALTH_STREAM)
    except cloudwatch_client.exceptions.ResourceAlreadyExistsException:
        pass  # Log stream already exists

    try:
        cloudwatch_client.create_log_stream(logGroupName=LOG_GROUP, logStreamName=SUBSCRIPTION_STREAM)
    except cloudwatch_client.exceptions.ResourceAlreadyExistsException:
        pass  # Log stream already exists

create_log_group_and_stream()

# Create a custom CloudWatch logging handler
class CloudWatchLoggingHandler(logging.Handler):
    def __init__(self, stream_name):
        super().__init__()
        self.log_stream_name = stream_name

    def emit(self, record):
        log_entry = self.format(record)
        timestamp = int(time.time() * 1000)  # Current time in milliseconds

        log_event = {
            'message': log_entry,
            'timestamp': timestamp
        }

        # Send log event to CloudWatch
        try:
            cloudwatch_client.put_log_events(
                logGroupName=LOG_GROUP,
                logStreamName=self.log_stream_name,
                logEvents=[log_event]
            )
        except Exception as e:
            logging.error(f"Failed to send log to CloudWatch: {e}")

# Function to switch to the appropriate log stream
def switch_log_stream(stream_name):
    global cloudwatch_handler
    cloudwatch_handler = CloudWatchLoggingHandler(stream_name)
    cloudwatch_handler.setLevel(logging.INFO)
    cloudwatch_formatter = logging.Formatter('%(asctime)s - %(message)s')
    cloudwatch_handler.setFormatter(cloudwatch_formatter)
    logging.getLogger().handlers = [cloudwatch_handler]

# Set up logging to log only to CloudWatch (removing console and file logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[]  # No local handlers, only CloudWatch
)

# Create the initial CloudWatch handler and set the default log stream to service health logs
switch_log_stream(SERVICE_HEALTH_STREAM)

# Test logging function
def test_logging():
    try:
        # Log an entry to service health log stream
        logging.info("This is a test log to the service health log stream.")

        # Switch to subscription log stream and log an entry
        switch_log_stream(SUBSCRIPTION_STREAM)
        logging.info("This is a test log to the subscription log stream.")

        # Switch back to service health log stream and log another entry
        switch_log_stream(SERVICE_HEALTH_STREAM)
        logging.info("This is another test log to the service health log stream.")

        print("Test logging complete!")
    except Exception as e:
        logging.error(f"Error during logging: {e}")

if __name__ == "__main__":
    test_logging()
