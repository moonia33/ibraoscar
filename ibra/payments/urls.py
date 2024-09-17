from django.urls import path
from .views import payment_methods_view

urlpatterns = [
    path('payment-methods/', payment_methods_view, name='payment_methods'),
]
