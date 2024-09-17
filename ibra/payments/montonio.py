import jwt
from datetime import datetime, timedelta
import requests
from django.conf import settings  # Importuojame Django nustatymus


def get_auth_header():
    access_key = settings.MONTONIO_ACCESS_KEY  # Paimame iš settings
    secret_key = settings.MONTONIO_SECRET_KEY  # Paimame iš settings

    payload = {
        'accessKey': access_key,
        'iat': datetime.now(),
        'exp': datetime.now() + timedelta(hours=1)  # Token galiojimas 1 valandą
    }

    auth_header = jwt.encode(payload, secret_key, algorithm='HS256')
    return auth_header


def get_payment_methods(country_code='EE'):
    auth_header = get_auth_header()
    # Naudojame sandbox arba production URL
    url = f"{settings.MONTONIO_API_URL}/stores/payment-methods"
    headers = {
        'Authorization': f'Bearer {auth_header}',
        'Content-Type': 'application/json',
    }
    params = {
        'countryCode': country_code  # Filtruojame pagal šalį
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()  # Grąžiname mokėjimo būdus
    else:
        print(f"Error fetching payment methods: {response.status_code}")
        return None


# Pavyzdys, kaip gauti mokėjimo būdus:
payment_methods = get_payment_methods('LT')
print(payment_methods)
