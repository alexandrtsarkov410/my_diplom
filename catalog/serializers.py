import re

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from catalog.models import User, Category, Shop, Product, ProductInfo, ProductParameter, ProductPriceHistory


class UserSerializer(serializers.ModelSerializer):
    """ Сериализатор для работы с профилем пользователя """
    contacts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'company', 'position', 'type', 'contacts')
        read_only_fields = ('id',)

    def get_contacts(self, obj):
        from orders.serializers import ContactSerializer
        return ContactSerializer(obj.contacts.all(), many=True).data

    def validate_password(self, value: str) -> str:
        """
        Валидатор паролей на соответствие корпоративным политикам безопасности.

        КРИТЕРИИ ПРОВЕРКИ:
        - Минимальная длина: 12 символов.
        - Обязательное наличие строчных и заглавных латинских букв.
        - Обязательное наличие хотя бы одной цифры.
        - Обязательное наличие спецсимвола (!@#$%^&* и т.д.).
        """
        if len(value) < 12:
            raise ValidationError("Пароль слишком короткий (не менее 12 символов).")
        if not re.search(r"[a-z]", value) or not re.search(r"[A-Z]", value):
            raise ValidationError("Пароль должен содержать заглавные и строчные буквы.")
        if not re.search(r"\d", value):
            raise ValidationError("Пароль должен содержать хотя бы одну цифру.")
        if not re.search(r"[ !@#$%^&*(),.?\":{}|<>_+-]", value):
            raise ValidationError("Пароль должен содержать спецсимвол.")
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name',)
        read_only_fields = ('id',)


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'state',)
        read_only_fields = ('id',)


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = ('name', 'category',)


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value',)


class ProductPriceHistorySerializer(serializers.ModelSerializer):
    """
    Сериализатор для представления истории цен товара.
    """
    class Meta:
        model = ProductPriceHistory
        fields = ('old_price', 'new_price', 'changed_at')


class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)
    price_history = ProductPriceHistorySerializer(many=True, read_only=True)  # Добавляем поле

    class Meta:
        model = ProductInfo
        fields = ('id', 'model', 'product', 'shop', 'quantity', 'price', 'price_rrc', 'product_parameters',)
        read_only_fields = ('id',)


class ProductInfoExportSerializer(serializers.ModelSerializer):
    """ Удобная выгрузка информации о товаре """
    category = serializers.CharField(source='product.category.name', read_only=True)
    name = serializers.CharField(source='product.name', read_only=True)
    parameters = serializers.SerializerMethodField()

    class Meta:
        model = ProductInfo
        fields = ('id', 'category', 'model', 'name', 'price', 'price_rrc', 'quantity', 'parameters')

    def get_parameters(self, obj):
        return {param.parameter.name: param.value for param in obj.product_parameters.all()}


class ShopExportSerializer(serializers.ModelSerializer):
    """ Выгрузка всего прайса конкретного магазина """
    shop = serializers.CharField(source='name', read_only=True)
    goods = ProductInfoExportSerializer(source='product_infos', read_only=True, many=True)

    class Meta:
        model = Shop
        fields = ('shop', 'goods')