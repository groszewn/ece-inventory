from __future__ import absolute_import
import os
from celery import Celery
from django.conf import settings
from django.core import mail
from datetime import datetime
from django.core.mail import EmailMessage
from django.template import Context
from django.template.loader import render_to_string, get_template
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
    from inventory.models import Loan, EmailPrependValue, LoanReminderEmailBody
    from django.contrib.auth.models import User
    try:
        obj = LoanReminderEmailBody.objects.all()[0]
        body = obj.body
    except (ObjectDoesNotExist, IndexError) as e:
        obj = LoanReminderEmailBody.objects.create(body='')
        body = obj.body
    loan_dict={}
    for loan in Loan.objects.filter(status="Checked Out"):
        if loan.user_name not in loan_dict:
            loan_dict[loan.user_name] = []
        loan_dict[loan.user_name].append((loan.item_name.item_name, loan.total_quantity))
    for user in loan_dict:
        try:
            prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
        except (ObjectDoesNotExist, IndexError) as e:
            prepend = ''
        subject = prepend + 'Loan Reminder'
        to = [User.objects.get(username=loan.user_name).email]
        from_email='noreply@duke.edu'
        ctx = {
            'user': user,
            'body':body,
            'item_list':loan_dict[user],
        }
        message=render_to_string('inventory/loan_reminder_email.txt', ctx)
        EmailMessage(subject, message, bcc=to, from_email=from_email).send()
    return
    
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