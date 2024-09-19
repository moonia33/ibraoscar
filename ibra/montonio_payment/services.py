import requests
from django.conf import settings
from .utils import generate_montonio_basic_token, generate_montonio_token


def get_payment_methods():
    """
    Gauna galimus mokėjimo metodus iš Montonio API.
    """
    try:
        token = generate_montonio_basic_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        response = requests.get(
            f'{settings.MONTONIO_API_URL}/stores/payment-methods', headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f'Unable to fetch payment methods: {response.status_code}, {response.text}')
    except Exception as e:
        raise Exception(f"Klaida gaunant mokėjimo būdus: {str(e)}")


def create_montonio_order(order_data):
    """
    Sukuria užsakymą Montonio API.
    """
    token = generate_montonio_token(
        order_data)  # Sugeneruojame JWT tokeną su užsakymo duomenimis
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    response = requests.post(
        f'{settings.MONTONIO_API_URL}/orders',
        json={'data': token},  # Montonio API laukia, kad 'data' būtų tokenas
        headers=headers
    )

    print(f"Montonio API atsakymas: {response.status_code}, {response.text}")
    if response.status_code in [200, 201]:
        return response.json()
    else:
        raise Exception(
            f'Unable to create Montonio order: {response.status_code}, {response.text}'
        )
