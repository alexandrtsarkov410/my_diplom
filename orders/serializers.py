from rest_framework import serializers
from django.db.models import Sum, F
from orders.models import Contact, Order, OrderItem
from catalog.serializers import ProductInfoSerializer


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure', 'building', 'apartment', 'user', 'phone')
        read_only_fields = ('id',)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity', 'order', 'price')
        read_only_fields = ('id',)
        extra_kwargs = {
            'order': {'write_only': True}
        }


class OrderItemCreateSerializer(OrderItemSerializer):
    product_info = ProductInfoSerializer(read_only=True)


class OrderSerializer(serializers.ModelSerializer):
    ordered_items = OrderItemCreateSerializer(read_only=True, many=True)
    contact = ContactSerializer(read_only=True)
    total_sum = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('id', 'ordered_items', 'state', 'dt', 'total_sum', 'contact',)
        read_only_fields = ('id',)

    def get_total_sum(self, obj):
        """ Динамический расчет общей стоимости заказа по зафиксированным ценам """
        total = obj.ordered_items.aggregate(total_sum=Sum(F('quantity') * F('price')))
        return total.get('total_sum') or 0
