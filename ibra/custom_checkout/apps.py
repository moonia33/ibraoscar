# custom_checkout/apps.py
from oscar.apps.checkout.apps import CheckoutConfig


class CustomCheckoutConfig(CheckoutConfig):
    name = 'custom_checkout'
