from django.contrib import admin
from django.http import HttpRequest
from django.db.models import F, Sum

from orders.models import Contact, Order, OrderItem, OrderByShop


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    pass


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    pass


# list of items in order
class OrderItemsInline(admin.TabularInline):
    model = OrderItem
    fields = ('product_info', 'get_product_shop', 'get_product_price', 'quantity')
    readonly_fields = fields
    can_delete = False

    @admin.display(description='Цена при заказе')
    def get_product_price(self, obj):
        return obj.price if obj.price > 0 else obj.product_info.price

    @admin.display(description='Магазин')
    def get_product_shop(self, obj):
        return obj.product_info.shop

    # disable to add order items
    def has_add_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    # disable to edit order items
    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    # enable shop users to view order items
    def has_view_permission(self, request: HttpRequest, obj=None) -> bool:
        if (request.user.is_superuser) or (request.user.type == 'shop'):
            return True
        return super().has_view_permission(request, obj)

# list of orders for shop
@admin.register(OrderByShop)
class OrderForShopAdmin(admin.ModelAdmin):
    inlines = [OrderItemsInline, ]
    list_display = ('dt', 'state', 'user', 'contact', 'total_sum')
    readonly_fields = ('dt', 'user', 'contact', 'total_sum')

    # order total sum
    def total_sum(self, obj):
        total_sum = obj.ordered_items.aggregate(total_sum=Sum(F('quantity') * F('price')))
        return total_sum.get('total_sum') or 0
    total_sum.short_description = 'Суммa заказа'

    # for shop user show only created orders with items from user's shop
    # (hide orders in state 'basket')
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.exclude(state='basket').filter(id__in=OrderItem.objects.filter(product_info__shop__user=request.user).values('order__id'))

    # enable shop users to view orders
    def has_view_permission(self, request: HttpRequest, obj=None) -> bool:
        if (request.user.is_superuser) or (request.user.type == 'shop'):
            return True
        return super().has_view_permission(request, obj)

    # enable shop users to change orders (only its state - see readonly fields above)
    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        if (request.user.is_superuser) or (request.user.type == 'shop'):
            return True
        return super().has_change_permission(request, obj)

    # show model in Django admin's model list for shop users
    def has_module_permission(self, request: HttpRequest) -> bool:
        if (request.user.is_superuser) or (request.user.type == 'shop'):
            return True
        return super().has_module_permission(request)