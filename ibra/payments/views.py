import json
from oscar.apps.checkout.views import PaymentDetailsView
from payments.montonio import MontonioPayment
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
import jwt
from django.conf import settings
from oscar.apps.order.models import Order
from oscar.core.loading import get_class
from django.urls import reverse

OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class CustomPreviewView(PaymentDetailsView):
    """
    Mokėjimų peržiūros vaizdas, kur vyksta banko pasirinkimas ir mokėjimo įvykdymas.
    """
    preview = True

    def get_template_names(self):
        """
        Nustatome teisingą šabloną, jei jis nėra nurodytas tiesiogiai.
        """
        return ["oscar/checkout/preview.html"]

    def get_context_data(self, **kwargs):
        """
        Pridedame Montonio mokėjimo būdus į kontekstą.
        """
        context = super().get_context_data(**kwargs)
        montonio_payment = MontonioPayment()
        context['payment_methods'] = montonio_payment.get_payment_methods(
            'LT')  # Šalies kodas „LT“

        # Gauname pasirinkto banko kodą iš sesijos
        selected_bank_code = self.request.session.get(
            'selected_bank_code', None)
        context['selected_bank_code'] = selected_bank_code

        return context

    def post(self, request, *args, **kwargs):
        """
        Užsakymo pateikimas su Montonio integracija arba banko pasirinkimas.
        """
        selected_bank_code = request.POST.get('selected_bank_code')
        if not selected_bank_code:
            messages.error(request, "Prašome pasirinkti banką.")
            return self.render_to_response(self.get_context_data())

        # Išsaugome pasirinktą banko kodą į sesiją
        request.session['selected_bank_code'] = selected_bank_code
        request.session.modified = True  # Pažymime, kad sesija pakeista

        # Sukuriame užsakymo pateikimo duomenų rinkinį (submission)
        submission = self.build_submission()

        # Sugeneruojame užsakymo numerį
        order_number = OrderNumberGenerator(
        ).order_number(submission['basket'])

        # Paruošiame užsakymo duomenis Montonio API
        order_data = {
            'number': order_number,
            'basket_total': submission['order_total'].incl_tax,
            'basket': submission['basket'],
        }

        montonio_payment = MontonioPayment()
        return_url = self.request.build_absolute_uri('/checkout/thank-you/')
        notification_url = self.request.build_absolute_uri('/checkout/notify/')

        # Sukuriame užsakymą Montonio API sistemoje
        result = montonio_payment.create_order(
            order_data,
            return_url,
            notification_url,
            selected_bank_code
        )

        if 'paymentUrl' in result:
            print(f"Redirecting to: {result['paymentUrl']}")
            # Užšaldome krepšelį (basket freeze)
            submission['basket'].freeze()
            return redirect(result['paymentUrl'])
        else:
            print(f"Error in Montonio response: {result}")
            messages.error(
                request, "Klaida kuriant užsakymą Montonio sistemoje.")
            return self.render_preview(request)


@csrf_exempt
def montonio_payment_notification(request):
    """
    Montonio webhook'as, skirtas pranešti apie mokėjimo būseną.
    """
    # Pirmiausia išskaitome JSON duomenis iš kūno
    try:
        data = json.loads(request.body)
        token = data.get('orderToken')  # Gauname 'orderToken' iš JSON objekto
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
    except jwt.InvalidTokenError:
        return JsonResponse({'error': 'Invalid token'}, status=400)
