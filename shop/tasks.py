from celery import shared_task
from celery.contrib.django.task import DjangoTask
from django.core.mail import EmailMultiAlternatives
from yaml import load as load_yaml, Loader


from catalog.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter
from catalog.serializers import ShopExportSerializer


@shared_task(base=DjangoTask)
def send_email(title, message, sender, recipients):
    """ Асинхронная отправка email через Django mail backend """
    msg = EmailMultiAlternatives(
        title,
        message,
        sender,
        recipients
    )
    msg.send()


@shared_task
def update_partner_info(stream, user_id):
    """
    Парсинг YAML-файла от магазина-поставщика.
    Автоматически обновляет категории, товары, цены и параметры в БД.
    """
    # Загружаем поток данных YAML
    data = load_yaml(stream, Loader=Loader)

    # Находим или создаем магазин, привязанный к текущему пользователю
    shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user_id)

    # Заполняем категории и связываем их с магазином
    for category in data['categories']:
        category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
        category_object.shops.add(shop.id)
        category_object.save()

    # Очищаем старый прайс-лист этого магазина перед загрузкой нового
    ProductInfo.objects.filter(shop_id=shop.id).delete()

    # Проходим по списку товаров (goods)
    for item in data['goods']:
        product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

        # Создаем детальную информацию о продукте на складе магазина
        product_info = ProductInfo.objects.create(
            product_id=product.id,
            external_id=item['id'],
            model=item['model'],
            price=item['price'],
            price_rrc=item['price_rrc'],
            quantity=item['quantity'],
            shop_id=shop.id
        )

        # Перебираем и сохраняем специфические характеристики товара (Цвет, Память и т.д.)
        for name, value in item['parameters'].items():
            parameter_object, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.create(
                product_info_id=product_info.id,
                parameter_id=parameter_object.id,
                value=value
            )


@shared_task
def export_partner_info(user_id):
    """ Асинхронный экспорт информации о прайс-листе магазина для партнера """
    shop = Shop.objects.filter(user_id=user_id).first()
    serializer = ShopExportSerializer(shop)
    return serializer.data