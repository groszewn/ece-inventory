from django import forms
from .models import Request

#  request_id = models.CharField(primary_key=True, max_length=200)
#     user_id = models.CharField(max_length=200, null=False)
#     item_name = models.CharField(max_length=200, null=False)
#     request_quantity = models.SmallIntegerField(null=False)
#     status = models.CharField(max_length=200, null=False)
#     comment = models.CharField(max_length=200, null=False)
#     time_requested = models.TimeField()
class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ('request_id', 'item_name', 'request_quantity', 'comment') #temporarily add request_id until we figure out what to do