from django.shortcuts import render, redirect
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from oscar.apps.checkout.views import PaymentDetailsView
from oscar.apps.payment.models import SourceType, Source
from oscar.apps.payment.exceptions import UnableToTakePayment
from .services import get_payment_methods, create_montonio_order


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
    Užsakymo peržiūros vaizdas, kuris pateikia vartotojo pasirinkimą ir leidžia patvirtinti užsakymą.
    """
    template_name = 'oscar/checkout/preview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Patikriname, ar sesijoje yra banko pasirinkimas
        context['selected_bank_code'] = self.request.session.get(
            'selected_bank_code')

        if not context['selected_bank_code']:
            messages.error(
                self.request, "Banko kodas nerastas sesijoje. Grįžkite atgal ir pasirinkite banką.")
            return redirect('montonio_payments:payment-details')

        print(
            f"Banko kodas sesijoje (preview): {context['selected_bank_code']}")
        return context

    def post(self, request, *args, **kwargs):
        # Patikriname, ar vartotojas nori pateikti užsakymą
        action = request.POST.get('action', '')

        if action == 'place_order':
            # Vykdome užsakymo patvirtinimą
            return self.submit_order(request, *args, **kwargs)

        return self.render_to_response(self.get_context_data())

    def submit_order(self, request, *args, **kwargs):
        order_number = self.generate_order_number(self.get_order())
        total = self.get_order_total(self.get_order())

        # Paimame išsaugotą banko kodą
        selected_bank_code = request.session.get('selected_bank_code')

        if not selected_bank_code:
            messages.error(
                self.request, "Banko kodas nerastas. Grįžkite atgal ir pasirinkite banką.")
            return redirect('montonio_payments:payment-details')

        try:
            # Paruošiame Montonio užsakymo duomenis
            order_data = {
                'accessKey': settings.MONTONIO_ACCESS_KEY,
                'merchantReference': order_number,
                'returnUrl': self.request.build_absolute_uri(reverse('checkout:thank-you', kwargs={'order_number': order_number})),
                'notificationUrl': self.request.build_absolute_uri(reverse('checkout:notification', kwargs={'order_number': order_number})),
                'currency': 'EUR',
                'grandTotal': total.incl_tax,
                'billingAddress': self.get_billing_address(),
                'shippingAddress': self.get_shipping_address(),
                'lineItems': self.get_order_line_items(),
                'payment': {
                    'method': 'paymentInitiation',
                    'methodDisplay': 'Pay with your bank',
                    'methodOptions': {
                        'preferredProvider': selected_bank_code,
                        'preferredCountry': 'LT'
                    },
                    'amount': total.incl_tax,
                    'currency': 'EUR'
                }
            }
            print(
                f"Vartotojo banko kodas užsakymo pateikime: {selected_bank_code}")
            # Sukuriame Montonio užsakymą
            order_response = create_montonio_order(order_data)
            payment_url = order_response.get('paymentUrl')

            # Išsaugome mokėjimo šaltinį
            source_type, created = SourceType.objects.get_or_create(
                name='Montonio')
            source = Source(source_type=source_type, amount_allocated=total.incl_tax,
                            reference=order_response.get('uuid'))
            self.add_payment_source(source)
            self.add_payment_event('order-created', total.incl_tax)

            # Nukreipiame klientą į Montonio mokėjimo puslapį
            return redirect(payment_url)

        except Exception as e:
            raise UnableToTakePayment(
                f"Unable to create Montonio order: {str(e)}")
