from django.conf.urls import url
 
from . import views
from django.contrib.auth.decorators import permission_required
 
#this app_name is important b/c Django needs to look through all the apps 
# and we need to differentiate
app_name = 'custom_admin'  
urlpatterns = [
    # the argument 'name' at the end of url() is IMPORTANT 
    # b/c we use it to load these urls later in the html files
    # this allows us to change the url of a page without changing it in the HTML files
     
    # this is what it goes to if typed /
#     url(r'^$', views.AdminIndexView.as_view(), name='index'),
    
    url(r'^request/accept/addcomment/(?P<pk>[\w\-\ ]+)$', permission_required('is_staff', login_url='/login/check_login/')(views.add_comment_to_request_accept), name='add_comment_to_request_accept'),
    url(r'^request/deny/addcomment/(?P<pk>[\w\-\ ]+)$', permission_required('is_staff', login_url='/login/check_login/')(views.add_comment_to_request_deny), name='add_comment_to_request_deny'),
    url(r'^disburse/item$', permission_required('is_staff', login_url='/login/check_login/')(views.post_new_disburse), name='post_new_disburse'),
    url(r'^deny/request/all$', permission_required('is_staff', login_url='/login/check_login/')(views.deny_all_request), name='deny_all_requests'),
    url(r'^approve/request/all$', permission_required('is_staff', login_url='/login/check_login/')(views.approve_all_requests), name='approve_all_requests'),
    url(r'^deny/request/(?P<pk>[\w\-\ ]+)$', permission_required('is_staff', login_url='/login/check_login/')(views.deny_request), name='deny_request'),
    url(r'^approve/request/(?P<pk>[\w\-\ ]+)$', permission_required('is_staff', login_url='/login/check_login/')(views.approve_request), name='approve_request'),
#     url(r'^edit/item/(?P<pk>[\w\-\ ]+)$', permission_required('is_staff', login_url='/login/check_login/')(views.edit_item), name='edit_item'),
#     url(r'^create/item$', permission_required('is_staff', login_url='/login/check_login/')(views.create_new_item), name='create_new_item'),
    url(r'^register/$', permission_required('is_staff', login_url='/login/check_login/')(views.register_page), name = 'register_page'),
    url(r'^delete/(?P<pk>[\w\-\ ]+)$', permission_required('is_staff', login_url='/login/check_login/')(views.delete_item), name='delete_item'),
    url(r'^$', permission_required('is_staff', login_url='/login/check_login/')(views.AdminIndexView.as_view()), name='index'),
    url(r'^log_item$', permission_required('is_staff', login_url='/login/check_login/')(views.log_item), name='log_item'),
#     url(r'^edit/tag/(?P<pk>[\w\-\ ]+)$', views.edit_tag, name='edit_tag'),
#     url(r'^add/tag/(?P<pk>[\w\-\ ]+)$', views.add_tags, name='add_tags'),
#     url(r'^delete/tag/(?P<pk>[\w\-\ ]+)$', views.delete_tag, name='delete_tag'),
]