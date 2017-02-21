"""MeeseeksInc URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from rest_framework import routers, serializers, viewsets
from rest_framework.authtoken import views

from inventory import views as inventory_views
from inventory.models import Item, Request, Disbursement
from inventory.serializers import ItemSerializer, RequestSerializer, \
    DisbursementSerializer


# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'is_staff')

# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer

class RequestViewSet(viewsets.ModelViewSet):
    queryset = Request.objects.all()
    serializer_class = RequestSerializer

class DisbursementViewSet(viewsets.ModelViewSet):  
    queryset = Disbursement.objects.all()
    serializer_class = DisbursementSerializer
    
# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'items', ItemViewSet)
router.register(r'requests', RequestViewSet)
router.register(r'disbursements', DisbursementViewSet)

urlpatterns = [
    url(r'^', include('inventory.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^customadmin/', include('custom_admin.urls')),
    url(r'^login/$', auth_views.login, {'template_name': 'inventory/login.html'}, name='login'), 
    url(r'^login/check_login/$', inventory_views.check_login, name='check_login'),
    url(r'^logout/$', auth_views.logout, {'template_name': 'inventory/logged_out.html'}, name='logout'),
    url(r'^login/check_OAuth_login/$', inventory_views.check_OAuth_login, name='check_OAuth_login'),
    url(r'^request_oauth/$', inventory_views.request_token, name='request_token'),
    url(r'^get_access_token/$', inventory_views.getAccessToken, name='get_access_token'), 
    # API URLS 
    url(r'^api-viewer/', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api-token-auth/', views.obtain_auth_token)
]
