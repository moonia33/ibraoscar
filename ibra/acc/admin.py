from django.contrib import admin
from .models import Child

# Paprastas Child modelio administravimas


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name',
                    'parent', 'email', 'phone_number')
    search_fields = ('first_name', 'last_name', 'parent__email', 'email')
    list_filter = ('parent',)

    # Pridedame paiešką pagal susijusio vartotojo el. paštą
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term:
            queryset = queryset.filter(parent__email__icontains=search_term)
        return queryset, use_distinct
