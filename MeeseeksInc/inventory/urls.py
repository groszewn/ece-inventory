from django.conf.urls import url

from . import views


#this app_name is important b/c Django needs to look through all the apps 
# and we need to differentiate
app_name = 'inventory'  
urlpatterns = [
    url(r'^api/token/$', views.get_api_token, name='api_token'),
    # the argument 'name' at the end of url() is IMPORTANT 
    # b/c we use it to load these urls later in the html files
    # this allows us to change the url of a page without changing it in the HTML files
     
    # this is what it goes to if typed /
    url(r'^inventory_cart$', views.CartListView.as_view(), name='inventory_cart'),
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^item/(?P<pk>[\w\-\ ]+)/$', views.DetailView.as_view(), name='detail'),
    url(r'^search/$', views.search_view, name='search_setup'),
    url(r'^post/request/(?P<pk>[\w\-\ ]+)/$', views.request_specific_item, name='request_specific_item'),
    url(r'^post/request/$', views.post_new_request, name='post_new_request'),
    url(r'^request_detail/(?P<pk>[\w\-\ ]+)$', views.request_detail.as_view(), name='request_detail'),
    url(r'^request_edit/(?P<pk>[\w\-\ ]+)$', views.edit_request, name='request_edit'),
    url(r'^(?P<pk>[\w\-\ ]+)/cancel/$', views.cancel_request, name='request_cancel'),
    url(r'^(?P<pk>[\w\-\ ]+)/approve/$', views.approve_request, name='request_approve'),
    url(r'^inventory_cart/delete/(?P<pk>[\w\-\ ]+)/$', views.delete_cart_instance, name='delete_cart_instance'),
    url(r'^request_edit_from_main/(?P<pk>[\w\-\ ]+)$', views.edit_request_main_page, name='request_edit_from_main'),
    
    ################################### API URLS #######################################
    url(r'^api/items/$', views.APIItemList.as_view(), name='api_item_list'),
    url(r'^api/items/(?P<pk>[\w\-\ ]+)/$', views.APIItemDetail.as_view(), name='api_item_detail'),
    url(r'^api/requests/$', views.APIRequestList.as_view()),
    url(r'^api/requests/create/(?P<pk>[\w\-\ ]+)/$', views.APIRequestThroughItem.as_view()),
    url(r'^api/requests/(?P<pk>[\w\-\ ]+)/$', views.APIRequestDetail.as_view()),
    url(r'^api/requests/approve/(?P<pk>[\w\-\ ]+)/$', views.APIApproveRequest.as_view()),
    url(r'^api/requests/deny/(?P<pk>[\w\-\ ]+)/$', views.APIDenyRequest.as_view()),
    url(r'^api/disbursements/$', views.APIDisbursementList.as_view()),
    url(r'^api/disbursements/direct/(?P<pk>[\w\-\ ]+)/$', views.APIDirectDisbursement.as_view()),
    url(r'^api/users/create/$', views.APICreateNewUser.as_view()),
    url(r'^api/tags/$', views.APITagList.as_view(), name='api_tag_list'),
    #url(r'^api/custom/field/$', views.APICustomField.as_view()),
    #url(r'^api/custom/field/modify/(?P<pk>[\w\-\ ]+)/$', views.APICustomFieldModify.as_view()),
]