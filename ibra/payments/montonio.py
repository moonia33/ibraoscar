import jwt
from datetime import datetime, timedelta
import requests
from django.conf import settings


class MontonioPayment:
    def __init__(self):
        self.api_url = settings.MONTONIO_API_URL
        self.access_key = settings.MONTONIO_ACCESS_KEY
        self.secret_key = settings.MONTONIO_SECRET_KEY

    def get_auth_header(self):
        """
        Sukuriame JWT autentifikacijos header'į.
        """
        payload = {
            'accessKey': self.access_key,
            'iat': datetime.now(),
            'exp': datetime.now() + timedelta(hours=1)
        }
        auth_header = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return auth_header

    def get_payment_methods(self, country_code='EE'):
        """
        Gauti galimus mokėjimo būdus pagal šalies kodą.
        """
        auth_header = self.get_auth_header()
        url = f"{self.api_url}/stores/payment-methods"
        headers = {
            'Authorization': f'Bearer {auth_header}',
            'Content-Type': 'application/json',
        }
        params = {
            'countryCode': country_code
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("paymentMethods", {})
        else:
            print(f"Error fetching payment methods: {response.status_code}")
            return None

    def create_order(self, order_data, return_url, notification_url, selected_bank_code):
        """
        Sukuriame užsakymą Montonio sistemoje ir perduodame pasirinktą banką.
        """
        if not order_data.get('number') or not order_data.get('basket_total'):
            raise ValueError("Trūksta užsakymo duomenų.")

        payload = {
            'accessKey': self.access_key,
            'merchantReference': str(order_data['number']),
            'returnUrl': return_url,
            'notificationUrl': notification_url,
            'currency': 'EUR',
            'grandTotal': float(order_data['basket_total']),
            'locale': 'lt',
            'payment': {
                'method': 'paymentInitiation',
                'amount': float(order_data['basket_total']),
                'currency': 'EUR',
                'methodOptions': {
                    'preferredProvider': selected_bank_code,
                }
            },
            'exp': datetime.utcnow() + timedelta(minutes=10)
        }

        token = jwt.encode(payload, self.secret_key, algorithm='HS256')

        response = requests.post(
            f"{self.api_url}/orders", json={'data': token})

        # Diagnostikos tikslams išspausdinsime atsakymą
        print(f"Montonio API response status: {response.status_code}")
        print(f"Montonio API response content: {response.text}")

        if response.status_code == 200:
            return response.json()
        else:
            # Jei gauname klaidą, grąžiname pranešimą
            return {'error': f"Klaida Montonio API užklausoje: {response.status_code}", 'details': response.json()}
