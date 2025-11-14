from unittest.mock import Mock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from account.models import User
from sms.models import SMS, SMSStatus


class SendSMSAPITestCase(APITestCase):
    """Test cases for the Send SMS API endpoint"""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.user.balance = 10000
        self.user.save()
        self.url = reverse("sms:send_sms")

    @patch("sms.tasks.send_normal_sms")
    def test_send_sms_api_success_normal(self, mock_normal_sms):
        """Test successful normal SMS send via API"""
        initial_balance = self.user.balance
        mock_task = Mock()
        mock_task.id = "task-123"
        mock_normal_sms.delay = Mock(return_value=mock_task)

        data = {
            "user_id": self.user.id,
            "receiver": "09120000001",
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sms_id", response.data)
        self.assertIn("task_id", response.data)
        self.assertEqual(response.data["task_id"], "task-123")

        # Verify SMS was created
        sms = SMS.objects.get(id=response.data["sms_id"])
        self.assertEqual(sms.user, self.user)
        self.assertEqual(sms.receiver, "09120000001")
        self.assertEqual(sms.content, "Test message")
        self.assertFalse(sms.is_express)
        self.assertEqual(sms.cost, 1000)
        self.assertEqual(sms.status, SMSStatus.IN_QUEUE)

        # Verify balance was deducted
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance - 1000)

        # Verify task was called
        mock_normal_sms.delay.assert_called_once_with(sms.id)

    @patch("sms.tasks.send_express_sms")
    def test_send_sms_api_success_express(self, mock_express_sms):
        """Test successful express SMS send via API"""
        initial_balance = self.user.balance
        mock_task = Mock()
        mock_task.id = "task-456"
        mock_express_sms.delay = Mock(return_value=mock_task)

        data = {
            "user_id": self.user.id,
            "receiver": "09120000002",
            "content": "Express message",
            "is_express": True,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sms_id", response.data)
        self.assertIn("task_id", response.data)

        # Verify SMS was created
        sms = SMS.objects.get(id=response.data["sms_id"])
        self.assertTrue(sms.is_express)
        self.assertEqual(sms.cost, 1500)

        # Verify balance was deducted
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance - 1500)

        # Verify express task was called
        mock_express_sms.delay.assert_called_once_with(sms.id)

    def test_send_sms_api_insufficient_funds(self):
        """Test send SMS API with insufficient funds"""
        self.user.balance = 500
        self.user.save()

        data = {
            "user_id": self.user.id,
            "receiver": "09120000001",
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "Insufficient funds")

        # Verify no SMS was created
        sms_count = SMS.objects.filter(user=self.user).count()
        self.assertEqual(sms_count, 0)

    def test_send_sms_api_user_not_found(self):
        """Test send SMS API with non-existent user"""
        data = {
            "user_id": 99999,
            "receiver": "09120000001",
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_send_sms_api_invalid_receiver_format(self):
        """Test send SMS API with invalid receiver format"""
        data = {
            "user_id": self.user.id,
            "receiver": "invalid-phone",
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_sms_api_receiver_too_short(self):
        """Test send SMS API with receiver too short"""
        data = {
            "user_id": self.user.id,
            "receiver": "12345678",  # Less than 9 digits
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_sms_api_receiver_too_long(self):
        """Test send SMS API with receiver too long"""
        data = {
            "user_id": self.user.id,
            "receiver": "1234567890123456",  # More than 15 digits
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_sms_api_empty_content(self):
        """Test send SMS API with empty content"""
        data = {
            "user_id": self.user.id,
            "receiver": "09120000001",
            "content": "",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_sms_api_content_too_long(self):
        """Test send SMS API with content too long"""
        data = {
            "user_id": self.user.id,
            "receiver": "09120000001",
            "content": "x" * 481,  # More than 480 characters
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_sms_api_missing_user_id(self):
        """Test send SMS API without user_id"""
        data = {
            "receiver": "09120000001",
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user_id", response.data)

    def test_send_sms_api_missing_receiver(self):
        """Test send SMS API without receiver"""
        data = {
            "user_id": self.user.id,
            "content": "Test message",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("receiver", response.data)

    def test_send_sms_api_missing_content(self):
        """Test send SMS API without content"""
        data = {
            "user_id": self.user.id,
            "receiver": "09120000001",
            "is_express": False,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("content", response.data)

    @patch("sms.tasks.send_normal_sms")
    def test_send_sms_api_valid_receiver_formats(self, mock_normal_sms):
        """Test send SMS API with various valid receiver formats"""
        mock_task = Mock()
        mock_task.id = "task-valid"
        mock_normal_sms.delay = Mock(return_value=mock_task)

        valid_receivers = ["09120000001", "123456789", "123456789012345"]

        for receiver in valid_receivers:
            data = {
                "user_id": self.user.id,
                "receiver": receiver,
                "content": "Test message",
                "is_express": False,
            }

            response = self.client.post(self.url, data, format="json")
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Receiver {receiver} should be valid",
            )
