from typing import Type
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from catalog.models import ConfirmEmailToken, User
from shop.tasks import send_email

# Объявляем сигнал регистрации здесь
new_user_registered = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """ Отправляем письмо с токеном для сброса пароля через Celery """
    send_email.delay_on_commit(
        title=f"Password Reset Token for {reset_password_token.user}",
        message=reset_password_token.key,
        sender=settings.DEFAULT_FROM_EMAIL,
        recipients=[reset_password_token.user.email],
    )


@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """ Отправляем письмо с подтверждением почты при создании пользователя """
    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)

        send_email.delay_on_commit(
            title=f"Confirm Email Token for {instance.email}",
            message=token.key,
            sender=settings.DEFAULT_FROM_EMAIL,
            recipients=[instance.email],
        )