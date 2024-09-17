from django.urls import path
from . import views

urlpatterns = [
    path('payment-details/', views.payment_details_view, name='payment-details'),
]
