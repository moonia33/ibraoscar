from django.shortcuts import render
from payments.montonio import get_payment_methods


def payment_details_view(request):
    payment_methods_data = get_payment_methods()

    if payment_methods_data is None:
        return render(request, 'oscar/checkout/payment_error.html', {"message": "Unable to fetch payment methods"})

    # Filtruojame pagal šalį, tarkime Lietuvą (LT)
    payment_methods = payment_methods_data.get('paymentMethods', {}).get(
        'paymentInitiation', {}).get('setup', {}).get('LT', {}).get('paymentMethods', [])

    # Renderiname `payment_details.html`, o ne `payment_methods.html`
    return render(request, 'oscar/checkout/payment_details.html', {
        'payment_methods': payment_methods,
    })
