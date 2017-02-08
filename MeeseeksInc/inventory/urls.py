from django.conf.urls import url

from . import views


#this app_name is important b/c Django needs to look through all the apps 
# and we need to differentiate
app_name = 'inventory'  
urlpatterns = [
    # the argument 'name' at the end of url() is IMPORTANT 
    # b/c we use it to load these urls later in the html files
    # this allows us to change the url of a page without changing it in the HTML files
     
    # this is what it goes to if typed /
    url(r'^inventory_cart$', views.CartListView.as_view(), name='inventory_cart'),
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^item/(?P<pk>[\w\-\ ]+)/$', views.DetailView.as_view(), name='detail'),
#     url(r'^(?P<pk>[0-9]+)/results/$', views.ResultsView.as_view(), name='results'),
    url(r'^search_setup/$', views.search_form, name='search_setup'),
    url(r'^post/request/(?P<pk>[\w\-\ ]+)/$', views.request_specific_item, name='request_specific_item'),
    url(r'^post/request/$', views.post_new_request, name='post_new_request'),
    url(r'^request_detail/(?P<pk>[\w\-\ ]+)$', views.request_detail.as_view(), name='request_detail'),
    url(r'^request_cancel/(?P<pk>[\w\-\ ]+)$', views.request_cancel_view.as_view(), name='request_cancel'),
    url(r'^request_edit/(?P<pk>[\w\-\ ]+)$', views.edit_request, name='request_edit'),
    url(r'^(?P<pk>[\w\-\ ]+)/cancel/$', views.cancel_request, name='request_cancel'),
]