from django.core.management.base import BaseCommand
from payments.montonio import get_payment_methods  # Importuokite funkciją


class Command(BaseCommand):
    help = 'Test Montonio payment methods'

    def handle(self, *args, **kwargs):
        country_code = 'LT'  # Testavimo šalis
        methods = get_payment_methods(country_code)
        if methods:
            self.stdout.write(self.style.SUCCESS(
                'Successfully fetched payment methods'))
            self.stdout.write(str(methods))
        else:
            self.stdout.write(self.style.ERROR(
                'Failed to fetch payment methods'))
