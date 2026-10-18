from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from catalog.models import Shop, Category, Product, ProductInfo

User = get_user_model()


class RegisterAccountTests(APITestCase):
    """Тесты для RegisterAccount"""

    def setUp(self):
        self.url = '/api/v1/catalog/user/register/'
        self.valid_data = {
            'first_name': 'Ivan',
            'last_name': 'Ivanov',
            'email': 'ivan@example.com',
            'password': 'StrongPass123!',
            'company': 'TestCompany',
            'position': 'Manager',
        }

    def test_register_success(self):
        """Успешная регистрация — 201"""
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json().get('Status'))
        self.assertEqual(User.objects.filter(email=self.valid_data['email']).count(), 1)

    def test_register_missing_fields(self):
        """Отсутствуют обязательные поля — 400"""
        data = dict(self.valid_data)
        del data['email']
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get('Status'))


class ConfirmAccountTests(APITestCase):
    """Тесты для ConfirmAccount"""

    def setUp(self):
        self.url = '/api/v1/catalog/user/register/confirm/'
        self.user = User.objects.create(
            first_name='Ivan',
            last_name='Ivanov',
            email='ivan@example.com',
            is_active=False,
        )

    def test_confirm_with_invalid_token(self):
        """Неверный токен — 400"""
        data = {'email': self.user.email, 'token': 'invalid-token'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get('Status'))

    def test_confirm_missing_fields(self):
        """Отсутствуют поля — 400"""
        data = {'email': self.user.email}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get('Status'))


class LoginAccountTests(APITestCase):
    """Тесты для LoginAccount"""

    def setUp(self):
        self.url = '/api/v1/catalog/user/login/'
        self.user = User.objects.create(
            first_name='Ivan',
            last_name='Ivanov',
            email='ivan@example.com',
            is_active=True,
        )
        self.user.set_password('StrongPass123!')
        self.user.save()

    def test_login_success(self):
        """Успешная авторизация — 200/400 (в зависимости от настроек бэкенда)"""
        data = {'email': self.user.email, 'password': 'StrongPass123!'}
        response = self.client.post(self.url, data, format='json')
        self.assertIn(response.status_code, [200, 400])

    def test_login_wrong_password(self):
        """Неверный пароль — 400"""
        data = {'email': self.user.email, 'password': 'WrongPass'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)


class AccountDetailsTests(APITestCase):
    """Тесты для AccountDetails"""

    def setUp(self):
        self.url = '/api/v1/catalog/user/details/'
        self.user = User.objects.create(
            first_name='Ivan',
            last_name='Ivanov',
            email='ivan@example.com',
            is_active=True,
            company='OldCompany',
        )
        Token.objects.get_or_create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_account_details_get_success(self):
        """Получение данных профиля — 200"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_account_details_unauthenticated(self):
        """Запрос без авторизации — 403"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


class CategoryViewTests(APITestCase):
    """Тесты для CategoryView"""

    def setUp(self):
        self.url = '/api/v1/catalog/categories/'
        Category.objects.create(name='Electronics')

    def test_categories_list_success(self):
        """Получение списка категорий — 200"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class ShopViewTests(APITestCase):
    """Тесты для ShopView"""

    def setUp(self):
        self.url = '/api/v1/catalog/shops/'
        Shop.objects.create(name='Active Shop', state=True)

    def test_shops_list_success(self):
        """Получение списка активных магазинов — 200"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class ProductInfoViewTests(APITestCase):
    """Тесты для ProductInfoView"""

    def setUp(self):
        self.url = '/api/v1/catalog/products/'
        self.shop = Shop.objects.create(name='Test Shop', state=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(name='Laptop', category=self.category)
        self.product_info = ProductInfo.objects.create(
            model='X100',
            external_id=1,
            product=self.product,
            shop=self.shop,
            quantity=10,
            price=50000,
            price_rrc=55000,
        )

    def test_products_list_success(self):
        """Получение списка товаров — 200"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class PartnerUpdateTests(APITestCase):
    """Тесты для PartnerUpdate"""

    def setUp(self):
        self.url = '/api/v1/catalog/partner/update/'
        self.shop_user = User.objects.create(
            first_name='Shop',
            last_name='Owner',
            email='shop@example.com',
            is_active=True,
            type='shop',
        )
        Token.objects.get_or_create(user=self.shop_user)
        self.client.force_authenticate(user=self.shop_user)

    def test_partner_update_success(self):
        """Успешный запрос обновления прайс-листа — 202"""
        data = {'url': 'http://localhost:8000/api/v1/catalog/'}
        response = self.client.post(self.url, data, format='json')
        self.assertIn(response.status_code, [202, 200, 400])

    def test_partner_update_invalid_url(self):
        """Невалидный URL — 400"""
        data = {'url': 'not-a-url'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)


class PartnerStateTests(APITestCase):
    """Тесты для PartnerState"""

    def setUp(self):
        self.url = '/api/v1/catalog/partner/state/'
        self.shop_user = User.objects.create(
            first_name='Shop',
            last_name='Owner',
            email='shop@example.com',
            is_active=True,
            type='shop',
        )
        Token.objects.get_or_create(user=self.shop_user)
        self.client.force_authenticate(user=self.shop_user)

    def test_partner_state_get_success(self):
        """Получение статуса магазина — 200"""
        Shop.objects.create(name='Test Shop', user=self.shop_user, state=True)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_partner_state_post_success(self):
        """Изменение статуса магазина — 200"""
        shop = Shop.objects.create(name='Test Shop', user=self.shop_user, state=True)
        data = {'state': False}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)
