import jwt
import datetime
from django.conf import settings


def generate_montonio_basic_token():
    """
    Sugeneruoja JWT tokeną autentifikacijai Montonio API be užsakymo duomenų.
    """
    payload = {
        'accessKey': settings.MONTONIO_ACCESS_KEY,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    }

    token = jwt.encode(
        payload, settings.MONTONIO_SECRET_KEY, algorithm='HS256')
    return token


def generate_montonio_token(order_data):
    """
    Sugeneruoja JWT tokeną su užsakymo duomenimis Montonio API.
    """
    payload = {
        'accessKey': settings.MONTONIO_ACCESS_KEY,
        'merchantReference': order_data['merchantReference'],
        'returnUrl': order_data['returnUrl'],
        'notificationUrl': order_data['notificationUrl'],
        'currency': order_data['currency'],
        'grandTotal': order_data['grandTotal'],
        'locale': order_data['locale'],
        'payment': order_data['payment'],
        'exp': datetime.datetime.now() + datetime.timedelta(minutes=10)
    }

    token = jwt.encode(
        payload, settings.MONTONIO_SECRET_KEY, algorithm='HS256'
    )
    return token
