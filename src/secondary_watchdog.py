import threading
import time
import requests
import logging
from flask import Flask, jsonify
from emailer import send_email

# Set up logging to log alerts and monitoring information
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(message)s", 
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('secondary_watchdog.log')  # Log to a file named 'watchdog.log'
    ]
)

# Initialize the Flask app for the secondary watchdog
app = Flask(__name__)

primary_watchdog_status = True  # Track the primary watchdog's status

# Microservices the secondary watchdog will monitor if the primary is down
microservices = [
    {"name": "data_collection", "url": "http://localhost:5001/status", "recipients": [], "prev_status": True},
    {"name": "data_retrival", "url": "http://localhost:5002/status", "recipients": [], "prev_status": True},
    {"name": "data_analytics", "url": "http://localhost:5003/status", "recipients": [], "prev_status": True},
    {"name": "primary", "url": "http://localhost:5003/status", "recipients": [], "prev_status": True},
]

# Flag to control whether microservices should be monitored
monitoring_active = False

# Sends an email alert for microservice status changes
def send_alert(service_name, recipients, alert_type="down"):
    subject = f"ALERT: {service_name} is {alert_type}!"
    body = f"The microservice {service_name} is {alert_type}. Please check the service."
    send_email(subject, body, recipients)

# Check health of a single microservice
def check_service_health(service):
    try:
        response = requests.get(service['url'], timeout=5)
        if response.status_code == 200:
            if service['prev_status'] == False:  # Microservice is back up
                logging.info(f"{service['name']} is back up.")
                send_alert(service['name'], service['recipients'], alert_type="up")
            service['prev_status'] = True
            logging.info(f"{service['name']} is healthy.")
        else:
            if service['prev_status'] == True:  # Microservice is down
                logging.error(f"{service['name']} returned status code {response.status_code}")
                send_alert(service['name'], service['recipients'], alert_type="down")
            service['prev_status'] = False
    except requests.exceptions.RequestException as e:
        if service['prev_status'] == True:  # Microservice is down
            logging.error(f"Error while checking {service['name']}: {e}")
            send_alert(service['name'], service['recipients'], alert_type="down")
        service['prev_status'] = False

# Monitor the primary watchdog's health
def monitor_primary_watchdog():
    global primary_watchdog_status
    try:
        while True:
            response = requests.get('http://localhost:8080/status', timeout=5)
            if response.status_code == 200:
                logging.info("Primary Watchdog is alive.")
                if not primary_watchdog_status:  # If the primary watchdog was down and is now back up
                    logging.info("Primary Watchdog is back up.")
                    primary_watchdog_status = True  # Primary watchdog is back online
                    stop_monitoring_services()  # Stop monitoring microservices
                time.sleep(30)  # Check every 30 seconds
            else:
                logging.error("Primary Watchdog is down.")
                if primary_watchdog_status:
                    logging.info("Taking over responsibilities from Primary Watchdog.")
                    primary_watchdog_status = False  # Mark primary as down
                    start_monitoring_services()  # Start monitoring microservices
                time.sleep(30)  # Check again in 30 seconds
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to reach primary watchdog: {e}")
        if primary_watchdog_status:
            logging.info("Taking over responsibilities from Primary Watchdog.")
            primary_watchdog_status = False  # Mark primary as down
            start_monitoring_services()  # Start monitoring microservices
        time.sleep(30)  # Try again in 30 seconds

# Start threads to monitor the microservices
def start_monitoring_services():
    global monitoring_active
    monitoring_active = True  # Set flag to start monitoring services

    # Start a new thread for each microservice health check
    for service in microservices:            
        thread = threading.Thread(target=check_service_health, args=(service,))
        thread.daemon = True
        thread.start()

# Stop threads for monitoring the microservices
def stop_monitoring_services():
    global monitoring_active
    monitoring_active = False  # Set flag to stop monitoring services
    logging.info("Stopped monitoring services.")

@app.route('/status')
def status():
    return jsonify({"status": "alive", "message": "Secondary Watchdog is running."}), 200

def main():
    # Start the primary watchdog monitoring thread
    monitoring_thread = threading.Thread(target=monitor_primary_watchdog)
    monitoring_thread.daemon = True
    monitoring_thread.start()

    # Run the Flask app for the secondary watchdog
    app.run(host='0.0.0.0', port=8081)  # Secondary watchdog runs on port 8081

if __name__ == "__main__":
    main()
