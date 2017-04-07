from django.conf.urls import url
from django.conf.urls.static import static
from django.conf import settings

import custom_admin.views
import inventory.api

from . import views


# this app_name is important b/c Django needs to look through all the apps 
# and we need to differentiate
app_name = 'inventory'  
urlpatterns = [
    url(r'^api/token/$', views.get_api_token, name='api_token'),
    # the argument 'name' at the end of url() is IMPORTANT 
    # b/c we use it to load these urls later in the html files
    # this allows us to change the url of a page without changing it in the HTML files
     
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^item/(?P<pk>[\w\-\ ]+)/$', views.DetailView.as_view(), name='detail'),
    url(r'^inventory_cart$', views.CartListView.as_view(), name='inventory_cart'),
    url(r'^inventory_cart/delete/(?P<pk>[\w\-\ ]+)/$', views.CartListView.delete_cart_instance, name='delete_cart_instance'),
    url(r'^post/request/(?P<pk>[\w\-\ ]+)/$', views.RequestDetailView.request_specific_item, name='request_specific_item'),
    url(r'^request_edit/(?P<pk>[\w\-\ ]+)/$', views.RequestDetailView.edit_request, name='request_edit'),
    url(r'^request_detail/(?P<pk>[\w\-\ ]+)/$', views.RequestDetailView.as_view(), name='request_detail'),
    url(r'^(?P<pk>[\w\-\ ]+)/cancel/$', views.RequestDetailView.cancel_request, name='request_cancel'),
    url(r'^item_detail/(?P<pk>[\w\-\ ]+)/cancel/$', views.RequestDetailView.cancel_request, name='item_detail_request_cancel'),
 #   url(r'^loan/detail/checkIn/loan/(?P<pk>[\w\-\ ]+)/$', custom_admin.views.check_in_loan, name='check_in_loan'), 
    url(r'^loan/detail/edit/loan/(?P<pk>[\w\-\ ]+)/$', custom_admin.views.edit_loan, name='edit_loan'), 
    url(r'^loan/detail/(?P<pk>[\w\-\ ]+)/$', views.LoanDetailView.as_view(), name='loan_detail'),
    url(r'^asset/(?P<pk>[\w\-\ ]+)/$', views.AssetDetailView.as_view(), name='asset_detail'),
    ################################### API URLS #######################################
    url(r'^api/items/$', inventory.api.APIItemList.as_view(), name='api_item_list'),
    url(r'^api/items/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIItemDetail.as_view(), name='api_item_detail'),
    url(r'^api/requests/$', inventory.api.APIRequestList.as_view()),
    url(r'^api/requests/create/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIRequestThroughItem.as_view()),
    url(r'^api/requests/multiple_create/(?P<item_list>[\w\-\ (\,)?]+)/$', inventory.api.APIMultipleRequests.as_view()),
    url(r'^api/requests/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIRequestDetail.as_view()),
    url(r'^api/requests/approve/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIApproveRequest.as_view()),
    url(r'^api/requests/deny/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIDenyRequest.as_view()),
    url(r'^api/requests/approve_with_assets/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIApproveRequestWithAssets.as_view()),
    url(r'^api/disbursements/$', inventory.api.APIDisbursementList.as_view()),
    url(r'^api/disbursements/direct/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIDirectDisbursement.as_view()),
    url(r'^api/users/$', inventory.api.APIUserList.as_view()),
    url(r'^api/users/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIUserDetail.as_view()),
    url(r'^api/custom/field/$', inventory.api.APICustomField.as_view()),
    url(r'^api/custom/field/modify/(?P<pk>[\w\-\ ]+)/$', inventory.api.APICustomFieldModify.as_view()),
    url(r'^api/tags/$', inventory.api.APITagList.as_view(), name='api_tag_list'),
    url(r'^api/logs/$', inventory.api.APILogList.as_view(), name='api_log_list'),
    url(r'^api/loan/checkin/(?P<pk>[\w\-\ ]+)/$', inventory.api.APILoanCheckIn.as_view(), name='api_loan_checkin'),
    url(r'^api/loan/convert/(?P<pk>[\w\-\ ]+)/$', inventory.api.APILoanConvert.as_view(), name='api_loan_convert'),
    url(r'^api/loan/update/(?P<pk>[\w\-\ ]+)/$', inventory.api.APILoanUpdate.as_view(), name='api_loan_update'),
    url(r'^api/loan/$', inventory.api.APILoanList.as_view(), name='api_loan_list'),
    url(r'^api/guide/$', custom_admin.views.api_guide_page, name='api_guide'),
    url(r'^api/upload/$', inventory.api.ItemUpload.as_view(), name='upload'),    
    url(r'^api/subscribe/(?P<pk>[\w\-\ ]+)/$', inventory.api.APISubscriptionDetail.as_view(), name='subscribe'),
    url(r'^api/loan/email/body/$', inventory.api.APILoanEmailBody.as_view(), name='email_body'),
    url(r'^api/loan/email/dates/configure/$', inventory.api.APILoanEmailConfigureDates.as_view(), name='email_send_dates'),
    url(r'^api/loan/email/dates/delete/$', inventory.api.APILoanEmailClearDates.as_view(), name='loan_email_delete_dates'),
    url(r'^api/loan/backfill/create/(?P<pk>[\w\-\ ]+)/$', inventory.api.APILoanBackfillPost.as_view(), name='backfill_create'),
    url(r'^api/loan/backfill/approve/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIApproveBackfill.as_view(), name='backfill_approve'),
    url(r'^api/loan/backfill/deny/(?P<pk>[\w\-\ ]+)/$', inventory.api.APIDenyBackfill.as_view(), name='backfill_deny'),
    url(r'^api/to_asset/(?P<pk>[\w\-\ ]+)/$',inventory.api.APIItemToAsset.as_view(),name='item_to_asset'),
    url(r'^api/v1/(?P<cls_name>[\w-]+)/$',inventory.api.MyAPI.as_view(),name='api'),
]+static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)