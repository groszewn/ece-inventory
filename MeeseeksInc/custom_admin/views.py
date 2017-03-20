from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.core.mail import EmailMessage
from django.db import connection, transaction
from django.db import models
from django.db.models import F
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import render, get_object_or_404, redirect, get_list_or_404
from django.template.defaulttags import comment
from django.template import Context
from django.template.loader import render_to_string, get_template
from django.urls import reverse
from django.urls import reverse_lazy 
from django.utils import timezone
from django.views import generic
from django.views.generic.edit import FormView
from django.core.mail import send_mail
from django.core import mail
from django.conf import settings
from datetime import date, time, datetime, timedelta
from custom_admin.tasks import email as task_email

from custom_admin.forms import UserPermissionEditForm, DisburseSpecificForm, SubscribeForm, ChangeEmailPrependForm, RequestEditForm
from inventory.forms import RequestForm
from inventory.forms import SearchForm
from inventory.models import Instance, Request, Item, Disbursement, Tag, Log, Custom_Field, Custom_Field_Value, Loan, SubscribedUsers, EmailPrependValue

from .forms import EditTagForm, DisburseForm, ItemEditForm, CreateItemForm, RegistrationForm, AddCommentRequestForm, LogForm, AddTagForm, CustomFieldForm, DeleteFieldForm
from django.core.exceptions import ObjectDoesNotExist


def staff_check(user):
    return user.is_staff

def admin_check(user):
    return user.is_superuser

def active_check(user):
    return user.is_active

# from inventory.models import Instance, Request, Item, Disbursement
# from .forms import DisburseForm, ItemEditForm, RegistrationForm, AddCommentRequestForm, LogForm
################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class AdminIndexView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/index.html'
    context_object_name = 'instance_list'
    def get_context_data(self, **kwargs):
        context = super(AdminIndexView, self).get_context_data(**kwargs)
        tags = Tag.objects.all()
        context['form'] = SearchForm(tags)
        context['request_list'] = Request.objects.all()
        context['approved_request_list'] = Request.objects.filter(status="Approved")
        context['pending_request_list'] = Request.objects.filter(status="Pending")
        context['denied_request_list'] = Request.objects.filter(status="Denied")
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(admin_name=self.request.user.username)
        context['user_list'] = User.objects.all()
        context['loan_list'] = Loan.objects.all()
        context['current_user'] = self.request.user.username
        if self.request.user.is_staff or self.request.user.is_superuser:
            context['custom_fields'] = Custom_Field.objects.filter() 
        else:
            context['custom_fields'] = Custom_Field.objects.filter(is_private=False)
        context['tags'] = Tag.objects.distinct('tag')
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
    def test_func(self):
        return self.request.user.is_staff
    
class LogView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    login_url='/login/'
    permission_required = 'is_staff'
    template_name = 'custom_admin/log.html'
    context_object_name = 'log_list'
    context_object_name = 'request_list'
    context_object_name = 'item_list'
    def get_context_data(self, **kwargs):
        context = super(LogView, self).get_context_data(**kwargs)
        context['log_list'] = Log.objects.all()
        request_lst = []
        item_lst = []
        for log in Log.objects.all():
            if log.nature_of_event == "Request" and Request.objects.filter(request_id=log.request_id).exists():
                request_lst.append(log.request_id)
            if Item.objects.filter(item_id=log.item_id).exists():
                item_lst.append(log.item_id)
        context['request_list'] = request_lst
        context['item_list'] = item_lst
        return context
        
    def get_queryset(self):
        return Log.objects.all()
    def test_func(self):
        return self.request.user.is_staff
 
class DetailView(LoginRequiredMixin, UserPassesTestMixin, generic.DetailView): ## DetailView to display detail for the object
    login_url = "/login/"
    permission_required = 'is_staff'
    model = Instance
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html
    
    def test_func(self):
        return self.request.user.is_staff
 
class DisburseView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView): ## DetailView to display detail for the object
    login_url = "/login/"
    permission_required = 'is_staff'
    model = Instance
    template_name = 'custom_admin/single_disburse.html' # w/o this line, default would've been inventory/<model_name>.html
    
    def test_func(self):
        return self.request.user.is_staff
 
@login_required(login_url='/login/')
def add_custom_field(request):
    if request.method == 'POST':
        form = CustomFieldForm(request.POST)
        if form.is_valid():
            form.save()
            Log.objects.create(request_id=None, item_id=None, item_name="-", initiating_user = request.user, nature_of_event="Create", 
                               affected_user='', change_occurred='Added custom field ' + str(form['field_name'].value()))
            return redirect(reverse('custom_admin:index'))
    else:
        form = CustomFieldForm()
    return render(request, 'custom_admin/create_custom_field.html', {'form': form})

@login_required(login_url='/login/')
def delete_custom_field(request):
    fields = Custom_Field.objects.all()
    if request.method == 'POST':
        form = DeleteFieldForm(fields,request.POST)
        if form.is_valid():
            pickedFields = form.cleaned_data.get('fields')
            if pickedFields:
                for field in pickedFields:
                    delField = Custom_Field.objects.get(field_name = field)
                    Log.objects.create(request_id=None,item_id=None,  item_name='', initiating_user = request.user, nature_of_event="Delete", 
                                       affected_user='', change_occurred='Deleted custom field ' + str(field))
                    delField.delete()
            return redirect(reverse('custom_admin:index'))
    else:
        form = DeleteFieldForm(fields)
    return render(request, 'custom_admin/delete_custom_field.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(admin_check, login_url='/login/')
def register_page(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['admin']:
                user = User.objects.create_superuser(username=form.cleaned_data['username'],password=form.cleaned_data['password1'],email=form.cleaned_data['email'])
                user.save()
            elif form.cleaned_data['staff']:
                user = User.objects.create_user(username=form.cleaned_data['username'], password=form.cleaned_data['password1'], email=form.cleaned_data['email'], is_staff=True)
            else:
                user = User.objects.create_user(username=form.cleaned_data['username'],password=form.cleaned_data['password1'],email=form.cleaned_data['email'])
                user.save()
            Log.objects.create(request_id = None, item_id=None, item_name='', initiating_user=request.user, nature_of_event='Create', 
                                     affected_user=user.username, change_occurred="Created user")
            return HttpResponseRedirect('/customadmin')
        
        elif form['password1'].value() != form['password2'].value():
            messages.error(request, (" passwords do not match."))
        else:
            messages.error(request, (form['username'].value() + " has already been created."))
    else:
        form = RegistrationForm()
    return render(request, 'custom_admin/register_user.html', {'form': form})

class UserListView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/user_list.html'
    context_object_name = 'user_list'
    def get_context_data(self, **kwargs):
        context = super(UserListView, self).get_context_data(**kwargs)
        context['user_list'] = User.objects.all()
        # And so on for more models
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
    def test_func(self):
        return self.request.user.is_staff

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_request_accept(request, pk):
    if request.method == "POST":
        form = AddCommentRequestForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            comment = form['comment'].value()
            indiv_request = Request.objects.get(request_id=pk)
            item = Item.objects.get(item_name=indiv_request.item_name)
            if item.quantity >= indiv_request.request_quantity:
                # decrement quantity in item
                item.quantity = F('quantity')-indiv_request.request_quantity
                item.save()
                 
                # change status of request to approved
                indiv_request.status = "Approved"
                indiv_request.comment = comment
                indiv_request.save()
                 
                # add new disbursement item to table
                disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_name = indiv_request.item_name), 
                                            total_quantity=indiv_request.request_quantity, comment=comment, time_disbursed=timezone.localtime(timezone.now()))
                disbursement.save()
                Log.objects.create(request_id=disbursement.disburse_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Approve", affected_user=indiv_request.user_id, change_occurred="Disbursed " + str(indiv_request.request_quantity))
                messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Request approval'
                to = [User.objects.get(username=disbursement.user_name).email]
                from_email='noreply@duke.edu'
                ctx = {
                    'user':User.objects.get(username=disbursement.user_name).username,
                    'item':disbursement.item_name,
                    'quantity':disbursement.total_quantity,
                }
                message=render_to_string('inventory/request_approval_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            else:
                messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            return redirect(reverse('custom_admin:index'))  
    else:
        form = AddCommentRequestForm() # blank request form with no data yet
    return render(request, 'custom_admin/request_accept_comment_inner.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def edit_item_module(request, pk):
    item = Item.objects.get(item_id=pk)
    custom_fields = Custom_Field.objects.all()
    custom_vals = Custom_Field_Value.objects.filter(item = item)
    original_quantity = item.quantity
    if request.method == "POST":
        form = ItemEditForm(request.user, custom_fields, custom_vals, request.POST or None, instance=item)
        if form.is_valid():
            if int(form['quantity'].value())!=original_quantity:    
                Log.objects.create(request_id = None, item_id=str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Override', 
                                         affected_user='', change_occurred="Change quantity from " + str(original_quantity) + ' to ' + str(form['quantity'].value()))
            else:
                Log.objects.create(request_id=None, item_id = str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user='', change_occurred="Edited " + str(form['item_name'].value()))
            form.save()
            for field in custom_fields:
                field_value = form[field.field_name].value()
                if Custom_Field_Value.objects.filter(item = item, field = field).exists():
                    custom_val = Custom_Field_Value.objects.get(item = item, field = field)
                else:
                    custom_val = Custom_Field_Value(item=item, field=field)
                if field.field_type == 'Short':    
                    custom_val.field_value_short_text = field_value
                if field.field_type == 'Long':
                    custom_val.field_value_long_text = field_value
                if field.field_type == 'Int':
                    if field_value != '':
                        custom_val.field_value_integer = field_value
                    else:
                        custom_val.field_value_integer = None
                if field.field_type == 'Float':
                    if field_value != '':
                        custom_val.field_value_floating = field_value 
                    else:
                        custom_val.field_value_floating = None
                custom_val.save()
            messages.success(request, ('Edited ' + item.item_name + '. (' + request.user.username +')'))
            return redirect('/item/' + pk)
    else:
        form = ItemEditForm(request.user, custom_fields, custom_vals, instance=item)
    return render(request, 'custom_admin/item_edit_module_inner.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_request_accept(request, pk):
    if request.method == "POST":
        form = AddCommentRequestForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            comment = form['comment'].value()
            indiv_request = Request.objects.get(request_id=pk)
            item = Item.objects.get(item_name=indiv_request.item_name)
            if item.quantity >= indiv_request.request_quantity:
                # decrement quantity in item
                item.quantity = F('quantity')-indiv_request.request_quantity
                item.save()
                 
                # change status of request to approved
                indiv_request.status = "Approved"
                indiv_request.comment = comment
                indiv_request.save()
                
                if indiv_request.type == "Disbursal": 
                    # add new disbursement item to table
                    disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_name = indiv_request.item_name), 
                                            total_quantity=indiv_request.request_quantity, comment=comment, time_disbursed=timezone.localtime(timezone.now()))
                    disbursement.save()
                    messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                    Log.objects.create(request_id=disbursement.disburse_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Approve", affected_user=indiv_request.user_id, change_occurred="Disbursed " + str(indiv_request.request_quantity))
                elif indiv_request.type == "Loan":
                    loan = Loan(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_name = indiv_request.item_name), 
                                            total_quantity=indiv_request.request_quantity, comment=comment, time_loaned=timezone.localtime(timezone.now()))
                    loan.save()
                    messages.success(request, ('Successfully loaned ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                    # add log object
                
            else:
                messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            return redirect(reverse('custom_admin:index'))  
    else:
        form = AddCommentRequestForm() # blank request form with no data yet
    return render(request, 'custom_admin/request_accept_comment_inner.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_request_deny(request, pk):
    if request.method == "POST":
        form = AddCommentRequestForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            comment = form['comment'].value()
            indiv_request = Request.objects.get(request_id=pk)
            indiv_request.status = "Denied"
            indiv_request.comment = comment
            indiv_request.save()
            id = indiv_request.item_name.item_id
            Log.objects.create(request_id=indiv_request.request_id, item_id=id, item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
            messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Request denial'
            to = [User.objects.get(username=indiv_request.user_id).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':User.objects.get(username=indiv_request.user_id),
                'item':indiv_request.item_name,
                'quantity':indiv_request.request_quantity,
                'comment':comment,
            }
            message=render_to_string('inventory/request_denial_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return redirect(reverse('custom_admin:index'))  
    else:
        form = AddCommentRequestForm() # blank request form with no data yet
    return render(request, 'custom_admin/request_deny_comment_inner.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def convert_loan(request, pk):
    if request.method == "POST":
        form = ConvertLoanForm(request.POST)
        if form.is_valid():
            loan = Loan.objects.get(loan_id=pk)
            if form.cleaned_data.get('convert_to_disburse_checkbox'):
                admin_name = request.user.username
                user_name = loan.user_name
                item = loan.item_name
                quantity = loan.total_quantity
                comment = loan.comment
                time_disbursed = timezone.localtime(timezone.now())
                loan.delete()
                disbursement = Disbursement(admin_name=admin_name, user_name=user_name, item_name=item, comment=comment, total_quantity=quantity, time_disbursed=time_disbursed)
                disbursement.save()
                
                # ADD A LOG ENTRY
                messages.success(request, ('Converted loan of ' + loan.item_name.item_name + ' to disbursement. (' + loan.user_name +')'))
                return redirect(reverse('custom_admin:index'))  
    else:
        form = ConvertLoanForm() 
    return render(request, 'custom_admin/convert_loan_inner.html', {'form': form, 'pk':pk})


@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def post_new_request(request):
    if request.method == "POST":
        form = RequestForm(request.POST) # create request-form with the data from the request 
        if form.is_valid():
            post = form.save(commit=False)
            post.item_id = form['item_field'].value()
            post.item_name = Item.objects.get(item_id = post.item_id)
            post.user_id = request.user.username
            post.status = "Pending"
            post.time_requested = timezone.now()
            post.save()
            Log.objects.create(request_id = str(post.request_id), item_name=str(post.item_name), initiating_user=post.user_id, nature_of_event='Request', 
                                         affected_user='', change_occurred="Requested " + str(form['request_quantity'].value()))
            messages.success(request, ('Successfully posted new request for ' + post.item_name.item_name + ' (' + post.user_id +')'))
            request_list=[]
            request_list.append((post.item_name, form['request_quantity'].value()))
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Request confirmation'
            to = [User.objects.get(username=post.user_id).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':post.user_id,
                'request':request_list,
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/request_confirmation_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return redirect('/customadmin')
    else:
        form = RequestForm() # blank request form with no data yet
    return render(request, 'inventory/request_create.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def edit_request_main_page(request, pk):
    instance = Request.objects.get(request_id=pk)
    if request.method == "POST":
        form = RequestEditForm(request.POST, instance=instance, initial = {'item_field': instance.item_name})
        change_list=[]
        if form['request_quantity'].value() != instance.request_quantity:
            change_list.append(('request quantity', instance.request_quantity, form['request_quantity'].value()))
        if form['reason'].value() != instance.reason:
            change_list.append(('reason', instance.reason, form['reason'].value()))
        if form.is_valid():
            messages.success(request, 'You just edited the request successfully.')
            post = form.save(commit=False)
#             post.item_id = form['item_field'].value()
#             post.item_name = Item.objects.get(item_id = post.item_id)
            post.status = "Pending"
            post.time_requested = timezone.now()
            post.save()
            Log.objects.create(request_id = str(instance.request_id), item_id=instance.item_name.item_id, item_name=str(post.item_name), initiating_user=str(post.user_id), nature_of_event='Edit', 
                                         affected_user='', change_occurred="Edited request for " + str(post.item_name))
            item = instance.item_name
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Request edit'
            to = [User.objects.get(username=instance.user_id).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':instance.user_id,
                'changes':change_list,
            }
            message=render_to_string('inventory/request_edit_email.txt', ctx)
            if len(change_list)>0:
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return redirect('/customadmin')
    else:
        form = RequestEditForm(instance=instance, initial = {'item_field': instance.item_name})
    return render(request, 'inventory/request_edit.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def post_new_disburse(request):
    if request.method == "POST":
        form = DisburseForm(request.POST) # create request-form with the data from the request
        
        if form.is_valid():
            post = form.save(commit=False)
            post.admin_name = request.user.username
            id_requested = form['item_field'].value()
            item = Item.objects.get(item_id=id_requested)
            post.item_name = item
            post.user_name = User.objects.get(id=form['user_field'].value()).username
            post.time_disbursed = timezone.localtime(timezone.now())
            if item.quantity >= int(form['total_quantity'].value()):
                # decrement quantity in item
                quant_change = int(form['total_quantity'].value())
                item.quantity = F('quantity')-int(form['total_quantity'].value()) 
                item.save()
                Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Disburse', 
                                         affected_user=post.user_name, change_occurred="Disbursed " + str(quant_change))
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Direct disbursal'
                to = [User.objects.get(username=post.user_name).email]
                from_email='noreply@duke.edu'
                ctx = {
                    'user':post.user_name,
                    'item':item.item_name,
                    'quantity':quant_change,
                    'disburser':request.user.username,
                }
                message=render_to_string('inventory/disbursement_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            else:
                messages.error(request, ('Not enough stock available for ' + item.item_name + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
                return redirect(reverse('custom_admin:index'))
            post.save()
            messages.success(request, 
                                 ('Successfully disbursed ' + form['total_quantity'].value() + " " + item.item_name + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
        
            return redirect('/customadmin')
    else:
        form = DisburseForm() # blank request form with no data yet
    return render(request, 'custom_admin/single_disburse_inner.html', {'form': form})
 
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def post_new_disburse_specific(request, pk):
    if request.method == "POST":
        form = DisburseSpecificForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            item = Item.objects.get(item_id=pk)
            user_name = User.objects.get(id=form['user_field'].value()).username
            if item.quantity >= int(form['total_quantity'].value()):
                # decrement quantity in item
                quant_change = int(form['total_quantity'].value())
                item.quantity = F('quantity')-int(form['total_quantity'].value()) 
                item.save()
                Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Disburse', 
                                         affected_user=user_name, change_occurred="Disbursed " + str(quant_change))
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Direct disbursal'
                to = [User.objects.get(username=user_name).email]
                from_email='noreply@duke.edu'
                ctx = {
                    'user':user_name,
                    'item':item.item_name,
                    'quantity':quant_change,
                    'disburser':request.user.username,
                }
                message=render_to_string('inventory/disbursement_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            else:
                messages.error(request, ('Not enough stock available for ' + item.item_name + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
                return redirect(reverse('custom_admin:index'))
            disbursement = Disbursement(admin_name=request.user.username, user_name=user_name, item_name=item, comment=form['comment'].value(),
                                        total_quantity=form['total_quantity'].value(), time_disbursed=timezone.localtime(timezone.now()))
            disbursement.save()
            messages.success(request, 
                                 ('Successfully disbursed ' + form['total_quantity'].value() + " " + item.item_name + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
        
            return redirect('/item/'+pk)
    else:
        form = DisburseSpecificForm() # blank request form with no data yet
    return render(request, 'custom_admin/specific_disburse_inner.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def approve_all_requests(request):
    pending_requests = Request.objects.filter(status="Pending")
    if not pending_requests:
        messages.error(request, ('No requests to accept!'))
        return redirect(reverse('custom_admin:index'))
    for indiv_request in pending_requests:
        item = get_object_or_404(Item,item_name=indiv_request.item_name.item_name)
        if item.quantity >= indiv_request.request_quantity:
            # decrement quantity in item
            item.quantity = F('quantity')-indiv_request.request_quantity
            item.save()
             
            # change status of request to approved
            indiv_request.status = "Approved"
            indiv_request.save()
             
            # add new disbursement item to table
            # TODO: add comments!!
            disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_id = indiv_request.item_name_id), 
                                        total_quantity=indiv_request.request_quantity, time_disbursed=timezone.localtime(timezone.now()))
            disbursement.save()
            Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Approve", 
                       affected_user=indiv_request.user_id, change_occurred="Disbursed " + str(indiv_request.request_quantity))
            messages.add_message(request, messages.SUCCESS, 
                                 ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Request approval'
            to = [User.objects.get(username=indiv_request.user_id).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':indiv_request.user_id,
                'item':disbursement.item_name,
                'quantity': disbursement.total_quantity,
            }
            message=render_to_string('inventory/request_approval_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
        else:
            messages.add_message(request, messages.ERROR, 
                                 ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
         
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def deny_all_request(request):
    pending_requests = Request.objects.filter(status="Pending")
    if not pending_requests:
        messages.error(request, ('No requests to deny!'))
        return redirect(reverse('custom_admin:index'))
    for indiv_request in pending_requests:
        indiv_request.status = "Denied"
        id = indiv_request.item_name.item_id
        Log.objects.create(request_id =indiv_request.request_id, item_id=id, item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
        indiv_request.save()
    messages.success(request, ('Denied all disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    return redirect(reverse('custom_admin:index'))
 
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def approve_request(request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    item = Item.objects.get(item_id=indiv_request.item_name_id)
    if item.quantity >= indiv_request.request_quantity:
        # decrement quantity in item
        item.quantity = F('quantity')-indiv_request.request_quantity
        item.save()
         
        # change status of request to approved
        indiv_request.status = "Approved"
        indiv_request.comment = request.POST.get('comment')
        indiv_request.save()
         
        # add new disbursement item to table
        # TODO: add comments!!
        disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_id = indiv_request.item_name_id), 
                                    total_quantity=indiv_request.request_quantity, comment=indiv_request.comment, time_disbursed=timezone.localtime(timezone.now()))
        disbursement.save()
        Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Approve', 
                                         affected_user=indiv_request.user_id, change_occurred="Approved request for " + str(indiv_request.request_quantity))
        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
        try:
            prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
        except (ObjectDoesNotExist, IndexError) as e:
            prepend = ''
        subject = prepend + 'Request approval'
        to = [User.objects.get(username=indiv_request.user_id).email]
        from_email='noreply@duke.edu'
        ctx = {
            'user':indiv_request.user_id,
            'item':disbursement.item_name,
            'quantity': disbursement.total_quantity,
        }
        message=render_to_string('inventory/request_approval_email.txt', ctx)
        EmailMessage(subject, message, bcc=to, from_email=from_email).send()
    else:
        messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
        return redirect(reverse('custom_admin:index'))
 
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def deny_request(request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    indiv_request.status = "Denied"
    indiv_request.save()
    id = indiv_request.item_name.item_id
    Log.objects.create(request_id=indiv_request.request_id, item_id=id,  item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
    messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def edit_item(request, pk):
    item = Item.objects.get(item_id=pk)
    custom_fields = Custom_Field.objects.all()
    custom_vals = Custom_Field_Value.objects.filter(item = item)
    original_quantity = item.quantity
    if request.method == "POST":
        form = ItemEditForm(request.user, custom_fields, custom_vals, request.POST or None, instance=item)
        if form.is_valid():
            if int(form['quantity'].value())!=original_quantity:    
                Log.objects.create(request_id = None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Override', 
                                         affected_user='', change_occurred="Change quantity from " + str(original_quantity) + ' to ' + str(form['quantity'].value()))
            else:
                Log.objects.create(request_id = None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user='', change_occurred="Edited " + str(form['item_name'].value()))
            form.save()
            for field in custom_fields:
                field_value = form[field.field_name].value()
                if Custom_Field_Value.objects.filter(item = item, field = field).exists():
                    custom_val = Custom_Field_Value.objects.get(item = item, field = field)
                else:
                    custom_val = Custom_Field_Value(item=item, field=field)
                if field.field_type == 'Short':    
                    custom_val.field_value_short_text = field_value
                if field.field_type == 'Long':
                    custom_val.field_value_long_text = field_value
                if field.field_type == 'Int':
                    if field_value != '':
                        custom_val.field_value_integer = field_value
                    else:
                        custom_val.field_value_integer = None
                if field.field_type == 'Float':
                    if field_value != '':
                        custom_val.field_value_floating = field_value 
                    else:
                        custom_val.field_value_floating = None
                custom_val.save()
            return redirect('/item/' + pk)
    else:
        form = ItemEditForm(request.user, custom_fields, custom_vals, instance=item)
    return render(request, 'inventory/item_edit.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(admin_check, login_url='/login/')
def edit_permission(request, pk):
    user = User.objects.get(username = pk)
    if request.method == "POST":
        form = UserPermissionEditForm(request.POST or None, instance=user)
        if form.is_valid():       
            form.save()
            Log.objects.create(request_id = None, item_id=None, item_name='', initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user=user.username, change_occurred="Changed permissions for " + str(user.username))
            return redirect('/customadmin')
    else:
        form = UserPermissionEditForm(instance = user, initial = {'username': user.username})
    return render(request, 'custom_admin/user_edit.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_tags(request, pk):
    if request.method == "POST":
        item = Item.objects.get(item_id = pk)
        tags = Tag.objects.all()
#         item_tags = Tag.objects.filter(item_name = item)
        item_tags = item.tags.all()
        form = AddTagForm(tags, item_tags, request.POST or None)
        if form.is_valid():
            pickedTags = form.cleaned_data.get('tag_field')
            createdTags = form['create_new_tags'].value()
            item = Item.objects.get(item_id=pk)
            if pickedTags:
                for oneTag in pickedTags:
#                     if not Tag.objects.filter(item_name=item, tag=oneTag).exists():
                    if not item.tags.filter(tag=oneTag).exists():
                        t = Tag(tag=oneTag) 
                        t.save(force_insert=True)
                        item.tags.add(t)
                        item.save()
            if createdTags is not "":
                tag_list = [x.strip() for x in createdTags.split(',')]
                for oneTag in tag_list:
                    if not item.tags.filter(tag=oneTag).exists():
                        t = Tag(tag=oneTag)
                        t.save(force_insert=True)
                        item.tags.add(t)
                        item.save()
            for ittag in item_tags:
                ittag.tag = form[ittag.tag].value()
                ittag.save()
            return redirect('/item/' + pk)
    else:
        item = Item.objects.get(item_id = pk)
        tags = Tag.objects.all()
        item_tags = item.tags.all()
        form = AddTagForm(tags, item_tags)
    return render(request, 'inventory/add_tags.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_tags_module(request, pk):
    if request.method == "POST":
        item = Item.objects.get(item_id = pk)
        tags = Tag.objects.all()
#         item_tags = Tag.objects.filter(item_name = item)
        item_tags = item.tags.all()
        form = AddTagForm(tags, item_tags, request.POST or None)
        if form.is_valid():
            pickedTags = form.cleaned_data.get('tag_field')
            createdTags = form['create_new_tags'].value()
            item = Item.objects.get(item_id=pk)
            if pickedTags:
                for oneTag in pickedTags:
#                     if not Tag.objects.filter(item_name=item, tag=oneTag).exists():
                    if not item.tags.filter(tag=oneTag).exists():
                        t = Tag(tag=oneTag) 
                        t.save(force_insert=True)
                        item.tags.add(t)
                        item.save()
            if createdTags is not "":
                tag_list = [x.strip() for x in createdTags.split(',')]
                for oneTag in tag_list:
                    if not item.tags.filter(tag=oneTag).exists():
                        t = Tag(tag=oneTag)
                        t.save(force_insert=True)
                        item.tags.add(t)
                        item.save()
            for ittag in item_tags:
                ittag.tag = form[ittag.tag].value()
                ittag.save()
            return redirect('/item/' + pk)
    else:
        item = Item.objects.get(item_id = pk)
        tags = Tag.objects.all()
        item_tags = item.tags.all()
        form = AddTagForm(tags, item_tags)
    return render(request, 'custom_admin/add_tags_module_inner.html', {'form': form,'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def log_item(request):
    form = LogForm(request.POST or None)
    if request.method=="POST":
        form = LogForm(request.POST)
        if form.is_valid():
            item = Item.objects.get(item_id=form['item_name'].value())
            change_type = form['item_change_status'].value()
            amount = int(form['item_amount'].value())
            if change_type == 'Acquired':  # this correlates to the item_change_option numbers for the tuples
                item.quantity = F('quantity')+amount
                Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Acquire", 
                                   affected_user='', change_occurred="Acquired " + str(amount))
                item.save()
                messages.success(request, ('Successfully logged ' + str(item.item_name) + ' (added ' + str(amount) +')'))
            elif change_type == "Broken":
                if item.quantity >= amount:
                    item.quantity = F('quantity')-amount
                    item.save()
                    Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Broken", 
                                       affected_user='', change_occurred="Broke " + str(amount))
                    messages.success(request, ('Successfully logged ' + item.item_name + ' (removed ' + str(amount) +')'))
                else:
                    messages.error(request, ("You can't break more of " + item.item_name + " than you have."))
                    return redirect(reverse('custom_admin:index'))
            elif change_type == "Lost":
                if item.quantity >= amount:
                    item.quantity = F('quantity')-amount
                    item.save()
                    Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Lost", 
                                       affected_user='', change_occurred="Lost " + str(amount))
                    messages.success(request, ('Successfully logged ' + item.item_name + ' (removed ' + str(amount) +')'))
                else:
                    messages.error(request, ("You can't lose more of " + item.item_name + " than you have."))
                    return redirect(reverse('custom_admin:index'))
            form.save()
            return redirect('/customadmin')
        else:
            messages.error(request, ('Please enter a valid value in order to submit this form.'))
    return render(request, 'inventory/log_item.html', {'form': form})

@login_required(login_url='/login/')    
@user_passes_test(active_check, login_url='/login/')
def api_guide_page(request):
    return render(request, 'custom_admin/api_guide.html')

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def edit_tag(request, pk, item):
    tag = Tag.objects.get(id=pk)
    item = Item.objects.get(item_id=item)
    if request.method == "POST":
        form = EditTagForm(request.POST or None, instance=tag)
        if form.is_valid():
            form.save()
            return redirect('/item/' + item.item_id)
    else:
        form = EditTagForm(instance=tag)
    return render(request, 'inventory/tag_edit.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def edit_specific_tag(request, pk, item):
    tag = Tag.objects.get(id=pk)
    item = Item.objects.get(item_id=item)
    if request.method == "POST":
        form = EditTagForm(request.POST or None, instance=tag)
        if form.is_valid():
            form.save()
            return redirect('/item/' + item.item_id)
    else:
        form = EditTagForm(instance=tag)
    return render(request, 'custom_admin/edit_tag_module_inner.html', {'form': form,'pk':pk,'item':item.item_id})

@login_required(login_url='/login/')
@user_passes_test(admin_check, login_url='/login/')
def delete_item(request, pk):
    item = Item.objects.get(item_id=pk)
    Log.objects.create(request_id=None, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user='', change_occurred="Deleted item " + str(item.item_name))
    item.delete()
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def delete_tag(request, pk, item):
    item = Item.objects.get(item_id=item)
    tag = Tag.objects.get(id=pk)
    tag.delete()
    return redirect('/item/' + item.item_id)
 
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def create_new_item(request):
    tags = Tag.objects.all()
    custom_fields = Custom_Field.objects.all()
    if request.method== 'POST':
        form = CreateItemForm(tags, custom_fields, request.POST or None)
        if form.is_valid():
            post = form.save(commit=False)
            pickedTags = form.cleaned_data.get('tag_field')
            createdTags = form['new_tags'].value()
            post.save()
            messages.success(request, (form['item_name'].value() + " created successfully."))
            item = Item.objects.get(item_name = form['item_name'].value())
            Log.objects.create(request_id=None, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Create", 
                       affected_user='', change_occurred="Created item " + str(item.item_name))
            if pickedTags:
                for oneTag in pickedTags:
                    t = Tag(tag=oneTag)
                    t.save(force_insert=True)
                    item.tags.add(t)
                    item.save()
            if createdTags is not "":
                tag_list = [x.strip() for x in createdTags.split(',')]
                for oneTag in tag_list:
                    t = Tag(tag=oneTag)
                    t.save()
                    item.tags.add(t)
                    item.save()
            for field in custom_fields:
                field_value = form[field.field_name].value()
                custom_val = Custom_Field_Value(item=item, field=field)
                if field.field_type == 'Short':    
                    custom_val.field_value_short_text = field_value
                if field.field_type == 'Long':
                    custom_val.field_value_long_text = field_value
                if field.field_type == 'Int':
                    if field_value != '':
                        custom_val.field_value_integer = field_value
                    else:
                        custom_val.field_value_floating = None
                if field.field_type == 'Float':
                    if field_value != '':
                        custom_val.field_value_floating = field_value
                    else:
                        custom_val.field_value_floating = None
                custom_val.save()
            return redirect('/customadmin')
        else:
            messages.error(request, (form['item_name'].value() + " has already been created."))
    else:
        form = CreateItemForm(tags, custom_fields)
    return render(request, 'custom_admin/item_create.html', {'form':form,})
 
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def deny_request(request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    indiv_request.status = "Denied"
    indiv_request.save()
    id = indiv_request.item_name.item_id
    Log.objects.create(request_id=indiv_request.request_id, item_id=id,  item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
    messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    try:
        prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
    except (ObjectDoesNotExist, IndexError) as e:
        prepend = ''
    subject = prepend + 'Request denial'
    to = [User.objects.get(username=indiv_request.user_id).email]
    from_email='noreply@duke.edu'
    ctx = {
        'user':indiv_request.user_id,
        'item':indiv_request.item_name,
        'quantity':indiv_request.request_quantity,
        'comment': indiv_request.comment,
    }
    message=render_to_string('inventory/request_denial_email.txt', ctx)
    EmailMessage(subject, message, bcc=to, from_email=from_email).send()
    return redirect(reverse('custom_admin:index'))
 
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def deny_all_request(request):
    pending_requests = Request.objects.filter(status="Pending")
    if not pending_requests:
        messages.error(request, ('No requests to deny!'))
        return redirect(reverse('custom_admin:index'))
    for indiv_request in pending_requests:
        indiv_request.status = "Denied"
        id = indiv_request.item_name.item_id
        Log.objects.create(request_id =indiv_request.request_id, item_id=id, item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
        indiv_request.save()
        try:
            prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
        except (ObjectDoesNotExist, IndexError) as e:
            prepend = ''
        subject = prepend + 'Request denial'
        to = [User.objects.get(username=indiv_request.user_id).email]
        from_email='noreply@duke.edu'
        ctx = {
            'user':indiv_request.user_id,
            'item':indiv_request.item_name,
            'quantity':indiv_request.request_quantity,
            'comment': indiv_request.comment,
        }
        message=render_to_string('inventory/request_denial_email.txt', ctx)
        EmailMessage(subject, message, bcc=to, from_email=from_email).send()
    messages.success(request, ('Denied all disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    return redirect(reverse('custom_admin:index'))
 
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def subscribe(request):
    exists = SubscribedUsers.objects.filter(user=request.user.username).exists()
    if request.method == "POST":
        form = SubscribeForm(request.POST or None, initial = {'subscribed': exists})
        if form.is_valid():  
            if form['subscribed'].value():
                try:
                    SubscribedUsers.objects.get(user=request.user.username)
                except ObjectDoesNotExist:
                    SubscribedUsers.objects.create(user=request.user.username, email=request.user.email)
            else:
                try:
                    subscribeduser = SubscribedUsers.objects.get(user=request.user.username)
                except ObjectDoesNotExist:
                    return redirect('/customadmin')
                subscribeduser.delete()
            return redirect('/customadmin')
    else:
        form = SubscribeForm(initial = {'subscribed': exists})
    return render(request, 'custom_admin/subscribe.html', {'form': form}) 
 

def delay_email(request):
    #task_email.apply_async(eta=datetime.now()+timedelta(seconds=5))
    task_email.apply_async(eta=datetime.utcnow()+timedelta(minutes=1))
    return redirect(reverse('custom_admin:log'))
 
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def create_email(request):
    email = mail.EmailMessage(
        'Testing delayed email', 
        'Body goes here', 
        'noreply@duke.edu', 
        ['nrg12@duke.edu'], 
    )
    email.send(fail_silently=False)
    return redirect(reverse('custom_admin:log'))

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def change_email_prepend(request):
    try:
        text = EmailPrependValue.objects.all()[0].prepend_text
    except (ObjectDoesNotExist, IndexError) as e:
        text=''
    if request.method == "POST":
        form = ChangeEmailPrependForm(request.POST or None, initial={'text': text})
        if form.is_valid():
            if form['text'].value() == text:
                return redirect('/customadmin')
            else:
                EmailPrependValue.objects.all().delete()
                EmailPrependValue.objects.create(prepend_text=form['text'].value())
            return redirect('/customadmin')
    else:
        form = ChangeEmailPrependForm(initial={'text':text})
    return render(request, 'custom_admin/change_prepend.html', {'form': form})

################### DJANGO CRIPSY FORM STUFF ###################
class AjaxTemplateMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(self, 'ajax_template_name'):
            split = self.template_name.split('.html')
            split[-1] = '_inner'
            split.append('.html')
            self.ajax_template_name = ''.join(split)
        if request.is_ajax():
            self.template_name = self.ajax_template_name
        return super(AjaxTemplateMixin, self).dispatch(request, *args, **kwargs)
 
class DisburseFormView(SuccessMessageMixin, AjaxTemplateMixin, FormView):
    model = Disbursement
    template_name = 'custom_admin/single_disburse.html'
    form_class = DisburseForm # do new form
    success_url = reverse_lazy('custom_admin:index')
    success_message = "Way to go!"
    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
#         form.send_email()
        post = form.save(commit=False)
        post.admin_name = self.request.user.username
        name_requested = form['item_field'].value()
        post.item_name = Item.objects.get(item_name = name_requested)
        post.user_name = User.objects.get(id=form['user_field'].value()).username
        post.time_disbursed = timezone.localtime(timezone.now())
        post.save()
        disbursement = Disbursement.objects.get(item_name = post.item_name)
        Log.objects.create(request_id=None, item_id=post.item_name.item_id, item_name=disbursement.item_name, initiating_user=disbursement.admin_name, nature_of_event='Disburse', 
                                         affected_user=disbursement.user_name, change_occurred="Disbursed " + str(disbursement.total_quantity))
        messages.success(self.request, 
                                 ('Successfully disbursed ' + form['total_quantity'].value() + " " + name_requested + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
        try:
            prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
        except (ObjectDoesNotExist, IndexError) as e:
            prepend = ''
        subject = prepend + 'Direct disbursal'
        to = [User.objects.get(username=post.user_name).email]
        from_email='noreply@duke.edu'
        ctx = {
            'user':post.user_name,
            'item':disbursement.item_name,
            'quantity':disbursement.total_quantity,
            'disburser':request.user.username,
        }
        message=render_to_string('inventory/disbursement_email.txt', ctx)
        EmailMessage(subject, message, bcc=to, from_email=from_email).send()
        return super(DisburseFormView, self).form_valid(form)

class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated():
            return User.objects.none()

        qs = User.objects.filter(is_staff="False")

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs  
################################################################