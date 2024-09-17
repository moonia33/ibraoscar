from django.apps import apps
from django.urls import include, path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from graphene_django.views import GraphQLView
from .schema import schema
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('admin/', admin.site.urls),
    path('graphql/', csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema))),
    path('checkout/', include('payments.urls')),
    path('', include(apps.get_app_config('oscar').urls[0]))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
