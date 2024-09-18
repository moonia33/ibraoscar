import json
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
import jwt
from oscar.apps.checkout.views import PaymentDetailsView
from oscar.apps.order.models import Order
from oscar.core.loading import get_class
from payments.montonio import MontonioPayment

OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class CustomPreviewView(PaymentDetailsView):
    """
    Vaizdas, kuriame vartotojas pasirenka mokėjimo būdą ir pateikia užsakymą.
    """
    preview = True

    def get_template_names(self):
        return ["oscar/checkout/preview.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        montonio_payment = MontonioPayment()
        context['payment_methods'] = montonio_payment.get_payment_methods()
        context['selected_bank_code'] = self.request.session.get(
            'selected_bank_code')
        return context

    def post(self, request, *args, **kwargs):
        selected_bank_code = request.POST.get('selected_bank_code')
        if not selected_bank_code:
            messages.error(request, "Prašome pasirinkti banką.")
            return self.render_to_response(self.get_context_data())

        request.session['selected_bank_code'] = selected_bank_code
        submission = self.build_submission()

        order_number = OrderNumberGenerator(
        ).order_number(submission['basket'])
        order_data = {
            'number': order_number,
            'basket_total': submission['order_total'].incl_tax,
            'preferred_bank_code': selected_bank_code,
            'billing_address': submission['billing_address'],
            'shipping_address': submission['shipping_address'],
            'items': [{
                'name': line.product.title,
                'quantity': line.quantity,
                'finalPrice': line.line_price_incl_tax
            } for line in submission['basket'].all_lines()]
        }

        montonio_payment = MontonioPayment()
        return_url = self.request.build_absolute_uri('/checkout/thank-you/')
        notification_url = self.request.build_absolute_uri('/checkout/notify/')

        try:
            result = montonio_payment.create_order(
                order_data, return_url, notification_url)
            if 'paymentUrl' in result:
                submission['basket'].freeze()
                return redirect(result['paymentUrl'])
            else:
                messages.error(
                    request, "Klaida kuriant užsakymą Montonio sistemoje.")
                return self.render_to_response(self.get_context_data())
        except Exception as e:
            messages.error(request, f"Klaida: {str(e)}")
            return self.render_to_response(self.get_context_data())


@csrf_exempt
def montonio_payment_notification(request):
    """
    Webhook'as iš Montonio, skirtas pranešti apie mokėjimo būseną.
    """
    try:
        data = json.loads(request.body)
        token = data.get('orderToken')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid JSON or missing orderToken'}, status=400)

    if not token:
        return JsonResponse({'error': 'Missing order token'}, status=400)

    try:
        decoded_token = jwt.decode(
            token, settings.MONTONIO_SECRET_KEY, algorithms=['HS256'])
        if decoded_token.get('paymentStatus') == 'PAID':
            order_number = decoded_token.get('merchantReference')
            order = Order.objects.get(number=order_number)
            order.set_status('PAID')
            return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'failed'}, status=400)
    except (jwt.InvalidTokenError, Order.DoesNotExist):
        return JsonResponse({'error': 'Invalid token or order not found'}, status=400)
