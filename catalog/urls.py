from django.urls import path
from django_rest_passwordreset.views import reset_password_request_token, reset_password_confirm

from catalog.views import (
    RegisterAccount, ConfirmAccount, AccountDetails, LoginAccount,
    CategoryView, ShopView, ProductInfoView, PartnerState, PartnerUpdate,
    PartnerExport, TaskResultView
)

app_name = 'catalog'

urlpatterns = [
    path('user/register/', RegisterAccount.as_view(), name='user-register'),
    path('user/register/confirm/', ConfirmAccount.as_view(), name='user-register-confirm'),
    path('user/details/', AccountDetails.as_view(), name='user-details'),
    path('user/login/', LoginAccount.as_view(), name='user-login'),
    path('user/password_reset/', reset_password_request_token, name='password-reset'),
    path('user/password_reset/confirm/', reset_password_confirm, name='password-reset-confirm'),
    path('categories/', CategoryView.as_view(), name='categories'),
    path('shops/', ShopView.as_view(), name='shops'),
    path('products/', ProductInfoView.as_view(), name='products'),
    path('partner/state/', PartnerState.as_view(), name='partner-state'),
    path('partner/update/', PartnerUpdate.as_view(), name='partner-update'),
    path('partner/export/', PartnerExport.as_view(), name='partner-export'),
    path('task_result/', TaskResultView.as_view(), name='task-result'),
]