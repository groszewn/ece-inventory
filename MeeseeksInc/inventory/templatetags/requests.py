from django import template
from inventory import models

register = template.Library()

@register.inclusion_tag('admin/pending_requests.html')
def display_requests():
#     document = models.Document.objects.get(id__exact=document_id)
    requests = models.Request.objects.all()
#     requests = models.Request.objects.filter('time_requested')[0:5]
    return {'request_list': requests }