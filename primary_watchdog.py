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

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Flag for refreshing microservices list
refresh_flag = False

# Load the microservices at startup
microservices = get_all_microservices()

# Configure MongoDB logging
mongo_logger = create_mongo_logger(log_level=logging.DEBUG)

SERVER_ADDRESS = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
PORT = int(os.getenv("FLASK_RUN_PORT", 5000))

@app.route('/status')
def status():
    # Primary Watchdog status endpoint to report if it's alive
    return jsonify({"status": "alive", "message": "Primary Watchdog is running."}), 200

@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    service_name = data.get("service_name")
    gmail_id = data.get("gmail_id")

    service = next((s for s in microservices if s["name"] == service_name), None)

    if not service:
        return jsonify({"error": "Service not found"}), 404

    if gmail_id not in service["recipients"]:
        update_recipients(service_name, gmail_id, add=True)
        mongo_logger.info(f"Subscribed {gmail_id} to {service_name}")
        return jsonify({"message": f"Subscribed {gmail_id} to {service_name}"}), 200
    else:
        return jsonify({"message": f"{gmail_id} is already subscribed to {service_name}"}), 200

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    data = request.get_json()
    service_name = data.get("service_name")
    gmail_id = data.get("gmail_id")

    service = next((s for s in microservices if s["name"] == service_name), None)

    if not service:
        return jsonify({"error": "Service not found"}), 404

    if gmail_id in service["recipients"]:
        update_recipients(service_name, gmail_id, add=False)
        mongo_logger.info(f"Unsubscribed {gmail_id} from {service_name}")
        return jsonify({"message": f"Unsubscribed {gmail_id} from {service_name}"}), 200
    else:
        return jsonify({"message": f"{gmail_id} is not subscribed to {service_name}"}), 404

@app.route('/refresh', methods=['POST'])
def refresh():
    global refresh_flag
    refresh_flag = True
    return jsonify({"message": "Refresh flag set to True. Microservices will be refreshed on next monitor iteration."}), 200

def send_alert(service_name, recipients, alert_type="down"):
    subject = f"ALERT: {service_name} is {alert_type}!"
    body = f"The microservice {service_name} is {alert_type}. Please check the service."
    send_email(subject, body, recipients)

def check_service_health(service):
    try:
        response = requests.get(service['url'], timeout=5)
        if response.status_code == 200:
            if service['prev_status'] == False:
                mongo_logger.info(f"{service['name']} is back up.")
                send_alert(service['name'], service['recipients'], alert_type="up")
            service['prev_status'] = True
            update_prev_status(service['name'], True)
            mongo_logger.info(f"{service['name']} is healthy.")
        else:
            if service['prev_status'] == True:
                mongo_logger.error(f"{service['name']} returned status code {response.status_code}")
                send_alert(service['name'], service['recipients'], alert_type="down")
            service['prev_status'] = False
            update_prev_status(service['name'], False)
    except requests.exceptions.RequestException as e:
        if service['prev_status'] == True:
            mongo_logger.error(f"Error while checking {service['name']}: {e}")
            send_alert(service['name'], service['recipients'], alert_type="down")
        service['prev_status'] = False
        update_prev_status(service['name'], False)

def monitor_services():
    try:
        global microservices
        while True:
            if refresh_flag:
                mongo_logger.info("Refreshing microservices list...")
                microservices = get_all_microservices()
                mongo_logger.info("Microservices list refreshed.")
                refresh_flag = False

            for service in microservices:
                check_service_health(service)
            time.sleep(300)  # Check every 5 minutes
    except Exception as e:
        mongo_logger.error(f"Error in monitoring services: {e}")

def main():
    threads = []
    
    service_monitoring_thread = threading.Thread(target=monitor_services)
    service_monitoring_thread.daemon = True
    threads.append(service_monitoring_thread)
    service_monitoring_thread.start()

    app.run(host=SERVER_ADDRESS, port=PORT, debug=False)

if __name__ == "__main__":
    main()
