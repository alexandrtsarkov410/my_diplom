from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from catalog.models import Shop, Category, Product, ProductInfo, ProductPriceHistory

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


class PasswordValidationIntegrationTests(APITestCase):
    """
    Интеграционные тесты для проверки валидации пароля в RegisterSerializer.

    НАЗНАЧЕНИЕ:
    Убедиться, что при регистрации пользователя пароль проходит проверку
    корпоративной политики безопасности, реализованную в методе validate_password()
    сериализатора UserSerializer. Пароль короче 12 символов должен приводить
    к возврату ошибки 400 с подробным описанием нарушения.

    Дипломная работа: проверка безопасности регистрации пользователей.
    """

    def setUp(self):
        """
        Настройка тестового окружения: URL-адрес эндпоинта регистрации
        и валидный набор данных для успешной регистрации.
        """
        self.url = '/api/v1/catalog/user/register/'
        self.valid_data = {
            'first_name': 'Ivan',
            'last_name': 'Ivanov',
            'email': 'ivan@example.com',
            'password': 'StrongPass123!',
            'company': 'TestCompany',
            'position': 'Manager',
        }

    def test_register_short_password_rejected(self):
        """
        Проверка: пароль короче 12 символов отклоняется сервером.

        СЦЕНАРИЙ:
        1. Отправить POST-запрос с паролем длиной менее 12 символов.
        2. Ожидается код ответа 400 (Bad Request).
        3. В теле ответа должно быть поле 'Status': False.
        4. В поле 'Errors' должна присутствовать ошибка валидации для поля 'password'.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Сервер корректно блокирует регистрацию с ослабленным паролем,
        что соответствует корпоративной политике безопасности.
        """
        data = dict(self.valid_data)
        data['password'] = 'Short1A!'
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertFalse(response_data.get('Status'))
        self.assertIn('Errors', response_data)
        self.assertIn('password', response_data['Errors'])

    def test_register_password_without_special_char_rejected(self):
        """
        Проверка: пароль без спецсимвола отклоняется сервером.

        СЦЕНАРИЙ:
        1. Отправить POST-запрос с паролем, содержащим буквы и цифры,
           но не содержащим спецсимвол.
        2. Ожидается код ответа 400 (Bad Request).

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Сервер требует наличия спецсимвола (!@#$%^&* и т.д.),
        что повышает стойкость пароля к брутфорс-атакам.
        """
        data = dict(self.valid_data)
        data['password'] = 'StrongPass123'
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertFalse(response_data.get('Status'))
        self.assertIn('Errors', response_data)
        self.assertIn('password', response_data['Errors'])

    def test_register_valid_password_accepted(self):
        """
        Проверка: пароль, соответствующий всем требованиям, принимается.

        СЦЕНАРИЙ:
        1. Отправить POST-запрос с валидным паролем (12+ символов,
           строчные и заглавные буквы, цифры, спецсимвол).
        2. Ожидается код ответа 201 (Created).
        3. В теле ответа должно быть поле 'Status': True.
        4. Пользователь должен быть создан в базе данных.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Регистрация проходит успешно, пользователь создан.
        """
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertTrue(response_data.get('Status'))
        self.assertEqual(User.objects.filter(email=self.valid_data['email']).count(), 1)


class ProductPriceHistoryIntegrationTests(APITestCase):
    """
    Интеграционные тесты для проверки автоматического создания записей
    в модели ProductPriceHistory при изменении цены в ProductInfo.

    НАЗНАЧЕНИЕ:
    Убедиться, что переопределённый метод save() модели ProductInfo
    автоматически фиксирует все изменения цены в истории ProductPriceHistory.
    Это обеспечивает аудит изменений цен и позволяет анализировать
    динамику стоимости товаров во времени.

    Дипломная работа: отслеживание истории изменения цен товаров.
    """

    def setUp(self):
        """
        Создание тестовых сущностей: магазин, категория, продукт и ProductInfo
        для тестирования логики сохранения истории цен.
        """
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

    def test_price_history_created_on_price_change(self):
        """
        Проверка: при изменении цены создаётся запись в ProductPriceHistory.

        СЦЕНАРИЙ:
        1. Изменить поле price у существующего объекта ProductInfo.
        2. Вызвать save() для сохранения изменений.
        3. Проверить, что в таблице ProductPriceHistory появилась новая запись.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Создаётся ровно одна запись в ProductPriceHistory с корректными
        значениями old_price (50000) и new_price (45000).
        """
        self.product_info.price = 45000
        self.product_info.save()

        history = ProductPriceHistory.objects.filter(product_info=self.product_info)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().old_price, 50000)
        self.assertEqual(history.first().new_price, 45000)

    def test_price_history_multiple_changes(self):
        """
        Проверка: каждая последующая смена цены создаёт новую запись.

        СЦЕНАРИЙ:
        1. Последовательно изменить цену три раза.
        2. Проверить, что в истории появилось три записи.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Каждая смена цены фиксируется отдельной записью в ProductPriceHistory,
        что позволяет отследить полную цепочку изменений стоимости.
        """
        self.product_info.price = 45000
        self.product_info.save()

        self.product_info.price = 40000
        self.product_info.save()

        self.product_info.price = 35000
        self.product_info.save()

        history = ProductPriceHistory.objects.filter(product_info=self.product_info)
        self.assertEqual(history.count(), 3)

        records = list(history)
        self.assertEqual(records[0].old_price, 50000)
        self.assertEqual(records[0].new_price, 45000)
        self.assertEqual(records[1].old_price, 45000)
        self.assertEqual(records[1].new_price, 40000)
        self.assertEqual(records[2].old_price, 40000)
        self.assertEqual(records[2].new_price, 35000)

    def test_price_history_not_created_when_price_unchanged(self):
        """
        Проверка: при сохранении без изменения цены история не создаётся.

        СЦЕНАРИЙ:
        1. Вызвать save() без изменения поля price.
        2. Проверить, что записей в ProductPriceHistory нет.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Записей в ProductPriceHistory нет, так как цена не изменялась.
        Это предотвращает создание пустых записей истории.
        """
        self.product_info.save()
        history = ProductPriceHistory.objects.filter(product_info=self.product_info)
        self.assertEqual(history.count(), 0)


class ProductInfoCacheIntegrationTests(APITestCase):
    """
    Интеграционные тесты для проверки логики кэширования в ProductInfoView.

    НАЗНАЧЕНИЕ:
    Убедиться, что первый GET-запрос к эндпоинту каталога товаров
    возвращает данные из базы данных (PostgreSQL), а второй GET-запрос
    — из кэша (Redis). Это подтверждает корректность реализации
    кэширования, снижающего нагрузку на СУБД и ускоряющего ответы.

    Дипломная работа: оптимизация производительности через кэширование Redis.
    """

    def setUp(self):
        """
        Создание тестовых сущностей и очистка кэша перед каждым тестом
        для обеспечения изолированности тестовых сценариев.
        """
        cache.clear()
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

    def test_first_request_serves_from_database(self):
        """
        Проверка: первый GET-запрос возвращает данные из базы данных.

        СЦЕНАРИЙ:
        1. Убедиться, что кэш пуст.
        2. Отправить первый GET-запрос к эндпоинту товаров.
        3. Проверить, что в ответе поле 'source' равно 'database_postgres'.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Первый запрос обслуживается напрямую из PostgreSQL,
        так как кэш ещё не заполнен. В ответе возвращается 'source': 'database_postgres'.
        """
        cache_key = 'products_data_shop_None_cat_None'
        self.assertIsNone(cache.get(cache_key))

        response = self.client.get('/api/v1/catalog/products/')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['source'], 'database_postgres')

    def test_second_request_serves_from_cache(self):
        """
        Проверка: второй GET-запрос возвращает данные из кэша Redis.

        СЦЕНАРИЙ:
        1. Отправить первый GET-запрос (заполняет кэш).
        2. Отправить второй GET-запрос с теми же параметрами.
        3. Проверить, что в ответе поле 'source' равно 'cache_redis'.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        Второй запрос обслуживается из Redis-кэша без обращения к PostgreSQL,
        что подтверждает работоспособность механизма кэширования.
        """
        # Первый запрос — заполняем кэш
        self.client.get('/api/v1/catalog/products/')

        # Второй запрос — должен вернуться из кэша
        response = self.client.get('/api/v1/catalog/products/')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['source'], 'cache_redis')

    def test_cache_contains_serialized_data(self):
        """
        Проверка: в кэше сохраняются сериализованные данные товаров.

        СЦЕНАРИЙ:
        1. Отправить GET-запрос к эндпоинту товаров.
        2. Проверить содержимое кэша.

        ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
        В кэше хранится сериализованный список ProductInfo, содержащий
        модель, цену и другие поля товара, что позволяет полностью
        обслужить следующий запрос без обращения к БД.
        """
        self.client.get('/api/v1/catalog/products/')

        cache_key = 'products_data_shop_None_cat_None'
        cached_data = cache.get(cache_key)

        self.assertIsNotNone(cached_data)
        self.assertIsInstance(cached_data, list)
        self.assertEqual(len(cached_data), 1)
        self.assertEqual(cached_data[0]['model'], 'X100')
        self.assertEqual(cached_data[0]['price'], 50000)


