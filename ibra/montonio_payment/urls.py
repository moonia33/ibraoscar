# urls.py
from django.urls import path
from .views import MontonioPaymentDetailsView, MontonioOrderPreviewView, montonio_payment_notification
# from oscar.apps.checkout.views import ThankYouView

app_name = 'montonio_payments'

urlpatterns = [
    path('payment-details/', MontonioPaymentDetailsView.as_view(),
         name='payment-details'),
    path('preview/', MontonioOrderPreviewView.as_view(), name='preview'),
    path('thank-you/<str:order_number>/',
         MontonioOrderPreviewView.as_view(), name='thank-you'),
    path('notification/<str:order_number>/',
         montonio_payment_notification, name='notification'),
]
