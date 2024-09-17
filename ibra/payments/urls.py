from .views import CustomPreviewView, montonio_payment_notification

from django.urls import path

app_name = 'payments'

urlpatterns = [
    path('preview/', CustomPreviewView.as_view(), name='preview'),
    path('notify/', montonio_payment_notification, name='montonio-notification'),

]
