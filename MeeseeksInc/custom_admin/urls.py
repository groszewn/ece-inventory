from django.conf.urls import url

from . import views

#this app_name is important b/c Django needs to look through all the apps 
# and we need to differentiate
app_name = 'custom_admin'  
urlpatterns = [
    # the argument 'name' at the end of url() is IMPORTANT 
    # b/c we use it to load these urls later in the html files
    # this allows us to change the url of a page without changing it in the HTML files
    
    # this is what it goes to if typed /
#     url(r'^$', views.AdminIndexView.as_view(), name='index'),
    url(r'^$', views.AdminIndexView.as_view(), name='index'),
    url(r'^deny/request/all$', views.deny_all_request, name='deny_all_requests'),
    url(r'^approve/request/all$', views.approve_all_requests, name='approve_all_requests'),
    url(r'^deny/request/(?P<pk>[\w\-\ ]+)$', views.deny_request, name='deny_request'),
    url(r'^approve/request/(?P<pk>[\w\-\ ]+)$', views.approve_request, name='approve_request'),
    url(r'^disburse/item$', views.post_new_disburse, name='post_new_disburse'),

]