from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import JsonResponse
from django.db.models import Q
from django.urls import reverse
from requests import get
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_yaml.renderers import YAMLRenderer

from catalog.models import Shop, Category, ProductInfo, ConfirmEmailToken
from catalog.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer

from shop.tasks import update_partner_info, export_partner_info
from shop.celery import get_task
from catalog.signals import new_user_registered


class RegisterAccount(APIView):
    """
    Класс для регистрации покупателей и партнеров
    """
    def post(self, request, *args, **kwargs):
        # Проверяем обязательные аргументы
        required_fields = {'first_name', 'last_name', 'email', 'password', 'company', 'position'}
        if required_fields.issubset(request.data):

            # Проверяем пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = [str(item) for item in password_error]
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}}, status=400)

            # Валидация и создание пользователя через сериализатор
            user_serializer = UserSerializer(data=request.data)
            if user_serializer.is_valid():
                # Сохраняем пользователя ОДИН раз. Метод set_password уже встроен
                # в наш кастомный UserManager.create_user, который вызовется внутри сериализатора.
                user = user_serializer.save()

                # Вызываем сигнал регистрации (потребуется для отправки письма с токеном)
                new_user_registered.send(sender=self.__class__, user_id=user.id)

                return JsonResponse({'Status': True}, status=201)
            else:
                return JsonResponse({'Status': False, 'Errors': user_serializer.errors}, status=400)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса (активации аккаунта)
    """
    def post(self, request, *args, **kwargs):
        if {'email', 'token'}.issubset(request.data):
            token = ConfirmEmailToken.objects.filter(
                user__email=request.data['email'],
                key=request.data['token']
            ).first()

            if token:
                token.user.is_active = True
                token.user.save()
                token.delete() # Удаляем токен после успешного использования
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'}, status=400)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class AccountDetails(APIView):
    """
    Класс для просмотра и редактирования данных текущего пользователя
    """
    def get(self, request: Request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        # Если пользователь меняет пароль
        if 'password' in request.data:
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = [str(item) for item in password_error]
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}}, status=400)
            else:
                request.user.set_password(request.data['password'])
                request.user.save()

        # Проверяем остальные данные (частичное обновление partial=True)
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors}, status=400)


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей и выдачи Auth Token
    """
    def post(self, request, *args, **kwargs):
        if {'email', 'password'}.issubset(request.data):
            # Передаем email в качестве username, так как у нас USERNAME_FIELD = 'email'
            user = authenticate(request, username=request.data['email'], password=request.data['password'])

            if user is not None:
                if user.is_active:
                    # Генерируем или получаем существующий токен DRF
                    token, _ = Token.objects.get_or_create(user=user)
                    return JsonResponse({'Status': True, 'Token': token.key})
                else:
                    return JsonResponse({'Status': False, 'Errors': 'Аккаунт не активирован. Подтвердите Email.'}, status=403)

            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать. Неверный email или пароль.'}, status=400)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class CategoryView(ListAPIView):
    """ Класс для просмотра категорий """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """ Класс для просмотра списка активных магазинов """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
    Эндпоинт для поиска и фильтрации информации о товарах
    """
    def get(self, request: Request, *args, **kwargs):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # Оптимальная выборка связанных данных, чтобы база не висла от запросов
        queryset = ProductInfo.objects.filter(query).select_related(
            'shop', 'product__category'
        ).prefetch_related(
            'product_parameters__parameter'
        ).distinct()

        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class PartnerUpdate(APIView):
    """
    Эндпоинт для загрузки и обновления прайс-листа магазина из YAML-файла по URL (через Celery)
    """
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)}, status=400)
            else:
                # Скачиваем файл и передаем его в Celery на асинхронную обработку
                stream = get(url).content
                import_task = update_partner_info.delay(stream, request.user.id)

                return JsonResponse({'Status': True, 'task_id': import_task.task_id}, status=202)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class PartnerState(APIView):
    """
    Управление статусом работы магазина (принимает заказы / не принимает)
    """
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        # Выводим информацию о связанном с пользователем магазине
        shop = getattr(request.user, 'shop', None)
        if not shop:
            return JsonResponse({'Status': False, 'Error': 'Магазин не найден'}, status=404)

        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        state = request.data.get('state')
        if state is not None:
            # Безопасное приведение строки к булеву типу без устаревшего strtobool
            is_active = str(state).lower() in ['true', '1', 'yes', 'y']
            Shop.objects.filter(user_id=request.user.id).update(state=is_active)
            return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class PartnerExport(APIView):
    """
    Эндпоинт для запуска асинхронного экспорта каталога товаров магазина в формат YAML
    """
    renderer_classes = [YAMLRenderer]

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        # Запускаем Celery-таску на сборку прайса
        task = export_partner_info.delay(request.user.id)

        # backend:task-result — имя вашего будущего url-роута для проверки статуса задачи
        return JsonResponse({
            'Status': True,
            'task_id': task.task_id,
            'url': reverse('catalog:task-result')
        }, status=202)


class TaskResultView(APIView):
    """
    Эндпоинт для проверки статуса и получения результатов Celery-задач по task_id
    """
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        task_id = request.query_params.get('task_id')
        if not task_id:
            return JsonResponse({'Status': False, 'Errors': 'Не указан аргумент task_id'}, status=400)

        try:
            task = get_task(task_id)
        except Exception:
            return JsonResponse({'Status': False, 'Errors': 'Задача не найдена'}, status=404)

        if task.state == 'SUCCESS':
            return JsonResponse({'Status': True, 'Task state': task.state, 'Result': task.result})
        else:
            return JsonResponse({'Status': True, 'Task state': task.state, 'Result': str(task.result)})