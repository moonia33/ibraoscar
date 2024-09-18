# urls.py
from django.urls import path
from .views import MontonioPaymentDetailsView, MontonioOrderPreviewView

urlpatterns = [
    path('payment-details/', MontonioPaymentDetailsView.as_view(),
         name='payment-details'),
    path('preview/', MontonioOrderPreviewView.as_view(), name='preview'),
]
