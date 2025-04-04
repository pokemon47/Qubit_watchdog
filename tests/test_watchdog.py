import unittest
from unittest.mock import patch, MagicMock, call
import json
import os
import sys
from pymongo import MongoClient
import requests

# Import the module to test
# Assuming primary_watchdog.py is in the same directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import primary_watchdog  # The module we're testing

class TestPrimaryWatchdog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup MongoDB test data
        cls.mongo_uri = os.getenv("MONGO_URI_TEST", "mongodb://localhost:27017/Qubit")
        cls.test_services = [
            {
                "name": "service1",
                "url": "http://example.com/service1/status",
                "recipients": ["test1@example.com", "test2@example.com"],
                "prev_status": True
            },
            {
                "name": "service2",
                "url": "http://example.com/service2/status",
                "recipients": ["test1@example.com"],
                "prev_status": False
            }
        ]

    def setUp(self):
        # Reset MongoDB before each test that interacts with it
        self.reset_mongo_data()
        
        # Create a test Flask client
        primary_watchdog.app.config['TESTING'] = True
        self.client = primary_watchdog.app.test_client()

    def reset_mongo_data(self):
        """Reset MongoDB database and initialize with test data"""
        client = MongoClient(self.mongo_uri)
        db = client["Qubit"]
        
        # Drop the collections we'll be using
        db["Watchdog_microservices"].drop()
        db["logs"].drop()
        
        # Initialize with test data
        db["Watchdog_microservices"].insert_many(self.test_services)
        client.close()

    @patch('primary_watchdog.get_all_microservices')
    def test_status_endpoint(self, mock_get_all):
        # Act
        response = self.client.get('/status')
        data = json.loads(response.data)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'alive')
        self.assertEqual(data['message'], 'Primary Watchdog is running.')

    @patch('primary_watchdog.send_email')
    @patch('primary_watchdog.requests.get')
    def test_check_service_health_up(self, mock_requests_get, mock_send_email):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response
        
        service = self.test_services[1].copy()  # Service was previously down
        
        # Act
        with patch('primary_watchdog.update_prev_status') as mock_update:
            result = primary_watchdog.check_service_health(service)
        
        # Assert
        self.assertTrue(result)
        mock_requests_get.assert_called_with(service['url'], timeout=5)
        mock_update.assert_called_with(service['name'], True)
        mock_send_email.assert_called_once()  # Should send "up" alert

    @patch('primary_watchdog.send_email')
    @patch('primary_watchdog.requests.get')
    def test_check_service_health_down(self, mock_requests_get, mock_send_email):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests_get.return_value = mock_response
        
        service = self.test_services[0].copy()  # Service was previously up
        
        # Act
        with patch('primary_watchdog.update_prev_status') as mock_update:
            result = primary_watchdog.check_service_health(service)
        
        # Assert
        self.assertFalse(result)
        mock_requests_get.assert_called_with(service['url'], timeout=5)
        mock_update.assert_called_with(service['name'], False)
        mock_send_email.assert_called_once()  # Should send "down" alert

    @patch('primary_watchdog.send_email')
    @patch('primary_watchdog.requests.get')
    def test_check_service_health_exception(self, mock_requests_get, mock_send_email):
        # Arrange
        mock_requests_get.side_effect = requests.exceptions.RequestException("Connection error")
        
        service = self.test_services[0].copy()  # Service was previously up
        
        # Act
        with patch('primary_watchdog.update_prev_status') as mock_update:
            result = primary_watchdog.check_service_health(service)
        
        # Assert
        self.assertFalse(result)
        mock_requests_get.assert_called_with(service['url'], timeout=5)
        mock_update.assert_called_with(service['name'], False)
        mock_send_email.assert_called_once()  # Should send "down" alert

    @patch('primary_watchdog.get_all_microservices')
    @patch('primary_watchdog.update_recipients')
    def test_subscribe_endpoint_new_subscription(self, mock_update, mock_get_all):
        # Arrange
        mock_get_all.return_value = self.test_services
        mock_update.return_value = True
        
        # Act
        response = self.client.post('/subscribe', 
                              json={"service_name": "service1", "gmail_id": "newuser@example.com"})
        data = json.loads(response.data)
        
        print("test_subscribe_endpoint_new_subscription", data)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], "Subscribed newuser@example.com to service1")
        mock_update.assert_called_with("service1", "newuser@example.com", add=True)
        # Should call get_all_microservices twice: once at initialization and once after update
        # self.assertEqual(mock_get_all.call_count, 2)

    @patch('primary_watchdog.get_all_microservices')
    def test_subscribe_endpoint_already_subscribed(self, mock_get_all):
        # Arrange
        mock_get_all.return_value = self.test_services
        
        # Act
        response = self.client.post('/subscribe', 
                              json={"service_name": "service1", "gmail_id": "test1@example.com"})
        data = json.loads(response.data)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], "test1@example.com is already subscribed to service1")

    @patch('primary_watchdog.get_all_microservices')
    def test_subscribe_endpoint_service_not_found(self, mock_get_all):
        # Arrange
        mock_get_all.return_value = self.test_services
        
        # Act
        response = self.client.post('/subscribe', 
                              json={"service_name": "nonexistent", "gmail_id": "test1@example.com"})
        data = json.loads(response.data)
        
        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(data['error'], "Service not found")

    @patch('primary_watchdog.get_all_microservices')
    @patch('primary_watchdog.update_recipients')
    def test_unsubscribe_endpoint_success(self, mock_update, mock_get_all):
        # Arrange
        mock_get_all.return_value = self.test_services
        mock_update.return_value = True
        
        # Act
        response = self.client.post('/unsubscribe', 
                              json={"service_name": "service1", "gmail_id": "test1@example.com"})
        data = json.loads(response.data)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], "Unsubscribed test1@example.com from service1")
        mock_update.assert_called_with("service1", "test1@example.com", add=False)

    @patch('primary_watchdog.get_all_microservices')
    def test_unsubscribe_endpoint_not_subscribed(self, mock_get_all):
        # Arrange
        mock_get_all.return_value = self.test_services
        
        # Act
        response = self.client.post('/unsubscribe', 
                              json={"service_name": "service1", "gmail_id": "notsubscribed@example.com"})
        data = json.loads(response.data)
        
        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(data['message'], "notsubscribed@example.com is not subscribed to service1")

    @patch('primary_watchdog.get_all_microservices')
    def test_unsubscribe_endpoint_service_not_found(self, mock_get_all):
        # Arrange
        mock_get_all.return_value = self.test_services
        
        # Act
        response = self.client.post('/unsubscribe', 
                              json={"service_name": "nonexistent", "gmail_id": "test1@example.com"})
        data = json.loads(response.data)
        
        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(data['error'], "Service not found")

    def test_refresh_endpoint(self):
        # Act
        response = self.client.post('/refresh')
        data = json.loads(response.data)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], "Refresh flag set to True. Microservices will be refreshed on next monitor iteration.")
        self.assertTrue(primary_watchdog.refresh_flag)
        
        # Reset the flag after test
        primary_watchdog.refresh_flag = False

    @patch('primary_watchdog.send_email')
    def test_send_alert_down(self, mock_send_email):
        # Act
        primary_watchdog.send_alert("service1", ["test1@example.com"], "down")
        
        # Assert
        mock_send_email.assert_called_with(
            "ALERT: service1 is down!",
            "The microservice service1 is down. Please check the service.",
            ["test1@example.com"]
        )

    @patch('primary_watchdog.send_email')
    def test_send_alert_up(self, mock_send_email):
        # Act
        primary_watchdog.send_alert("service1", ["test1@example.com"], "up")
        
        # Assert
        mock_send_email.assert_called_with(
            "ALERT: service1 is up!",
            "The microservice service1 is up. Please check the service.",
            ["test1@example.com"]
        )

    @patch('primary_watchdog.check_service_health')
    @patch('primary_watchdog.get_all_microservices')
    @patch('time.sleep')  # Prevent actual sleeping during tests
    def test_monitor_services(self, mock_sleep, mock_get_all, mock_check_health):
        # Arrange
        primary_watchdog.refresh_flag = True  # Set refresh flag to test that code path
        mock_get_all.return_value = self.test_services
        
        # Create a version of monitor_services that runs once and exits
        def mock_run_once():
            try:
                primary_watchdog.monitor_services()
            except StopIteration:
                pass
                
        # Set up mock_sleep to raise StopIteration on its first call to exit the loop
        mock_sleep.side_effect = StopIteration()
        
        # Act
        with patch.object(primary_watchdog, 'SLEEP_TIME', 0):  # Avoid sleeping
            mock_run_once()
        
        # Assert
        mock_get_all.assert_called_once()
        self.assertFalse(primary_watchdog.refresh_flag)
        
        # Should have called check_service_health for each service
        expected_calls = [call(service) for service in self.test_services]
        mock_check_health.assert_has_calls(expected_calls)
        
    @patch('primary_watchdog.threading.Thread')
    def test_main(self, mock_thread):
        # Arrange
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Create a mock Flask app run method
        with patch.object(primary_watchdog.app, 'run') as mock_run:
            # Act
            primary_watchdog.main()
            
            # Assert
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()
            mock_run.assert_called_once_with(
                host=primary_watchdog.SERVER_ADDRESS, 
                port=primary_watchdog.PORT, 
                debug=False
            )

class TestPrimaryWatchdogIntegration(unittest.TestCase):
    """Integration tests that interact with a real MongoDB instance"""
    
    @classmethod
    def setUpClass(cls):
        # Setup MongoDB test connection
        cls.mongo_uri = os.getenv("MONGO_URI_TEST", "mongodb://localhost:27017/Qubit")
        cls.test_services = [
            {
                "name": "service1",
                "url": "http://example.com/service1/status",
                "recipients": ["test1@example.com", "test2@example.com"],
                "prev_status": True
            },
            {
                "name": "service2",
                "url": "http://example.com/service2/status",
                "recipients": ["test1@example.com"],
                "prev_status": False
            }
        ]

    def setUp(self):
        # Reset MongoDB before each test
        self.reset_mongo_data()
        
        # Create a test Flask client
        primary_watchdog.app.config['TESTING'] = True
        self.client = primary_watchdog.app.test_client()
        
        # Force refresh of microservices list
        primary_watchdog.microservices = primary_watchdog.get_all_microservices()

    def reset_mongo_data(self):
        """Reset MongoDB database and initialize with test data"""
        client = MongoClient(self.mongo_uri)
        db = client["Qubit"]
        
        # Drop the collections we'll be using
        db["Watchdog_microservices"].drop()
        db["logs"].drop()
        
        # Initialize with test data
        db["Watchdog_microservices"].insert_many(self.test_services)
        client.close()

    def test_subscribe_endpoint_integration(self):
        # Act
        response = self.client.post('/subscribe', 
                             json={"service_name": "service1", "gmail_id": "newuser@example.com"})
        data = json.loads(response.data)
        print(data)
        # Assert API response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], "Subscribed newuser@example.com to service1")
        
        # Verify database was updated correctly
        client = MongoClient(self.mongo_uri)
        db = client["Qubit"]
        service = db["Watchdog_microservices"].find_one({"name": "service1"})
        client.close()
        
        self.assertIn("newuser@example.com", service["recipients"])

    def test_unsubscribe_endpoint_integration(self):
        # Act
        response = self.client.post('/unsubscribe', 
                             json={"service_name": "service1", "gmail_id": "test1@example.com"})
        data = json.loads(response.data)
        
        # Assert API response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], "Unsubscribed test1@example.com from service1")
        
        # Verify database was updated correctly
        client = MongoClient(self.mongo_uri)
        db = client["Qubit"]
        service = db["Watchdog_microservices"].find_one({"name": "service1"})
        client.close()
        
        self.assertNotIn("test1@example.com", service["recipients"])

    @patch('primary_watchdog.send_email')
    @patch('primary_watchdog.requests.get')
    def test_check_service_health_integration(self, mock_requests_get, mock_send_email):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 500  # Service is down
        mock_requests_get.return_value = mock_response
        
        # Get service1 (which was initialized as 'up')
        client = MongoClient(self.mongo_uri)
        db = client["Qubit"]
        service = db["Watchdog_microservices"].find_one({"name": "service1"})
        client.close()
        
        # Act
        result = primary_watchdog.check_service_health(service)
        
        # Assert
        self.assertFalse(result)
        
        # Verify database was updated
        client = MongoClient(self.mongo_uri)
        db = client["Qubit"]
        updated_service = db["Watchdog_microservices"].find_one({"name": "service1"})
        client.close()
        
        self.assertFalse(updated_service["prev_status"])
        mock_send_email.assert_called_once()  # Should send "down" alert

if __name__ == '__main__':
    unittest.main()