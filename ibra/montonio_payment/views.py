import jwt
import json
from django.shortcuts import render, redirect
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from oscar.apps.checkout.views import PaymentDetailsView
from oscar.apps.payment.models import SourceType, Source
from oscar.apps.payment.exceptions import UnableToTakePayment
from oscar.apps.order.models import Order
from oscar.apps.order.utils import OrderNumberGenerator
from oscar.apps.checkout import signals
from .services import get_payment_methods, create_montonio_order
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from jwt.exceptions import InvalidTokenError


class MontonioPaymentDetailsView(PaymentDetailsView):
    """
    Vaizdas, kuris apdoroja banko pasirinkimą ir nukreipia į užsakymo suvestinę.
    """
    template_name = 'oscar/checkout/payment_details.html'

    def post(self, request, *args, **kwargs):
        # Patikriname, ar banko kodas buvo pasirinktas
        selected_bank_code = request.POST.get('selected_bank_code')
        print(
            f"POST užklausa gauta, pasirinktas banko kodas: {selected_bank_code}")

        if not selected_bank_code:
            messages.error(request, "Prašome pasirinkti banką.")
            return self.render_to_response(self.get_context_data())

        # Atnaujiname vartotojo banko pasirinkimą sesijoje (jei pakeista)
        request.session['selected_bank_code'] = selected_bank_code
        print(f"Banko kodas atnaujintas sesijoje: {selected_bank_code}")

        # Nukreipiame į užsakymo suvestinę (preview)
        return redirect('montonio_payments:preview')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            # Gauti mokėjimo metodus iš Montonio API
            payment_methods = get_payment_methods()
            context['payment_methods'] = payment_methods.get(
                'paymentMethods', {})
        except Exception as e:
            context['payment_methods'] = {}
            print(f"Klaida gaunant mokėjimo būdus: {str(e)}")

        # Pateikiame pasirinkimą, jei vartotojas grįžta iš preview į payment-details
        context['selected_bank_code'] = self.request.session.get(
            'selected_bank_code', None)
        print(
            f"Banko kodas sesijoje (payment details): {context['selected_bank_code']}")

        return context


class MontonioOrderPreviewView(PaymentDetailsView):
    """
    Užsakymo suvestinės vaizdas
    """
    template_name = "oscar/checkout/preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_bank_code'] = self.request.session.get(
            'selected_bank_code')
        if not context['selected_bank_code']:
            messages.error(
                self.request, "Pasirinkimo sesijoje nėra. Grįžkite atgal.")
            return redirect('montonio_payments:payment-details')
        return context

    def post(self, request, *args, **kwargs):
        return self.submit_order(request)

    def submit_order(self, request, *args, **kwargs):
        submission = self.build_submission()
        order_number = self.generate_order_number(submission['basket'])
        selected_bank_code = request.session.get('selected_bank_code')

        if not selected_bank_code:
            messages.error(request, "Prašome pasirinkti banką.")
            return redirect('checkout:payment-details')

        # Pilnai užpildome URL su domeno adresu
        return_url = request.build_absolute_uri(
            reverse('montonio_payments:thank-you', kwargs={'order_number': order_number}))
        notification_url = request.build_absolute_uri(
            reverse('montonio_payments:notification', kwargs={'order_number': order_number}))

        order_data = {
            'accessKey': settings.MONTONIO_ACCESS_KEY,
            'merchantReference': str(order_number),  # Konvertuokime į string
            'returnUrl': return_url,
            'notificationUrl': notification_url,
            'currency': 'EUR',
            'grandTotal': float(submission['order_total'].incl_tax),
            'locale': 'lt',
            'payment': {
                'method': 'paymentInitiation',
                'methodOptions': {
                    'preferredProvider': selected_bank_code,
                    'paymentDescription': f'Apmokėjimas už užsakymą {order_number}',
                    'preferredCountry': 'LT',
                },
                'amount': float(submission['order_total'].incl_tax),
                'currency': 'EUR'
            }
        }
        print(order_data)
        try:
            # Siunčiame užsakymo duomenis į Montonio API
            order_response = create_montonio_order(order_data)
            payment_url = order_response.get('paymentUrl')

            # Išsaugome mokėjimo šaltinį
            if order_response.get('paymentStatus') == 'PENDING':
                source_type, created = SourceType.objects.get_or_create(
                    name='Montonio')
                source = Source(
                    source_type=source_type,
                    amount_allocated=submission['order_total'].incl_tax,
                    reference=order_response.get('uuid')
                )
                self.add_payment_source(source)
                self.add_payment_event(
                    'order-created', submission['order_total'].incl_tax)

            # Sukuriame užsakymą Oscar sistemoje
            self.place_order(
                order_number=order_number,
                user=self.request.user,
                basket=submission['basket'],
                shipping_address=submission.get('shipping_address', None),
                shipping_method=submission.get('shipping_method', None),
                shipping_charge=submission.get('shipping_charge', None),
                order_total=submission['order_total']
            )

            # Peradresuojame į Montonio mokėjimo puslapį
            return redirect(payment_url)
        except Exception as e:
            print(f"Klaida kuriant užsakymą Montonio API: {str(e)}")
            raise UnableToTakePayment(
                f"Nepavyko sukurti Montonio užsakymo: {str(e)}")


@csrf_exempt
def montonio_payment_notification(request, order_number):
    """
    Webhook iš Montonio apdorojimas, skirtas pranešti apie mokėjimo būseną
    """
    try:
        print(
            f"Gauta POST užklausa iš Montonio su order_number: {order_number}")
        print(f"Request body: {request.body}")

        # Dekoduojame request body, kad gautume tokeną
        data = request.body.decode('utf-8')
        json_data = json.loads(data)  # Dekoduojame JSON formatą
        order_token = json_data.get('orderToken')

        if not order_token:
            print(f"Tokenas nebuvo gautas iš Montonio POST užklausos.")
            return JsonResponse({'error': 'Order token not found'}, status=400)

        # Dekoduojame tokeną naudojant Montonio Secret Key
        try:
            decoded_token = jwt.decode(
                order_token, settings.MONTONIO_SECRET_KEY, algorithms=['HS256'])
            print(f"Decoded token: {decoded_token}")
        except InvalidTokenError as e:
            print(f"Neteisingas tokenas: {e}")
            return JsonResponse({'error': 'Invalid token'}, status=400)

        # Patikriname, ar mokėjimo būklė yra "PAID"
        if decoded_token.get('paymentStatus') == 'PAID':
            order_number = decoded_token.get('merchantReference')
            try:
                order = Order.objects.get(number=order_number)

                # Tikriname dabartinę užsakymo būseną ir atnaujiname į PAID
                if order.status != 'PAID':  # Pakeiskite į galiojantį tikrinimą, priklausomai nuo verslo logikos
                    order.set_status('PAID')  # Atnaujiname užsakymo būseną
                    print(
                        f"Užsakymas {order_number} atnaujintas į PAID būseną.")
                else:
                    print(f"Užsakymas {order_number} jau buvo PAID būsenoje.")

                return JsonResponse({'status': 'ok'}, status=200)

            except Order.DoesNotExist:
                print(f"Užsakymas {order_number} nerastas.")
                return JsonResponse({'error': 'Order not found'}, status=404)

        print(
            f"Mokėjimas nepavyko arba nebuvo PAID būsenos. Token duomenys: {decoded_token}")
        return JsonResponse({'status': 'failed'}, status=400)

    except Exception as e:
        print(f"Klaida apdorojant webhook: {e}")
        return JsonResponse({'error': str(e)}, status=500)
