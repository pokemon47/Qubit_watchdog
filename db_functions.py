import os
import logging
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get MongoDB URI from the .env file
MONGO_URI = os.getenv("MONGO_URI")

# Establishing MongoDB connection using the URI from .env file
client = MongoClient(MONGO_URI)
db = client["Qubit"]  # Your database name
collection = db["Watchdog_microservices"]  # The collection name where microservices are stored

# Function to get all microservices stored in the collection
def get_all_microservices():
    # Get all microservices stored in the collection
    microservices = collection.find()
    return list(microservices)  # Return a list of microservices

# Function to update the prev_status field for a specific microservice by its name
def update_prev_status(service_name, new_status):
    # Update the prev_status field for a specific microservice by its name
    result = collection.update_one(
        {"name": service_name},
        {"$set": {"prev_status": new_status}}
    )
    return result.modified_count > 0  # Return True if the update was successful

# Function to add or remove an email from the recipients list for a specific microservice by its name
def update_recipients(service_name, email, action="add"):
    # Add or remove an email from the recipients list for a specific microservice by its name
    if action == "add":
        result = collection.update_one(
            {"name": service_name},
            {"$addToSet": {"recipients": email}}  # $addToSet ensures no duplicates
        )
    elif action == "remove":
        result = collection.update_one(
            {"name": service_name},
            {"$pull": {"recipients": email}}  # $pull removes the specific email
        )
    else:
        raise ValueError("Action must be 'add' or 'remove'")
    return result.modified_count > 0  # Return True if the update was successful

# Function to retrieve the prev_status field for a specific microservice by its name
def get_prev_status(service_name):
    # Retrieve the prev_status field for a specific microservice by its name
    service = collection.find_one({"name": service_name}, {"prev_status": 1})
    if service:
        return service.get("prev_status")
    return None  # Return None if the service is not found

# Function to retrieve the recipients list for a specific microservice by its name
def get_recipients(service_name):
    # Retrieve the recipients list for a specific microservice by its name
    service = collection.find_one({"name": service_name}, {"recipients": 1})
    if service:
        return service.get("recipients", [])
    return []  # Return an empty list if the service is not found

# Example usage:
# if __name__ == "__main__":
#     # Get all microservices
#     all_services = get_all_microservices()
#     print("All microservices:", all_services)

#     # Update the prev_status of a service
#     service_name = "data_collection"
#     new_status = True
#     updated = update_prev_status(service_name, new_status)
#     print(f"Updated prev_status for {service_name}: {updated}")

#     # Update the recipients for a service
#     email_to_add = "user@example.com"
#     added = update_recipients(service_name, email_to_add, action="remove")
#     print(f"Added email to {service_name}: {added}")

#     # Get the prev_status for a service
#     prev_status = get_prev_status(service_name)
#     print(f"prev_status for {service_name}: {prev_status}")

#     # Get the recipients for a service
#     recipients = get_recipients(service_name)
#     print(f"Recipients for {service_name}: {recipients}")




####################################################################################
############################ LOGGING FUNCTIONS BELOW ###############################
####################################################################################
# Default MongoDB configuration

DEFAULT_DB_NAME = 'Qubit'
DEFAULT_COLLECTION_NAME = 'logs'
DEFAULT_LOG_LEVEL = logging.DEBUG  # Default log level

class MongoDBHandler(logging.Handler):
    def __init__(self, mongo_uri, db_name, collection_name):
        super().__init__()
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def emit(self, record):
        log_entry = self.format(record)
        log_document = {
            "timestamp": datetime.utcnow(),
            "level": record.levelname,
            "message": log_entry,
            "logger": record.name,
        }
        # Insert log document into MongoDB
        self.collection.insert_one(log_document)

def create_mongo_logger(mongo_uri=MONGO_URI, 
                        db_name=DEFAULT_DB_NAME, 
                        collection_name=DEFAULT_COLLECTION_NAME,
                        log_level=DEFAULT_LOG_LEVEL):
    # Create the MongoDB handler with provided or default parameters
    mongo_handler = MongoDBHandler(mongo_uri, db_name, collection_name)
    mongo_handler.setLevel(log_level)
    
    # Create a logger and add the MongoDB handler to it
    logger = logging.getLogger('MongoLogger')
    logger.setLevel(log_level)
    logger.addHandler(mongo_handler)
    
    return logger