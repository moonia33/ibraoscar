from django.db import models
from oscar.core.compat import AUTH_USER_MODEL


class Child(models.Model):
    parent = models.ForeignKey(
        AUTH_USER_MODEL,  # Naudojame Oscar būdą nuorodai į vartotojo modelį
        on_delete=models.CASCADE,
        related_name='children'
    )
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
