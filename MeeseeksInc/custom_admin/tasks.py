from __future__ import absolute_import
import os
from celery import Celery
from django.conf import settings
from django.core import mail
from datetime import datetime
#from inventory.models import Loan
# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MeeseeksInc.settings')

app = Celery('MeeseeksInc')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
#from inventory.models import Request


@app.task
def test(param):
    return 'The test task executed with argument " %s" ' % param

@app.task
def loan_reminder_email():
    pass
    
@app.task
def email():
    email = mail.EmailMessage(
        'Testing delayed email', 
        'Sent at '+ str(datetime.utcnow()), 
        'noreply@duke.edu', 
        ['nrg12@duke.edu'], 
    )
    email.send(fail_silently=False)
    return "DONE"