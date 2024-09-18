import jwt
import datetime
from django.conf import settings


def generate_montonio_token():
    """
    Sugeneruoja JWT tokeną autentifikacijai Montonio API.
    """
    payload = {
        'accessKey': settings.MONTONIO_ACCESS_KEY,
        'exp': datetime.datetime.now() + datetime.timedelta(minutes=10),
    }
    token = jwt.encode(
        payload, settings.MONTONIO_SECRET_KEY, algorithm='HS256')
    return token
