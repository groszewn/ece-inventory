from dal import autocomplete
from django.conf.urls import url

from custom_admin.views import UserAutocomplete
import inventory

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

    url(r'^convert/loan/(?P<pk>[\w\-\ ]+)$', views.convert_loan, name='convert_loan'),
    url(r'^request/accept/addcomment/(?P<pk>[\w\-\ ]+)$', views.add_comment_to_request_accept, name='add_comment_to_request_accept'),
    url(r'^request/deny/addcomment/(?P<pk>[\w\-\ ]+)$', views.add_comment_to_request_deny, name='add_comment_to_request_deny'),
    url(r'^disburse/item$', views.post_new_disburse, name='post_new_disburse'),
    url(r'^disburse/item/(?P<pk>[\w\-\ ]+)$', views.post_new_disburse_specific, name='post_specific_disburse'),
    url(r'^deny/request/all$', views.deny_all_request, name='deny_all_requests'),
    url(r'^approve/request/all$', views.approve_all_requests, name='approve_all_requests'),
    url(r'^deny/request/(?P<pk>[\w\-\ ]+)$', views.deny_request, name='deny_request'),
    url(r'^approve/request/(?P<pk>[\w\-\ ]+)$', views.approve_request, name='approve_request'),
    url(r'^post/request/$', views.post_new_request, name='post_new_request'),
    url(r'^edit/item/(?P<pk>[\w\-\ ]+)$', views.edit_item, name='edit_item'),
    url(r'^edit/item/module/(?P<pk>[\w\-\ ]+)$', views.edit_item_module, name='edit_item_module'),
    url(r'^create/item$', views.create_new_item, name='create_new_item'),
    url(r'^register/$', views.register_page, name = 'register_page'),
    url(r'^delete/(?P<pk>[\w\-\ ]+)$', views.delete_item, name='delete_item'),
    url(r'^$', views.AdminIndexView.as_view(), name='index'),
    url(r'^log_item$', views.log_item, name='log_item'),
    url(r'^edit/tags/(?P<pk>[\w\-\ ]+)$', views.add_tags_module, name='tags_module'),
    url(r'^edit/tag/(?P<pk>[\w\-\ ]+)/(?P<item>[\w\-\ ]+)$', views.edit_tag, name='edit_tag'),
    url(r'^edit/specific/tag/(?P<pk>[\w\-\ ]+)/(?P<item>[\w\-\ ]+)$', views.edit_specific_tag, name='edit_specific_tag'),
    url(r'^add/tag/(?P<pk>[\w\-\ ]+)$', views.add_tags, name='add_tags'),
    url(r'^delete/tag/(?P<pk>[\w\-\ ]+)/(?P<item>[\w\-\ ]+)$', views.delete_tag, name='delete_tag'),
    url(r'^search/$', inventory.views.search_view, name='search_setup'),
    url(r'^add_custom_field/$', views.add_custom_field, name='add_custom_field'),
    url(r'^delete_custom_field/$', views.delete_custom_field, name='delete_custom_field'),
    url(r'^log$', views.LogView.as_view(), name='log'),
    url(r'^edit/user_permission/(?P<pk>[\w\-\ ]+)$', views.edit_permission, name='edit_permission'),
    url(r'^users/$', views.UserListView.as_view(), name='user_page'),
    url(r'^userfield-autocomplete/$', UserAutocomplete.as_view(), name='userfield-autocomplete'),
    url(r'^request_edit_from_main/(?P<pk>[\w\-\ ]+)$', views.edit_request_main_page, name='request_edit_from_main'),
    url(r'^subscription/$', views.subscribe, name='subscribe'),
    url(r'^edit_prepend/$', views.change_email_prepend, name='change_email_prepend'),
    url(r'^send_email/$', views.create_email, name='send_email'),
    url(r'delay_email/$', views.delay_email, name='delay_email'),
]