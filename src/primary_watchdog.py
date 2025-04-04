import threading
import time
import requests
import logging
import os
from flask import Flask, request, jsonify
from emailer import send_email
from dotenv import load_dotenv
from db_functions import (
    get_all_microservices,
    update_prev_status,
    update_recipients,
    create_mongo_logger
)

# Load .env file from the parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

# Initialize Flask app
app = Flask(__name__)

# Flag for refreshing microservices list
refresh_flag = False

# Load the microservices at startup
microservices = get_all_microservices()

# Configure MongoDB logging
mongo_logger = create_mongo_logger(log_level=logging.DEBUG)

SLEEP_TIME = 30 if os.getenv("TEST_MODE", "false").lower() == "true" else 300
SERVER_ADDRESS = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
PORT = int(os.getenv("FLASK_RUN_PORT", 5000))

@app.route('/status')
def status():
    # Primary Watchdog status endpoint to report if it's alive
    return jsonify({"status": "alive", "message": "Primary Watchdog is running."}), 200

@app.route('/subscribe', methods=['POST'])
def subscribe():

    global microservices

    data = request.get_json()
    service_name = data.get("service_name")
    gmail_id = data.get("gmail_id")

    service = next((s for s in microservices if s["name"] == service_name), None)

    if not service:
        return jsonify({"error": "Service not found"}), 404

    if gmail_id not in service["recipients"]:
        success = update_recipients(service_name, gmail_id, add=True)
        if success:
            # Refresh our local copy to reflect the update
            microservices = get_all_microservices()
            mongo_logger.info(f"Subscribed {gmail_id} to {service_name}")
            return jsonify({"message": f"Subscribed {gmail_id} to {service_name}"}), 200
        else:
            return jsonify({"error": "Failed to update subscription"}), 500
    else:
        return jsonify({"message": f"{gmail_id} is already subscribed to {service_name}"}), 200

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    global microservices
    data = request.get_json()
    service_name = data.get("service_name")
    gmail_id = data.get("gmail_id")

    service = next((s for s in microservices if s["name"] == service_name), None)

    if not service:
        return jsonify({"error": "Service not found"}), 404

    if gmail_id in service["recipients"]:
        success = update_recipients(service_name, gmail_id, add=False)
        if success:
            # Refresh our local copy to reflect the update
            microservices = get_all_microservices()
            mongo_logger.info(f"Unsubscribed {gmail_id} from {service_name}")
            return jsonify({"message": f"Unsubscribed {gmail_id} from {service_name}"}), 200
        else:
            return jsonify({"error": "Failed to update subscription"}), 500
    else:
        return jsonify({"message": f"{gmail_id} is not subscribed to {service_name}"}), 404

@app.route('/refresh', methods=['POST'])
def refresh():
    global refresh_flag
    refresh_flag = True
    return jsonify({"message": "Refresh flag set to True. Microservices will be refreshed on next monitor iteration."}), 200

def send_alert(service_name, recipients, alert_type="down"):
    try:
        subject = f"ALERT: {service_name} is {alert_type}!"
        body = f"The microservice {service_name} is {alert_type}. Please check the service."
        send_email(subject, body, recipients)
        mongo_logger.info(f"Alert sent for {service_name}: {alert_type}")
    except Exception as e:
        mongo_logger.error(f"Failed to send alert for {service_name}: {e}")

def check_service_health(service):
    try:
        # Add /status to the URL if it's not already there
        url = service['url']
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            if service.get('prev_status') == False:
                mongo_logger.info(f"{service['name']} is back up.")
                send_alert(service['name'], service['recipients'], alert_type="up")
            update_prev_status(service['name'], True)
            mongo_logger.info(f"{service['name']} is healthy.")
            return True
        else:
            if service.get('prev_status') == True:
                mongo_logger.error(f"{service['name']} returned status code {response.status_code}")
                send_alert(service['name'], service['recipients'], alert_type="down")
            update_prev_status(service['name'], False)
            mongo_logger.info(f"{service['name']} is down.")
            return False
    except requests.exceptions.RequestException as e:
        if service.get('prev_status') == True:
            mongo_logger.error(f"Error while checking {service['name']}: {e}")
            send_alert(service['name'], service['recipients'], alert_type="down")
        update_prev_status(service['name'], False)
        mongo_logger.info(f"{service['name']} is down.")
        return False

def monitor_services():
    try:
        global microservices, refresh_flag
        while True:
            if refresh_flag:
                mongo_logger.info("Refreshing microservices list...")
                microservices = get_all_microservices()
                mongo_logger.info("Microservices list refreshed.")
                refresh_flag = False

            for service in microservices:
                check_service_health(service)
            time.sleep(SLEEP_TIME)
    except Exception as e:
        mongo_logger.error(f"Error in monitoring services: {e}")

def main():
    service_monitoring_thread = threading.Thread(target=monitor_services)
    service_monitoring_thread.daemon = True  # Make thread daemon so it exits when main thread exits
    service_monitoring_thread.start()

    app.run(host=SERVER_ADDRESS, port=PORT, debug=False)

if __name__ == "__main__":
    main()