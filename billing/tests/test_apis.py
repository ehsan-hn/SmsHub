from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from account.models import User


class ChargeAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.user.balance = 10000
        self.user.save()
        self.url = reverse("billing:charge")

    def test_charge_api_success(self):
        """Test successful charge via API"""
        self.user.refresh_from_db()
        initial_balance = self.user.balance
        charge_amount = 5000

        data = {
            "user_id": self.user.id,
            "amount": charge_amount,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_id"], self.user.id)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance + charge_amount)

    def test_charge_api_user_not_found(self):
        """Test charge API with non-existent user"""
        data = {
            "user_id": 99999,
            "amount": 1000,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_charge_api_invalid_amount_zero(self):
        """Test charge API with zero amount"""
        data = {
            "user_id": self.user.id,
            "amount": 0,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_charge_api_invalid_amount_negative(self):
        """Test charge API with negative amount"""
        data = {
            "user_id": self.user.id,
            "amount": -1000,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_charge_api_missing_user_id(self):
        """Test charge API without user_id"""
        data = {
            "amount": 1000,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user_id", response.data)

    def test_charge_api_missing_amount(self):
        """Test charge API without amount"""
        data = {
            "user_id": self.user.id,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)

    def test_charge_api_invalid_user_id_type(self):
        """Test charge API with invalid user_id type"""
        data = {
            "user_id": "not_an_integer",
            "amount": 1000,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_charge_api_invalid_amount_type(self):
        """Test charge API with invalid amount type"""
        data = {
            "user_id": self.user.id,
            "amount": "not_an_integer",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_charge_api_large_amount(self):
        """Test charge API with large amount"""
        self.user.refresh_from_db()
        initial_balance = self.user.balance
        charge_amount = 1000000

        data = {
            "user_id": self.user.id,
            "amount": charge_amount,
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance + charge_amount)
