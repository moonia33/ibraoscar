from django.db import models
from oscar.apps.payment.abstract_models import AbstractSourceType, AbstractSource


class MontonioSourceType(AbstractSourceType):
    pass


class MontonioSource(AbstractSource):
    order = models.ForeignKey(
        'order.Order',
        on_delete=models.CASCADE,
        related_name='montonio_sources',  # Unikalus related_name
        verbose_name="Order"
    )
    source_type = models.ForeignKey(
        MontonioSourceType,
        on_delete=models.CASCADE,
        related_name='montonio_sources',  # Unikalus related_name
        verbose_name="Source Type"
    )
