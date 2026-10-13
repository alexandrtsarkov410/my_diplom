from django.urls import path

from orders.views import BasketView, ContactView, OrderView, PartnerOrders

app_name = 'orders'

urlpatterns = [
    path('user/contact/', ContactView.as_view(), name='user-contact'),
    path('basket/', BasketView.as_view(), name='basket'),
    path('order/', OrderView.as_view(), name='order'),
    path('partner/orders/', PartnerOrders.as_view(), name='partner-orders'),
]