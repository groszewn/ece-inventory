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
     
    # if typed /, goes to following url
    # url(r'^$', views.AdminIndexView.as_view(), name='index'),

    url(r'^edit/loan/(?P<pk>[\w\-\ ]+)/$', views.LoanView.edit_loan, name='edit_loan'),
    url(r'^convert/loan/(?P<pk>[\w\-\ ]+)/$', views.LoanView.convert_loan, name='convert_loan'),
    url(r'^convert_with_assets/loan/(?P<pk>[\w\-\ ]+)/$', views.LoanView.convert_loan_with_assets, name='convert_loan_with_assets'),
    url(r'^checkIn/loan/(?P<pk>[\w\-\ ]+)/$', views.LoanView.check_in_loan, name='check_in_loan'),
    url(r'^checkin_with_assets/loan/(?P<pk>[\w\-\ ]+)/$', views.LoanView.check_in_loan_with_assets, name='check_in_loan_with_assets'),
    url(r'^request/accept/addcomment/(?P<pk>[\w\-\ ]+)/$', views.RequestsView.add_comment_to_request_accept, name='add_comment_to_request_accept'),
    url(r'^request/deny/addcomment/(?P<pk>[\w\-\ ]+)/$', views.RequestsView.add_comment_to_request_deny, name='add_comment_to_request_deny'),
    url(r'^request/asset_accept/(?P<pk>[\w\-\ ]+)/$', views.request_accept_with_assets, name='request_accept_with_assets'),
    url(r'^disburse/item$', views.DisbursementView.post_new_disburse, name='post_new_disburse'),
    url(r'^disburse/item/(?P<pk>[\w\-\ ]+)/$', views.DisbursementView.post_new_disburse_specific, name='post_specific_disburse'),
    url(r'^deny/request/all$', views.RequestsView.deny_all_request, name='deny_all_requests'),
    url(r'^approve/request/all$', views.RequestsView.approve_all_requests, name='approve_all_requests'),
    url(r'^deny/request/(?P<pk>[\w\-\ ]+)/$', views.RequestsView.deny_request, name='deny_request'),
    url(r'^approve/request/(?P<pk>[\w\-\ ]+)/$', views.RequestsView.approve_request, name='approve_request'),
    url(r'^edit/item/module/(?P<pk>[\w\-\ ]+)/$', views.ItemView.edit_item_module, name='edit_item_module'),
    url(r'^create/item$', views.ItemView.create_new_item, name='create_new_item'),
    url(r'^delete/(?P<pk>[\w\-\ ]+)/$', views.ItemView.delete_item, name='delete_item'),
    url(r'^$', inventory.views.IndexView.as_view(), name='index'),
    
    url(r'^asset/edit/(?P<pk>[\w\-\ ]+)/$', views.AssetView.edit_asset, name='edit_asset'),
    url(r'^asset/delete/(?P<pk>[\w\-\ ]+)/$', views.AssetView.delete_asset, name='delete_asset'),
    url(r'^asset/delete/detail/(?P<pk>[\w\-\ ]+)/$', views.AssetView.delete_asset_from_detail, name='delete_asset_from_detail'),
    url(r'^add/assets/(?P<pk>[\w\-\ ]+)/$', views.AssetView.add_assets, name='add_assets'),
    
    url(r'^edit/tags/(?P<pk>[\w\-\ ]+)/$', views.TagView.add_tags_module, name='tags_module'),
    url(r'^delete/tag/(?P<pk>[\w\-\ ]+)/(?P<item>[\w\-\ ]+)/$', views.TagView.delete_tag, name='delete_tag'),
    
    url(r'^add_custom_field/$', views.CustomFieldView.as_view(), name='add_custom_field'),
    url(r'^delete_custom_field/$', views.CustomFieldView.delete_custom_field, name='delete_custom_field'),
    url(r'^modify_custom_field/$', views.CustomFieldView.modify_custom_field, name='modify_custom_field'),
    url(r'^modify_custom_field/(?P<pk>[\w\-\ ]+)/$', views.CustomFieldView.modify_custom_field_modal, name='modify_custom_field_modal'),
    
    url(r'^log$', views.LogView.as_view(), name='log'),
    url(r'^log_item$', views.LogView.log_item, name='log_item'),
    url(r'^destroy/asset/(?P<pk>[\w\-\ ]+)/$', views.LogView.log_asset, name='destroy_asset'),
    
    url(r'^edit/user_permission/(?P<pk>[\w\-\ ]+)/$', views.UserListView.edit_permission, name='edit_permission'),
    url(r'^users/$', views.UserListView.as_view(), name='user_page'),
    url(r'^userfield-autocomplete/$', views.UserAutocomplete.as_view(), name='userfield-autocomplete'),
    url(r'^registration/$', views.RegistrationView.as_view(), name = 'register_page'),
    
    url(r'^subscription/$', views.EmailView.subscribe, name='subscribe'),
    url(r'^edit_prepend/$', views.EmailView.change_email_prepend, name='change_email_prepend'),
    url(r'^send_email/$', views.EmailView.create_email, name='send_email'),
    url(r'delay_email/$', views.EmailView.delay_email, name='delay_email'),
    url(r'change_loan_email_body/$', views.EmailView.loan_reminder_body, name='change_loan_body'),
    url(r'delete_task_queue/$', views.EmailView.delete_task_queue, name='delete_task_queue'),
    
    url(r'^csv/guide/$',inventory.views.csv_guide_page,name='csv_help'),
    url(r'^upload/$', views.upload_page, name='upload_page'),
    url(r'^backfill/from/loan/(?P<pk>[\w\-\ ]+)/$', views.create_backfill_from_loan, name='backfill_from_loan'),
    url(r'^backfill/accept/addcomment/(?P<pk>[\w\-\ ]+)/$', views.add_comment_to_backfill_accept, name='add_comment_to_backfill_accept'),
    url(r'^backfill/deny/addcomment/(?P<pk>[\w\-\ ]+)/$', views.add_comment_to_backfill_deny, name='add_comment_to_backfill_deny'),
    url(r'^backfill/complete/addcomment/(?P<pk>[\w\-\ ]+)/$', views.add_comment_to_backfill_complete, name='add_comment_to_backfill_complete'),
    url(r'^backfill/complete/addcomment/asset/(?P<pk>[\w\-\ ]+)/$', views.add_comment_to_backfill_asset_complete, name='add_comment_to_backfill_complete_asset'),
    url(r'^backfill/fail/addcomment/(?P<pk>[\w\-\ ]+)/$', views.add_comment_to_backfill_fail, name='add_comment_to_backfill_fail'),
    url(r'^backfill/add/notes/(?P<pk>[\w\-\ ]+)/$', views.add_notes_to_backfill, name='add_notes_to_backfill'),
]


