from rest_framework import serializers
from catalog.models import User, Category, Shop, Product, ProductInfo, ProductParameter


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


class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)

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