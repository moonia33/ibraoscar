from django.apps import apps
from django.urls import include, path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
# from oscar.apps.checkout.views import ThankYouView
# from montonio_payment.views import MontonioPaymentDetailsView, MontonioOrderPreviewView

app_name = 'checkout'

urlpatterns = [
    path('admin/', admin.site.urls),

    # Perrašome numatytąjį Oscar "payment-details" ir "preview" URL
    path('checkout/', include('montonio_payment.urls')),
    # path('oscar/checkout/thank-you/', ThankYouView.as_view(), name='thank-you'),

    # Numatytoji Oscar programos URL struktūra
    path('', include(apps.get_app_config('oscar').urls[0]))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
