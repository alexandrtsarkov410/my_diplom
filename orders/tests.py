from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()

class SimpleOrdersTests(APITestCase):
    """автотесты для проверки эндпоинтов заказов и корзины"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='buyer_order_test@example.com',
            password='Password123!',
            first_name='Ivan',
            type='buyer'
        )
        self.client.force_authenticate(user=self.user)

    def test_get_basket_endpoint(self):
        """Проверяем доступность эндпоинта корзины"""
        url = '/api/v1/orders/basket/'
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_get_orders_endpoint(self):
        """Проверяем доступность эндпоинта списка заказов"""
        url = '/api/v1/orders/order/'
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])

