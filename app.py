import threading
import time
import requests
import logging
from flask import Flask, jsonify
from emailer import send_email  # Make sure emailer.py is in the same directory

# List of microservices with health check URLs
microservices = [
    {"name": "data_collection", "url": "http://localhost:5001/health", "recipients": [], "is_online": True},
    {"name": "data_retrival", "url": "http://localhost:5002/health", "recipients": [], "is_online": True},
    {"name": "data_analytics", "url": "http://localhost:5003/health", "recipients": [], "is_online": True}
]

# Global variable to track the last heartbeat time of the watchdog
last_heartbeat_time = time.time()

# Lock for thread-safe logging
log_lock = threading.Lock()

# Set up logging to log alerts and monitoring information
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Initialize the Flask app for the watchdog's status endpoint
app = Flask(__name__)

@app.route('/status')
def status():
    # Status endpoint to report if the primary watchdog is running.
    return jsonify({"status": "alive", "message": "Primary Watchdog is running."}), 200

def send_alert(service_name, recipients):
    # Send an email alert if the service is down.
    subject = f"ALERT: {service_name} is down!"
    body = f"The microservice {service_name} is not responding. Please check the service."
    send_email(subject, body, recipients)

def check_service_health(service):
    # Check the health of a single service.
    try:
        response = requests.get(service['url'], timeout=5)
        if response.status_code == 200:
            logging.info(f"{service['name']} is healthy.")
        else:
            logging.error(f"{service['name']} returned status code {response.status_code}")
            send_alert(service['name'], service['recipients'])
    except requests.exceptions.RequestException as e:
        logging.error(f"Error while checking {service['name']}: {e}")
        send_alert(service['name'], service['recipients'])

def watchdog_health_check():
    # Watchdog's own health check. Periodically sends heartbeat.
    global last_heartbeat_time
    try:
        while True:
            response = requests.post('http://localhost:8080/heartbeat', json={'status': 'alive'})
            if response.status_code == 200:
                logging.info("Watchdog heartbeat sent successfully.")
            else:
                logging.error("Watchdog heartbeat failed.")
            last_heartbeat_time = time.time()
            time.sleep(30)  # Heartbeat interval (30 seconds)
    except requests.exceptions.RequestException as e:
        logging.error(f"Watchdog heartbeat failed: {e}")

def monitor_heartbeat():
    # Monitor the watchdog's own heartbeat to ensure it is alive.
    global last_heartbeat_time
    try:
        while True:
            if time.time() - last_heartbeat_time > 60:  # 1 minute without heartbeat
                logging.error("Watchdog failed to send heartbeat in time. Watchdog might be down.")
                send_alert("Watchdog", [])  # You can specify recipients here
            time.sleep(30)  # Check every 30 seconds
    except Exception as e:
        logging.error(f"Error in monitoring heartbeat: {e}")

def main():
    threads = []
    
    # Start a thread for each microservice health check
    for service in microservices:
        thread = threading.Thread(target=check_service_health, args=(service,))
        thread.daemon = True
        threads.append(thread)
        thread.start()

    # Start the watchdog's own health check thread
    watchdog_thread = threading.Thread(target=watchdog_health_check)
    watchdog_thread.daemon = True
    threads.append(watchdog_thread)
    watchdog_thread.start()

    # Start the heartbeat monitoring thread for the watchdog
    heartbeat_thread = threading.Thread(target=monitor_heartbeat)
    heartbeat_thread.daemon = True
    threads.append(heartbeat_thread)
    heartbeat_thread.start()

    # Run the Flask app in the main thread
    app.run(host='0.0.0.0', port=8080)  # Flask will now run in the main thread

if __name__ == "__main__":
    main()
