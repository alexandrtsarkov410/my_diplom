from django.conf import settings
from django.dispatch import receiver, Signal

from catalog.models import User
from shop.tasks import send_email


new_order = Signal()


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """ Отправляем письмо покупателю, что его заказ сформирован """
    user = User.objects.get(id=user_id)

    send_email.delay_on_commit(
        title="Обновление статуса заказа",
        message='Заказ сформирован',
        sender=settings.DEFAULT_FROM_EMAIL,
        recipients=[user.email],
    )