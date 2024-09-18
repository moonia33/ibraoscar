import requests
from django.conf import settings
from .utils import generate_montonio_token


def get_payment_methods():
    """
    Gauna galimus mokėjimo metodus iš Montonio API.
    """
    token = generate_montonio_token()
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(
        f'{settings.MONTONIO_API_URL}/stores/payment-methods', headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f'Unable to fetch payment methods: {response.status_code}')


def create_montonio_order(order_data):
    """
    Sukuria užsakymą Montonio API.
    """
    token = generate_montonio_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    response = requests.post(
        f'{settings.MONTONIO_API_URL}/orders', json={'data': token}, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f'Unable to create Montonio order: {response.status_code}')
