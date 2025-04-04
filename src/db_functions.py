import os
import logging
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get MongoDB URI from the .env file
MONGO_URI = os.getenv("MONGO_URI")
# MONGO_URI_TEST = os.getenv("MONGO_URI_TEST", "mongodb://localhost:27017/Qubit")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Choose the appropriate MongoDB URI based on the TEST_MODE
if TEST_MODE:
    MONGO_URI = os.getenv("MONGO_URI_TEST", "mongodb://localhost:27017/Qubit")

# Function to get all microservices stored in the collection
def get_all_microservices(mongo_uri=None):
    # Use provided URI or fall back to the global one
    if mongo_uri is None:
        mongo_uri = MONGO_URI
    
    # Establish MongoDB connection
    client = MongoClient(mongo_uri)
    db = client["Qubit"]
    collection = db["Watchdog_microservices"]
    
    # Get all microservices stored in the collection
    microservices = collection.find()
    microservices = list(microservices)
    # print(list(microservices))
    # print(mongo_uri)
    client.close()
    return list(microservices)

# Function to update the prev_status field for a specific microservice by its name
def update_prev_status(service_name, new_status, mongo_uri=None):
    # Use provided URI or fall back to the global one
    if mongo_uri is None:
        mongo_uri = MONGO_URI
        
    # Establish MongoDB connection
    client = MongoClient(mongo_uri)
    db = client["Qubit"]
    collection = db["Watchdog_microservices"]
    
    try:
        # Update the prev_status field for a specific microservice by its name
        result = collection.update_one(
            {"name": service_name},
            {"$set": {"prev_status": new_status}}
        )
        
        # Return True if the update was successful
        return result.modified_count > 0
    finally:
        # Ensure the client is closed regardless of success or failure
        client.close()

# Function to add or remove an email from the recipients list for a specific microservice by its name
def update_recipients(service_name, email, add=True, mongo_uri=None):
    # Use provided URI or fall back to the global one
    if mongo_uri is None:
        mongo_uri = MONGO_URI
        
    # Establish MongoDB connection
    client = MongoClient(mongo_uri)
    db = client["Qubit"]
    collection = db["Watchdog_microservices"]
    
    # Add or remove an email from the recipients list
    try:
        if add:
            result = collection.update_one(
                {"name": service_name},
                {"$addToSet": {"recipients": email}}
            )
        else:
            result = collection.update_one(
                {"name": service_name},
                {"$pull": {"recipients": email}}
            )
        
        # Return True if the update was successful
        return result.modified_count > 0
    finally:
        client.close()

# Function to retrieve the prev_status field for a specific microservice by its name
def get_prev_status(service_name, mongo_uri=None):
    # Use provided URI or fall back to the global one
    if mongo_uri is None:
        mongo_uri = MONGO_URI
        
    # Establish MongoDB connection
    client = MongoClient(mongo_uri)
    db = client["Qubit"]
    collection = db["Watchdog_microservices"]
    
    # Retrieve the prev_status field for a specific microservice by its name
    try:
        service = collection.find_one({"name": service_name}, {"prev_status": 1})
        if service:
            return service.get("prev_status")
        return None
    finally:
        client.close()

# Function to retrieve the recipients list for a specific microservice by its name
def get_recipients(service_name, mongo_uri=None):
    # Use provided URI or fall back to the global one
    if mongo_uri is None:
        mongo_uri = MONGO_URI
        
    # Establish MongoDB connection
    client = MongoClient(mongo_uri)
    db = client["Qubit"]
    collection = db["Watchdog_microservices"]
    
    # Retrieve the recipients list for a specific microservice by its name
    try:
        service = collection.find_one({"name": service_name}, {"recipients": 1})
        if service:
            return service.get("recipients", [])
        return []
    finally:
        client.close()

####################################################################################
############################ LOGGING FUNCTIONS BELOW ###############################
####################################################################################
# Default MongoDB configuration

DEFAULT_DB_NAME = 'Qubit'
DEFAULT_COLLECTION_NAME = 'logs'
DEFAULT_LOG_LEVEL = logging.DEBUG

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

def create_mongo_logger(mongo_uri=None, 
                        db_name=DEFAULT_DB_NAME, 
                        collection_name=DEFAULT_COLLECTION_NAME,
                        log_level=DEFAULT_LOG_LEVEL):
    
    # Use provided URI or fall back to the global one
    if mongo_uri is None:
        mongo_uri = MONGO_URI
        
    mongo_handler = MongoDBHandler(mongo_uri, db_name, collection_name)
    mongo_handler.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    mongo_handler.setFormatter(formatter)
    logger = logging.getLogger('MongoLogger')
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers = []
        
    logger.addHandler(mongo_handler)
    
    return logger