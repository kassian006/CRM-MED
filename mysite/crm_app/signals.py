import random
from django.core.mail import send_mail
from django_rest_passwordreset.signals import reset_password_token_created
from django.dispatch import receiver


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    # Генерация случайного 4-значного кода
    reset_code = random.randint(1000, 9999)

    # Сохраняем код в поле key токена
    reset_password_token.key = str(reset_code)
    reset_password_token.save()

    # Текст сообщения
    email_plaintext_message = f"Ваш код для сброса пароля: {reset_code}"

    # Отправка email
    send_mail(
        "Сброс пароля",  # Тема письма
        email_plaintext_message,  # Текст письма
        "noreply@somehost.local",  # От кого
        [reset_password_token.user.email],  # Список получателей
        fail_silently=False,
    )
