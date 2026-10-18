import json
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Contact, Order, OrderItem, STATE_CHOICES
from orders.serializers import ContactSerializer, OrderItemSerializer, OrderSerializer

from shop.tasks import send_email
from orders.signals import new_order


class BasketView(APIView):
    """
    Класс для управления корзиной пользователя (Просмотр, добавление, изменение, удаление)
    """

    def get(self, request: Request, *args, **kwargs):
        """ Получить все позиции в корзине текущего пользователя """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        basket = Order.objects.filter(
            user_id=request.user.id, state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__price'))
        ).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs):
        """ Добавить товары в корзину """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if items_string:
            try:
                # Используем стандартный json для безопасности сборки
                items_dict = json.loads(items_string) if isinstance(items_string, str) else items_string
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'}, status=400)
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_created = 0

                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors': str(error)}, status=400)
                        else:
                            objects_created += 1
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)

                return JsonResponse({'Status': True, 'Создано объектов': objects_created}, status=201)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

    def put(self, request: Request, *args, **kwargs):
        """ Изменить количество товара в корзине """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if items_string:
            try:
                items_dict = json.loads(items_string) if isinstance(items_string, str) else items_string
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'}, status=400)
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0

                for order_item in items_dict:
                    if isinstance(order_item.get('id'), int) and isinstance(order_item.get('quantity'), int):
                        objects_updated += OrderItem.objects.filter(
                            order_id=basket.id,
                            id=order_item['id']
                        ).update(quantity=order_item['quantity'])

                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

    def delete(self, request: Request, *args, **kwargs):
        """ Удалить товары из корзины """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if items_string:
            # Парсим элементы (могут прийти строкой "1,2,3" или списком)
            items_list = items_string.split(',') if isinstance(items_string, str) else items_string
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            objects_deleted = False

            for order_item_id in items_list:
                if str(order_item_id).isdigit():
                    query = query | Q(order_id=basket.id, id=int(order_item_id))
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class PartnerOrders(APIView):
    """
    Эндпоинт для работы магазина со своими заказами (Просмотр и изменение статусов)
    """
    def get(self, request: Request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        orders = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id
        ).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__price'))
        ).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def put(self, request: Request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        if not {'id', 'state'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

        order_id = request.data.get('id')
        new_state = request.data.get('state')

        # Валидация нового статуса по списку разрешенных значений
        if new_state:
            if not (any(new_state == state[0] for state in STATE_CHOICES) and new_state != 'basket'):
                return JsonResponse({'Status': False, 'Errors': 'Указан недопустимый статус заказа'}, status=400)

        order = Order.objects.filter(id=order_id).first()
        if not order:
            return JsonResponse({'Status': False, 'Error': 'Заказ не найден'}, status=404)

        order.state = new_state
        order.save()

        # Отправляем уведомление клиенту об изменении статуса его заказа
        send_email.delay(
            title=f'Обновление статуса заказа № {order_id}',
            message=f'Новый статус вашего заказа: {dict(STATE_CHOICES).get(order.state)}',
            sender=settings.DEFAULT_FROM_EMAIL,
            recipients=[order.user.email],
        )

        return JsonResponse({'Status': True})


class ContactView(APIView):
    """
    Класс для управления контактами (адресами доставки) пользователя
    """

    def get(self, request: Request, *args, **kwargs):
        """ Получить список контактов текущего пользователя """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        contacts = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs):
        """ Добавить новый контакт """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'city', 'street', 'phone'}.issubset(request.data):
            serializer = ContactSerializer(data=request.data, context={'request': request})

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True}, status=201)
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

    def put(self, request: Request, *args, **kwargs):
        """ Редактировать существующий контакт """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        contact_id = request.data.get('id')
        if contact_id and str(contact_id).isdigit():
            contact = Contact.objects.filter(id=int(contact_id), user_id=request.user.id).first()
            if contact:
                serializer = ContactSerializer(contact, data=request.data, partial=True, context={'request': request})
                if serializer.is_valid():
                    serializer.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)
            return JsonResponse({'Status': False, 'Error': 'Контакт не найден'}, status=404)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

    def delete(self, request: Request, *args, **kwargs):
        """ Удалить контакт(ы) """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if items_string:
            items_list = items_string.split(',') if isinstance(items_string, str) else items_string
            query = Q()
            objects_deleted = False

            for contact_id in items_list:
                if str(contact_id).isdigit():
                    query = query | Q(user_id=request.user.id, id=int(contact_id))
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class OrderView(APIView):
    """
    Класс для получения истории заказов и размещения заказа из корзины покупателем
    """

    def get(self, request: Request, *args, **kwargs):
        """ Получить список всех оформленных заказов (кроме корзины) """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        orders = Order.objects.filter(
            user_id=request.user.id
        ).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__price'))
        ).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs):
        """ Оформить (разместить) заказ из корзины """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'id', 'contact'}.issubset(request.data):
            order_id = request.data.get('id')
            contact_id = request.data.get('contact')

            if str(order_id).isdigit():
                try:
                    # Переводим заказ из статуса корзины ('basket') в статус нового заказа ('new')
                    is_updated = Order.objects.filter(
                        user_id=request.user.id,
                        id=int(order_id),
                        state='basket'
                    ).update(
                        contact_id=contact_id,
                        state='new'
                    )
                except IntegrityError:
                    return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'}, status=400)
                else:
                    if is_updated:
                        # Отправляем сигнал о создании нового заказа (для отправки писем через Celery)
                        new_order.send(sender=self.__class__, user_id=request.user.id)
                        return JsonResponse({'Status': True})
                    return JsonResponse({'Status': False, 'Error': 'Корзина с таким ID не найдена'}, status=404)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)