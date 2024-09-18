import jwt
import datetime
import requests
from django.conf import settings


class MontonioPayment:
    """
    Montonio API integracija, apdorojimas ir komunikacija su Montonio API.
    """

    def create_jwt_token(self, payload):
        """
        Sukuria JWT tokeną naudojant užsakymo duomenis.
        """
        token = jwt.encode(
            payload, settings.MONTONIO_SECRET_KEY, algorithm='HS256')
        return token

    def get_payment_methods(self):
        """
        Gauna visus galimus mokėjimo metodus iš Montonio API.
        """
        api_url = f"{settings.MONTONIO_API_URL}/stores/payment-methods"
        payload = {
            'accessKey': settings.MONTONIO_ACCESS_KEY,
            'exp': datetime.datetime.now() + datetime.timedelta(minutes=10)
        }
        token = self.create_jwt_token(payload)

        headers = {
            'Authorization': f'Bearer {token}'
        }

        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            return response.json().get('paymentMethods', {})
        else:
            raise ValueError(
                f"Klaida gaunant mokėjimo metodus: {response.status_code}")

    def create_order(self, order_data, return_url, notification_url):
        """
        Sukuria užsakymą Montonio API ir nukreipia klientą į mokėjimo puslapį.
        """
        api_url = f"{settings.MONTONIO_API_URL}/orders"
        payload = {
            'accessKey': settings.MONTONIO_ACCESS_KEY,
            'merchantReference': order_data['number'],
            'grandTotal': order_data['basket_total'],
            'currency': 'EUR',
            'returnUrl': return_url,
            'notificationUrl': notification_url,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
            'payment': {
                'method': 'paymentInitiation',
                'amount': order_data['basket_total'],
                'currency': 'EUR',
                'methodOptions': {
                    'preferredProvider': order_data.get('preferred_bank_code'),
                    'preferredCountry': 'LT'
                }
            },
            'billingAddress': order_data['billing_address'],
            'shippingAddress': order_data['shipping_address'],
            'lineItems': order_data['items']
        }
        token = self.create_jwt_token(payload)

        response = requests.post(api_url, json={'data': token})
        if response.status_code == 201:
            return response.json()
        else:
            raise ValueError(
                f"Klaida siunčiant užsakymą Montonio API: {response.status_code}")
