from django.shortcuts import render
from .montonio import get_payment_methods


def payment_methods_view(request):
    payment_methods_data = get_payment_methods()

    country_code = request.GET.get('country', 'LT')  # Default to Lithuania
    payment_methods = payment_methods_data['paymentMethods']['paymentInitiation']['setup'].get(
        country_code, {}).get('paymentMethods', [])

    return render(request, 'payments/payment_methods.html', {'payment_methods': payment_methods})
