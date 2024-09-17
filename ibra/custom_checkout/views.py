from django.shortcuts import redirect
from oscar.apps.checkout.views import PaymentDetailsView, PreviewView
from payments.montonio import MontonioPayment
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import jwt
from django.conf import settings
from oscar.apps.order.models import Order

# Mokėjimo būdų pasirinkimas ir mokėjimo detalės (payment-details žingsnis)


class CustomPaymentDetailsView(PaymentDetailsView):
    """
    Vartotojo mokėjimo būdo pasirinkimas ir mokėjimo suvestinės vaizdas.
    """

    def get_context_data(self, **kwargs):
        """
        Pridedame Montonio mokėjimo būdus į kontekstą.
        """
        context = super().get_context_data(**kwargs)
        montonio_payment = MontonioPayment()
        context['payment_methods'] = montonio_payment.get_payment_methods(
            'LT')  # LT šalies kodas, gali keistis
        return context

    def post(self, request, *args, **kwargs):
        """
        Išsaugome vartotojo pasirinktą banką ir tęsiame mokėjimo procesą.
        """
        selected_bank_code = request.POST.get('selected_bank_code')
        if not selected_bank_code:
            self.add_payment_error("Prašome pasirinkti banką.")
            return self.render_to_response(self.get_context_data())

        # Išsaugome banko kodą sesijoje
        self.checkout_session.set_payment_method(
            'selected_bank_code', selected_bank_code)
        return redirect('checkout:preview')


# Užsakymo suvestinė ir patvirtinimas (preview žingsnis)
class CustomPreviewView(PreviewView):
    """
    Apdorojame užsakymo suvestinę ir atvaizduojame pasirinktą banko mokėjimo būdą.
    """

    def get_context_data(self, **kwargs):
        """
        Įtraukiame pasirinkto mokėjimo būdo informaciją į kontekstą.
        """
        context = super().get_context_data(**kwargs)
        # Gauname pasirinkto banko kodą iš sesijos
        selected_bank_code = self.checkout_session.get_payment_method(
            'selected_bank_code')
        context['selected_bank_code'] = selected_bank_code
        return context

    def post(self, request, *args, **kwargs):
        """
        Kai vartotojas patvirtina užsakymą, sukuriame užsakymą Montonio sistemoje.
        """
        # Gauname pasirinkto banko kodą iš sesijos
        selected_bank_code = self.checkout_session.get_payment_method(
            'selected_bank_code')

        if not selected_bank_code:
            self.add_payment_error("Nepasirinktas banko mokėjimo būdas.")
            return self.render_preview(self.request)

        # Sukuriame Montonio mokėjimą
        montonio_payment = MontonioPayment()
        return_url = self.request.build_absolute_uri('/checkout/success/')
        notification_url = self.request.build_absolute_uri('/checkout/notify/')

        # Sukuriame užsakymą Montonio sistemoje
        order = self.get_order()
        result = montonio_payment.create_order(
            order, return_url, notification_url, selected_bank_code)

        if 'paymentUrl' in result:
            # Nukreipiame vartotoją į Montonio mokėjimo puslapį
            return redirect(result['paymentUrl'])
        else:
            self.add_payment_error(
                "Klaida kuriant užsakymą Montonio sistemoje.")
            return self.render_preview(self.request)


# Montonio webhook'as užsakymo būsenos atnaujinimui
@csrf_exempt
def montonio_payment_notification(request):
    """
    Montonio webhook'as, pranešantis apie mokėjimo būseną.
    """
    token = request.POST.get('orderToken')

    try:
        decoded_token = jwt.decode(
            token, settings.MONTONIO_SECRET_KEY, algorithms=['HS256'])
        if decoded_token.get('paymentStatus') == 'PAID':
            order_number = decoded_token.get('merchantReference')
            order = Order.objects.get(number=order_number)
            order.set_status('Paid')
            return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'failed'}, status=400)
    except jwt.InvalidTokenError:
        return JsonResponse({'error': 'Invalid token'}, status=400)
