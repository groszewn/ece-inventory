from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.db import connection, transaction
from django.db import models
from django.db.models import F
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import render, get_object_or_404, redirect, get_list_or_404
from django.template.defaulttags import comment
from django.urls import reverse
from django.urls import reverse_lazy 
from django.utils import timezone
from django.views import generic
from django.views.generic.edit import FormView

from custom_admin.forms import UserPermissionEditForm
from inventory.forms import SearchForm
from inventory.models import Instance, Request, Item, Disbursement, Tag, Log, Custom_Field, Custom_Field_Value

def staff_check(user):
    return user.is_staff

def admin_check(user):
    return user.is_superuser
    

from .forms import EditTagForm, DisburseForm, ItemEditForm, CreateItemForm, RegistrationForm, AddCommentRequestForm, LogForm, AddTagForm
from .forms import EditTagForm, DisburseForm, ItemEditForm, CreateItemForm, RegistrationForm, AddCommentRequestForm, LogForm, AddTagForm, CustomFieldForm, DeleteFieldForm


# from inventory.models import Instance, Request, Item, Disbursement
# from .forms import DisburseForm, ItemEditForm, RegistrationForm, AddCommentRequestForm, LogForm
################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class AdminIndexView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/index.html'
    context_object_name = 'instance_list'
    def get_context_data(self, **kwargs):
        context = super(AdminIndexView, self).get_context_data(**kwargs)
        cursor = connection.cursor()
        cursor.execute('select inventory_item.item_name, array_agg(inventory_request.request_id order by inventory_request.status desc) from inventory_request join inventory_item on inventory_item.item_id = inventory_request.item_name_id group by inventory_item.item_name')
        raw_request_list = cursor.fetchall()
        for raw_request in raw_request_list:
            raw_request_ids = raw_request[1] # all the ids in this item
            counter = 0
            for request_ID in raw_request_ids:
                raw_request[1][counter] = Request.objects.get(request_id=request_ID)
                counter += 1
        tags = Tag.objects.all()
        context['form'] = SearchForm(tags)
#         context['request_list'] = raw_request_list
        context['request_list'] = Request.objects.all()
        context['approved_request_list'] = Request.objects.filter(status="Approved")
        context['pending_request_list'] = Request.objects.filter(status="Pending")
        context['denied_request_list'] = Request.objects.filter(status="Denied")
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(admin_name=self.request.user.username)
        context['custom_fields'] = Custom_Field.objects.all()
        context['custom_vals'] = Custom_Field_Value.objects.all()
        context['user_list'] = User.objects.all()
        # And so on for more models
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
    def get_context_data(self, **kwargs):
        context = super(LogView, self).get_context_data(**kwargs)
        context['log_list'] = Log.objects.all()
        lst = []
        for log in Log.objects.all():
            if log.nature_of_event == "Request" and Request.objects.filter(request_id=log.reference_id).exists():
                lst.append(log.reference_id)
        context['request_list'] = lst
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
 
#####################################################################

@login_required(login_url='/login/')
def add_custom_field(request):
    if request.method == 'POST':
        form = CustomFieldForm(request.POST)
        if form.is_valid():
            form.save()
            Log.objects.create(reference_id=None, item_name="ALL", initiating_user = request.user, nature_of_event="Create", 
                               affected_user=None, change_occurred='Added custom field ' + str(form['field_name'].value()))
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
                    delField.delete()
                    Log.objects.create(reference_id=None, item_name="ALL", initiating_user = request.user, nature_of_event="Delete", 
                                       affected_user=None, change_occurred='Deleted custom field ' + str(field))
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
            else:
                user = User.objects.create_user(username=form.cleaned_data['username'],password=form.cleaned_data['password1'],email=form.cleaned_data['email'])
                user.save()
            Log.objects.create(reference_id = None, item_name=None, initiating_user=request.user, nature_of_event='Create', 
                                     affected_user=user.username, change_occurred="Created user")
            return HttpResponseRedirect('/customadmin')
        
        elif form['password1'].value() != form['password2'].value():
            messages.error(request, (" passwords do not match."))
        else:
            messages.error(request, (form['username'].value() + " has already been created."))
    else:
        form = RegistrationForm()
    return render(request, 'custom_admin/register_user.html', {'form': form})

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
                Log.objects.create(reference_id=disbursement.disburse_id, item_name = item.item_name, initiating_user=indiv_request.admin_name, 
                                   nature_of_event="Disburse", affected_user=indiv_request.user_name, change_occurred="Disbursed " + str(indiv_request.total_quantity))
                messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
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
    starting_quantity=item.quantity
    if request.method == "POST":
        form = ItemEditForm(request.POST or None, instance=item)
        if form.is_valid():
            name = form['item_name'].value()
            quantity = form['quantity'].value()
            location = form['location'].value()
            model_num = form['model_number'].value()
            desc = form['description'].value()
            item.item_name = name
            item.save()
            messages.success(request, ('Successfully Saved Item Changes.'))
            if int(quantity)!=starting_quantity:    
                Log.objects.create(reference_id = str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Override', 
                                         affected_user=None, change_occurred="Change quantity from " + str(starting_quantity) + ' to ' + str(quantity))
            else:
                Log.objects.create(reference_id = str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user=None, change_occurred="Edited " + str(name))
            return redirect(reverse('custom_admin:index'))
            #form.save()
            # return redirect('/item/' + pk)
    else:
        form = ItemEditForm(instance=item, initial = {'item_field': item.item_name})
    return render(request, 'inventory/item_edit.html', {'form': form})

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
            Log.objects.create(reference_id = str(indiv_request.request_id), item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
            messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            return redirect(reverse('custom_admin:index'))  
    else:
        form = AddCommentRequestForm() # blank request form with no data yet
    return render(request, 'custom_admin/request_deny_comment_inner.html', {'form': form, 'pk':pk})

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
                Log.objects.create(item_name=item.item_name, initiating_user=request.user, nature_of_event='Disburse', 
                                         affected_user=post.user_name, change_occurred="Disbursed " + str(quant_change))
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
            Log.objects.create(reference_id = str(item.item_id), item_name = item.item_name, initiating_user=request.user, nature_of_event="Disburse", 
                       affected_user=indiv_request.user_id, change_occurred="Disbursed " + str(indiv_request.request_quantity))
            messages.add_message(request, messages.SUCCESS, 
                                 ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
        else:
            messages.add_message(request, messages.ERROR, 
                                 ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
         
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
        Log.objects.create(reference_id=str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Disburse', 
                                         affected_user=indiv_request.user_id, change_occurred="Approved request for " + str(indiv_request.request_quantity))
        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    else:
        messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
        return redirect(reverse('custom_admin:index'))
 
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def edit_item(request, pk):
    item = Item.objects.get(item_id=pk)
    custom_fields = Custom_Field.objects.all()
    custom_vals = Custom_Field_Value.objects.filter(item = item)
    original_quantity = item.quantity
    if request.method == "POST":
        form = ItemEditForm(custom_fields, custom_vals, request.POST or None, instance=item)
        if form.is_valid():
            if int(form['quantity'].value())!=original_quantity:    
                Log.objects.create(reference_id = str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Override', 
                                         affected_user=None, change_occurred="Change quantity from " + str(original_quantity) + ' to ' + str(form['quantity'].value()))
            else:
                Log.objects.create(reference_id = str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user=None, change_occurred="Edited " + str(form['item_name'].value()))
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
        form = ItemEditForm(custom_fields, custom_vals, instance=item)
    return render(request, 'inventory/item_edit.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(admin_check, login_url='/login/')
def edit_permission(request, pk):
    user = User.objects.get(username = pk)
    if request.method == "POST":
        form = UserPermissionEditForm(request.POST or None, instance=user)
        if form.is_valid():
            form.save()
            Log.objects.create(reference_id = None, item_name=None, initiating_user=request.user, nature_of_event='Edit', 
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
        item_tags = Tag.objects.filter(item_name = item)
        form = AddTagForm(tags, item_tags, request.POST or None)
        if form.is_valid():
            pickedTags = form.cleaned_data.get('tag_field')
            createdTags = form['create_new_tags'].value()
            item = Item.objects.get(item_id=pk)
            if pickedTags:
                for oneTag in pickedTags:
                    if not Tag.objects.filter(item_name=item, tag=oneTag).exists():
                        t = Tag(item_name=item, tag=oneTag) 
                        t.save(force_insert=True)
            if createdTags is not "":
                tag_list = [x.strip() for x in createdTags.split(',')]
                for oneTag in tag_list:
                    if not Tag.objects.filter(item_name=item, tag=oneTag).exists():
                        t = Tag(item_name=item, tag=oneTag)
                        t.save(force_insert=True)
            for ittag in item_tags:
                ittag.tag = form[ittag.tag].value()
                ittag.save()
            Log.objects.create(reference_id=None, item_name = item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                               affected_user=None, change_occurred="Added tags to " + str(item.item_name))
            return redirect('/item/' + pk)
    else:
        item = Item.objects.get(item_id = pk)
        tags = Tag.objects.all()
        item_tags = Tag.objects.filter(item_name = item)
        form = AddTagForm(tags, item_tags)
    return render(request, 'inventory/add_tags.html', {'form': form})

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
                Log.objects.create(reference_id=None, item_name=item.item_name, initiating_user=request.user, nature_of_event="Acquire", 
                                   affected_user=None, change_occurred="Acquired " + str(amount))
                item.save()
                messages.success(request, ('Successfully logged ' + str(item.item_name) + ' (added ' + str(amount) +')'))
            elif change_type == "Broken":
                if item.quantity >= amount:
                    item.quantity = F('quantity')-amount
                    item.save()
                    Log.objects.create(reference_id=None, item_name=item.item_name, initiating_user=request.user, nature_of_event="Broken", 
                                       affected_user=None, change_occurred="Broke " + str(amount))
                    messages.success(request, ('Successfully logged ' + item.item_name + ' (removed ' + str(amount) +')'))
                else:
                    messages.error(request, ("You can't break more of " + item.item_name + " than you have."))
                    return redirect(reverse('custom_admin:index'))
            elif change_type == "Lost":
                if item.quantity >= amount:
                    item.quantity = F('quantity')-amount
                    item.save()
                    Log.objects.create(reference_id=None, item_name=item.item_name, initiating_user=request.user, nature_of_event="Lost", 
                                       affected_user=None, change_occurred="Lost " + str(amount))
                    messages.success(request, ('Successfully logged ' + item.item_name + ' (removed ' + str(amount) +')'))
                else:
                    messages.error(request, ("You can't lose more of " + item.item_name + " than you have."))
                    return redirect(reverse('custom_admin:index'))
            form.save()
            return redirect('/customadmin')
    return render(request, 'inventory/log_item.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def edit_tag(request, pk):
    tag = Tag.objects.get(id=pk)
    if request.method == "POST":
        form = EditTagForm(request.POST or None, instance=tag)
        if form.is_valid():
            Log.objects.create(reference_id=None, item_name=tag.item_name, initiating_user=request.user, nature_of_event='Edit', 
                               affected_user=None, change_occurred="Edited tag on item " + str(tag.item_name))
            form.save()
            return redirect('/item/' + tag.item_name.item_id)
    else:
        form = EditTagForm(instance=tag)
    return render(request, 'inventory/tag_edit.html', {'form': form})

@login_required(login_url='/login/')
@user_passes_test(admin_check, login_url='/login/')
def delete_item(request, pk):
    item = Item.objects.get(item_id=pk)
    item.delete()
    Log.objects.create(reference_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user=None, change_occurred="Deleted item " + str(item.item_name))
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def delete_tag(request, pk):
    tag = Tag.objects.get(id=pk)
    tag.delete()
    Log.objects.create(item_name = tag.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user=None, change_occurred="Deleted tag " + str(tag.tag))
    return redirect('/item/' + tag.item_name.item_id)
 
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
            Log.objects.create(reference_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Create", 
                       affected_user=None, change_occurred="Created item " + str(item.item_name))
            if pickedTags:
                for oneTag in pickedTags:
                    t = Tag(item_name=item, tag=oneTag)
                    t.save(force_insert=True)
            if createdTags is not "":
                tag_list = [x.strip() for x in createdTags.split(',')]
                for oneTag in tag_list:
                    t = Tag(item_name=item, tag=oneTag)
                    t.save()
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
    Log.objects.create(reference_id = str(indiv_request.request_id), item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
    messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
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
        Log.objects.create(reference_id = str(indiv_request.request_id), item_name=indiv_request.item_name, initiating_user=request.user, nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
        indiv_request.save()
    messages.success(request, ('Denied all disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    return redirect(reverse('custom_admin:index'))
 
 
 
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
        Log.objects.create(reference_id = str(disbursement.disburse_id), item_name=disbursement.item_name, initiating_user=disbursement.admin_name, nature_of_event='Disburse', 
                                         affected_user=disbursement.user_name, change_occurred="Disbursed " + str(disbursement.total_quantity))
        messages.success(self.request, 
                                 ('Successfully disbursed ' + form['total_quantity'].value() + " " + name_requested + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
        return super(DisburseFormView, self).form_valid(form)

def search_form(request):
    if request.method == "POST":
        tags = Tag.objects.all()
        form = SearchForm(tags, request.POST)
        if form.is_valid():
            picked = form.cleaned_data.get('tags1')
            excluded = form.cleaned_data.get('tags2')
            keyword = form.cleaned_data.get('keyword')
            modelnum = form.cleaned_data.get('model_number')
            itemname = form.cleaned_data.get('item_name')
            
            keyword_list = []
            for item in Item.objects.all():
                if ((keyword is "") or ((keyword in item.item_name) or ((item.description is not None) and (keyword in item.description)) \
                    or ((item.model_number is not None) and (keyword in item.model_number)) or ((item.location is not None) and (keyword in item.location)))) \
                    and ((modelnum is "") or ((item.model_number is not None) and (modelnum in item.model_number))) \
                    and ((itemname is "") or (itemname in item.item_name)) \
                    and ((itemname is not "") or (modelnum is not "") or (keyword is not "")): 
                    keyword_list.append(item)
            
            excluded_list = []
            if excluded:
                for excludedTag in excluded:
                    tagQSEx = Tag.objects.filter(tag = excludedTag)
                    for oneTag in tagQSEx:
                        excluded_list.append(Item.objects.get(item_name = oneTag.item_name))
             # have list of all excluded items
            included_list = []
            if picked:
                for pickedTag in picked:
                    tagQSIn = Tag.objects.filter(tag = pickedTag)
                    for oneTag in tagQSIn:
                        included_list.append(Item.objects.get(item_name = oneTag.item_name))
            # have list of all included items
            
            final_list = []
            item_list = Item.objects.all()
            if not picked:
                if excluded:
                    final_list = [x for x in item_list if x not in excluded_list]
            else:
                final_list = [x for x in included_list if x not in excluded_list]
            
            # for a more constrained search
            if not final_list:
                search_list = keyword_list
            elif not keyword_list:
                search_list = final_list
            else:
                search_list = [x for x in final_list if x in keyword_list]
            # for a less constrained search
            # search_list = final_list + keyword_list
            cursor = connection.cursor()
            cursor.execute('select inventory_item.item_name, array_agg(inventory_request.request_id order by inventory_request.status desc) from inventory_request join inventory_item on inventory_item.item_id = inventory_request.item_name_id group by inventory_item.item_name')
            raw_request_list = cursor.fetchall()
            for raw_request in raw_request_list:
                raw_request_ids = raw_request[1] # all the ids in this item
                counter = 0
                for request_ID in raw_request_ids:
                    raw_request[1][counter] = Request.objects.get(request_id=request_ID)
                    counter += 1
            return render(request,'custom_admin/search_result.html', {'item_list': item_list,'request_list': raw_request_list,'search_list': set(search_list)})
    else:
        tags = Tag.objects.all()
        form = SearchForm(tags)
    return render(request, 'custom_admin/search.html', {'form': form})    
################################################################