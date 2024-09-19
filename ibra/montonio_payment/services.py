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


def get_bank_name_by_code(selected_bank_code):
    payment_methods = get_payment_methods()  # Gaukime visus mokėjimo metodus
    print(f"Payment methods response: {payment_methods}")  # Debugging

    # Patikriname, ar egzistuoja 'LT' šalies duomenys
    if 'paymentMethods' not in payment_methods or 'LT' not in payment_methods['paymentMethods']['paymentInitiation']['setup']:
        return "Montonio"

    # Filtruojame pagal LT šalį
    lt_methods = payment_methods['paymentMethods']['paymentInitiation']['setup']['LT']['paymentMethods']
    print(f"Payment LT methods response: {lt_methods}")
    # Naršome per visus LT mokėjimo metodus ir tikriname kodą
    for method in lt_methods:
        if method['code'] == selected_bank_code:
            return method['name']
            # Grąžiname banko pavadinimą
        # print(method['name'])

    return "Montonio"  # Jei banko kodas nerastas, grąžiname "Montonio"


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
            f'Unable to create Montonio order: {response.status_code}, {response.text}')
