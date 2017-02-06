from django.db.models import F
from django.http import HttpResponseRedirect
from django.db import connection, transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from .forms import EditTagForm, DisburseForm, ItemEditForm, CreateItemForm, RegistrationForm, AddCommentRequestForm, LogForm
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy 
from django.views.generic.edit import FormView
from inventory.models import Instance, Request, Item, Disbursement, Tag
from django.contrib import messages
from django.template.defaulttags import comment
 
################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class AdminIndexView(LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/index.html'
    context_object_name = 'instance_list'
    def get_context_data(self, **kwargs):
        context = super(AdminIndexView, self).get_context_data(**kwargs)
        cursor = connection.cursor()
#         cursor.execute('select item_name, array_agg(request_id order by status desc) from inventory_request inner join item_name on inventory_request.item_name = inventory_item.item_name group by item_name')
        cursor.execute('select item_name, array_agg(request_id order by status desc) from inventory_request group by item_name')
        raw_request_list = cursor.fetchall()
        for raw_request in raw_request_list:
            raw_request_ids = raw_request[1] # all the ids in this item
            counter = 0
            for request_ID in raw_request_ids:
                raw_request[1][counter] = Request.objects.get(request_id=request_ID)
                counter += 1
         
        context['request_list'] = raw_request_list
        context['pending_requests'] = Request.objects.filter(status="Pending")
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(admin_name=self.request.user.username)
        # And so on for more models
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
 
class DetailView(LoginRequiredMixin, generic.DetailView): ## DetailView to display detail for the object
    login_url = "/login/"
    model = Instance
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html
 
class DisburseView(LoginRequiredMixin, generic.ListView): ## DetailView to display detail for the object
    login_url = "/login/"
    model = Instance
    template_name = 'custom_admin/single_disburse.html' # w/o this line, default would've been inventory/<model_name>.html
 
#####################################################################
@login_required(login_url='/login/')
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
            return HttpResponseRedirect('/customadmin')
    form = RegistrationForm()
    return render(request, 'custom_admin/register_user.html', {'form': form})
 
@login_required(login_url='/login/')
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
                messages.success(request, ('Successfully disbursed ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
            else:
                messages.error(request, ('Not enough stock available for ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
            return redirect(reverse('custom_admin:index'))  
    else:
        form = AddCommentRequestForm() # blank request form with no data yet
    return render(request, 'custom_admin/request_accept_comment_inner.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
def add_comment_to_request_deny(request, pk):
    if request.method == "POST":
        form = AddCommentRequestForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            comment = form['comment'].value()
            indiv_request = Request.objects.get(request_id=pk)
            indiv_request.status = "Denied"
            indiv_request.comment = comment
            indiv_request.save()
            messages.success(request, ('Denied disbursement ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
            return redirect(reverse('custom_admin:index'))  
    else:
        form = AddCommentRequestForm() # blank request form with no data yet
    return render(request, 'custom_admin/request_deny_comment_inner.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
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
                item.quantity = F('quantity')-int(form['total_quantity'].value())
                item.save()
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
def approve_all_requests(request):
    pending_requests = Request.objects.filter(status="Pending")
    for indiv_request in pending_requests:
        item = get_object_or_404(Item,item_name=indiv_request.item_name)
        if item.quantity >= indiv_request.request_quantity:
            # decrement quantity in item
            item.quantity = F('quantity')-indiv_request.request_quantity
            item.save()
             
            # change status of request to approved
            indiv_request.status = "Approved"
            indiv_request.save()
             
            # add new disbursement item to table
            # TODO: add comments!!
            disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_name = indiv_request.item_name), 
                                        total_quantity=indiv_request.request_quantity, time_disbursed=timezone.localtime(timezone.now()))
            disbursement.save()
             
            messages.add_message(request, messages.SUCCESS, 
                                 ('Successfully disbursed ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
        else:
            messages.add_message(request, messages.ERROR, 
                                 ('Not enough stock available for ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
         
    return redirect(reverse('custom_admin:index'))
 
@login_required(login_url='/login/')
def approve_request(request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    item = Item.objects.get(item_name=indiv_request.item_name)
    if item.quantity >= indiv_request.request_quantity:
        # decrement quantity in item
        item.quantity = F('quantity')-indiv_request.request_quantity
        item.save()
         
        # change status of request to approved
        indiv_request.status = "Approved"
        indiv_request.save()
         
        # add new disbursement item to table
        # TODO: add comments!!
        disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_name = indiv_request.item_name), 
                                    total_quantity=indiv_request.request_quantity, time_disbursed=timezone.localtime(timezone.now()))
        disbursement.save()
        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
    else:
        messages.error(request, ('Not enough stock available for ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
        return redirect(reverse('custom_admin:index'))
 
    return redirect(reverse('custom_admin:index'))
#         ("Successfully disbursed " + indiv_request.request_quantity + " " + indiv_request.item_name + " to " + indiv_request.user_id))
         
#     return redirect('/')
@login_required(login_url='/login/')
def edit_item(request, pk):
    item = Item.objects.get(item_id=pk)
    tags = Tag.objects.filter(item_name=item)
    if request.method == "POST":
        form = ItemEditForm(request.POST or None, instance=item)
        if form.is_valid():
            post = form.save(commit=False)
            pickedTags = form.cleaned_data.get('tag_field')
            createdTags = form['create_new_tags'].value()
            post.save()
            item = Item.objects.get(item_name = form['item_name'].value())
            for oneTag in pickedTags:
                t = Tag(item_name=item, tag=oneTag)
                t.save(force_insert=True)
            if createdTags is not "":
                tag_list = [x.strip() for x in createdTags.split(',')]
                for oneTag in tag_list:
                    t = Tag(item_name=item, tag=oneTag)
                    t.save(force_insert=True)
            return redirect('/customadmin')
            form.save()
            return redirect('/customadmin')
    else:
        form = ItemEditForm(instance=item, initial = {'item_field': item.item_name,'tag_field':tags})
    return render(request, 'inventory/item_edit.html', {'form': form})

@login_required(login_url='/login/')
def log_item(request):
    form = LogForm(request.POST or None)
    if request.method=="POST":
        form = LogForm(request.POST)
        if form.is_valid():
            item = Item.objects.get(item_id=form['item_name'].value())
            change_type = form['item_change_status'].value()
            print(change_type)
            amount = int(form['item_amount'].value())
            if change_type == '2':  # this correlates to the item_change_option numbers for the tuples
                item.quantity = F('quantity')+amount
                item.save()
            else:
                item.quantity = F('quantity')-amount
                item.save()
            form.save()
            return redirect('/customadmin')
    return render(request, 'inventory/log_item.html', {'form': form})
def edit_tag(request, pk):
    tag = Tag.objects.get(id=pk)
    if request.method == "POST":
        form = EditTagForm(request.POST or None, instance=tag)
        if form.is_valid():
            form.save()
            return redirect('/customadmin')
    else:
        form = EditTagForm(instance=tag)
    return render(request, 'inventory/tag_edit.html', {'form': form})

@login_required(login_url='/login/')
def delete_item(request, pk):
    item = Item.objects.get(item_id=pk)
    item.delete()
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
def delete_tag(request, pk):
    tag = Tag.objects.get(id=pk)
    tag.delete()
    return redirect('/customadmin')
 
@login_required(login_url='/login/')
def create_new_item(request):
    if request.method== 'POST':
        form = CreateItemForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            pickedTags = form.cleaned_data.get('tag_field')
            createdTags = form['new_tags'].value()
            post.save()
            item = Item.objects.get(item_name = form['item_name'].value())
            for oneTag in pickedTags:
                t = Tag(item_name=item, tag=oneTag)
                t.save(force_insert=True)
            if createdTags is not "":
                tag_list = [x.strip() for x in createdTags.split(',')]
                for oneTag in tag_list:
                    t = Tag(item_name=item, tag=oneTag)
                    t.save(force_insert=True)
            return redirect('/customadmin')
    return render(request, 'inventory/item_create.html', {'form':CreateItemForm(),})
 
@login_required(login_url='/login/')
def deny_request(request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    indiv_request.status = "Denied"
    indiv_request.save()
    messages.success(request, ('Denied disbursement ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
    return redirect(reverse('custom_admin:index'))
 
@login_required(login_url='/login/')
def deny_all_request(request):
    pending_requests = Request.objects.filter(status="Pending")
    for indiv_request in pending_requests:
        indiv_request.status = "Denied"
        indiv_request.save()
    messages.success(request, ('Denied all disbursement ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
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
        messages.success(self.request, 
                                 ('Successfully disbursed ' + form['total_quantity'].value() + " " + name_requested + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
        return super(DisburseFormView, self).form_valid(form)
    
################################################################