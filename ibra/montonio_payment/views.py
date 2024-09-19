import jwt
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from oscar.apps.checkout.views import PaymentDetailsView
from oscar.apps.payment.models import SourceType, Source
from oscar.apps.payment.exceptions import UnableToTakePayment
from django.views.generic import TemplateView  # Tinkamas importavimas
from oscar.apps.order.models import Order
from oscar.apps.order.utils import OrderNumberGenerator
from oscar.apps.checkout import signals
from .services import get_payment_methods, create_montonio_order
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from jwt.exceptions import InvalidTokenError
from django.utils.timezone import now


class MontonioPaymentDetailsView(PaymentDetailsView):
    """
    Vaizdas, kuris apdoroja mokėjimo būdų pasirinkimą iš Montonio API
    ir nukreipia į užsakymo suvestinę (preview).
    """
    template_name = 'oscar/checkout/payment_details.html'

    def post(self, request, *args, **kwargs):
        # Patikriname, ar vartotojas pasirinko banką
        selected_bank_code = request.POST.get('selected_bank_code')
        print(
            f"POST užklausa gauta, pasirinktas banko kodas: {selected_bank_code}")

        if not selected_bank_code:
            messages.error(request, "Prašome pasirinkti banką.")
            return self.render_to_response(self.get_context_data())

        # Atnaujiname banko kodą vartotojo sesijoje
        request.session['selected_bank_code'] = selected_bank_code
        print(f"Banko kodas atnaujintas sesijoje: {selected_bank_code}")

        # Nukreipiame į užsakymo suvestinę (preview)
        return redirect('montonio_payment:preview')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            # Gauname mokėjimo metodus iš Montonio API
            payment_methods = get_payment_methods()
            context['payment_methods'] = payment_methods.get(
                'paymentMethods', {})
        except Exception as e:
            context['payment_methods'] = {}
            print(f"Klaida gaunant mokėjimo būdus: {str(e)}")

        # Parodome vartotojui jo anksčiau pasirinktą banką (jei jis buvo pasirinktas)
        context['selected_bank_code'] = self.request.session.get(
            'selected_bank_code', None)
        print(
            f"Banko kodas sesijoje (payment details): {context['selected_bank_code']}")

        return context


class OrderNumberGenerator:
    """
    Generuoja unikalius užsakymo numerius. Paskutinis užsakymo numeris + 1.
    """

    def generate_order_number(self):
        # Gauname paskutinį užsakymo numerį
        last_order = Order.objects.all().order_by('number').last()

        if last_order:
            # Paskutinis užsakymo numeris + 1
            return int(last_order.number) + 1
        else:
            # Jei tai pirmasis užsakymas, pradedame numeraciją nuo 100001
            return 200001


class MontonioOrderPreviewView(PaymentDetailsView):
    """
    Užsakymo suvestinės (Preview) vaizdas.
    Vartotojas peržiūri užsakymą ir jį pateikia.
    """
    template_name = "oscar/checkout/preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_bank_code'] = self.request.session.get(
            'selected_bank_code')
        if not context['selected_bank_code']:
            messages.error(
                self.request, "Pasirinkimo sesijoje nėra. Grįžkite atgal.")
            return redirect('montonio_payment:payment-details')
        return context

    def post(self, request, *args, **kwargs):
        # Užsakymo pateikimas
        return self.submit_order(request)

    def submit_order(self, request, *args, **kwargs):
        submission = self.build_submission()

        # Paliekame banko kodą sesijoje, kol baigsime kurti užsakymą
        selected_bank_code = request.session.get('selected_bank_code')
        if not selected_bank_code:
            print("No bank code found in session, redirecting back to payment-details")
            messages.error(request, "Prašome pasirinkti banką.")
            # Grąžiname redirect'ą atgal į payment-details
            return redirect('checkout:payment-details')

        print(f"Selected bank code in session: {selected_bank_code}")

        # Generuojame naują užsakymo numerį (paskutinis užsakymo numeris + 1)
        order_number = OrderNumberGenerator().generate_order_number()
        print(f"Generated order number: {order_number}")

        # Sukuriame return ir notification URL
        return_url = request.build_absolute_uri(
            reverse('montonio_payment:thank-you', kwargs={'order_number': order_number}))
        notification_url = request.build_absolute_uri(
            reverse('montonio_payment:notification', kwargs={'order_number': order_number}))

        print(f"Return URL: {return_url}")
        print(f"Notification URL: {notification_url}")

        order_data = {
            'accessKey': settings.MONTONIO_ACCESS_KEY,
            'merchantReference': str(order_number),
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

        print(f"Order data: {order_data}")

        try:
            # Siunčiame užsakymo duomenis į Montonio API
            order_response = create_montonio_order(order_data)
            print(f"Montonio API response: {order_response}")
            payment_url = order_response.get('paymentUrl')

            # Išsaugome mokėjimo šaltinį
            if order_response.get('paymentStatus') == 'PENDING':
                print("Payment status is PENDING, saving source")
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
            order = self.place_order(
                order_number=order_number,
                user=self.request.user,
                basket=submission['basket'],
                shipping_address=submission.get('shipping_address', None),
                shipping_method=submission.get('shipping_method', None),
                shipping_charge=submission.get('shipping_charge', None),
                order_total=submission['order_total']
            )

            # Atnaujiname užsakymo būseną į "BEING PROCESSED"
            order.set_status('BEING PROCESSED')
            print(f"Order {order_number} created and set to 'BEING PROCESSED'")

            # Pakeičiame krepšelio būseną į SUBMITTED
            basket = self.request.basket
            basket.status = basket.SUBMITTED
            basket.date_submitted = now()
            basket.save()
            print(f"Basket {basket.id} status updated to 'SUBMITTED'")

            # Išvalome krepšelį ir sesiją po sėkmingo užsakymo
            self.request.basket.flush()
            # Pašaliname banko kodą po užsakymo užbaigimo
            del request.session['selected_bank_code']
            self.request.session.modified = True  # Užtikriname, kad sesija atnaujinta
            print("Basket flushed, bank code removed, and session modified")

            # Peradresuojame vartotoją į Montonio mokėjimo puslapį
            print(f"Redirecting to payment URL: {payment_url}")
            return redirect(payment_url)

        except Exception as e:
            print(f"Error creating Montonio order: {str(e)}")
            raise UnableToTakePayment(
                f"Nepavyko sukurti Montonio užsakymo: {str(e)}")


@csrf_exempt
def montonio_payment_notification(request, order_number):
    """
    Webhook iš Montonio apdorojimas, skirtas pranešti apie mokėjimo būseną.
    """
    try:
        print(
            f"Gauta POST užklausa iš Montonio su order_number: {order_number}")
        print(f"Request body: {request.body}")

        # Dekoduojame request body, kad gautume tokeną
        data = request.body.decode('utf-8')
        json_data = json.loads(data)
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
                if order.status != 'PAID':
                    order.set_status('PAID')
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


class CustomThankYouView(TemplateView):
    template_name = 'oscar/checkout/thank_you.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Paimame užsakymo numerį iš URL
        order_number = self.kwargs.get('order_number')
        # Gauname užsakymą iš DB pagal numerį
        order = get_object_or_404(Order, number=order_number)
        context['order'] = order  # Pridedame užsakymą į šablono kontekstą
        return context
