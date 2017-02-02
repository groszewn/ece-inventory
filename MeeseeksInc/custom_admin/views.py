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
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy 
from django.views.generic.edit import FormView
from .forms import DisburseForm, RegistrationForm
from inventory.models import Instance, Request, Item, Disbursement
from django.contrib import messages

################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class AdminIndexView(LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/index.html'
    context_object_name = 'instance_list'
    
    def get_context_data(self, **kwargs):
        context = super(AdminIndexView, self).get_context_data(**kwargs)
        cursor = connection.cursor()
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
def post_new_disburse(request):
    if request.method == "POST":
        form = DisburseForm(request.POST) # create request-form with the data from the request 
        if form.is_valid():
            post = form.save(commit=False)
            post.admin_name = request.user.username
            name_requested = form['item_field'].value()
            item_requested = Item.objects.get(item_name = name_requested)
            post.item_name = item_requested
            post.user_name = User.objects.get(id=form['user_field'].value()).username
            post.time_disbursed = timezone.localtime(timezone.now())
            post.save()
            return redirect('/customadmin')
    else:
        form = DisburseForm() # blank request form with no data yet
    return render(request, 'custom_admin/single_disburse.html', {'form': form})

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
            disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=indiv_request.item_name, 
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
        disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=indiv_request.item_name, 
                                    total_quantity=indiv_request.request_quantity, time_disbursed=timezone.localtime(timezone.now()))
        disbursement.save()
        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    else:
        messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
        return redirect(reverse('custom_admin:index'))

    return redirect(reverse('custom_admin:index'))
#         ("Successfully disbursed " + indiv_request.request_quantity + " " + indiv_request.item_name + " to " + indiv_request.user_id))
        

#     return redirect('/')

@login_required(login_url='/login/')
def deny_request(request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    indiv_request.status = "Denied"
    indiv_request.save()
    messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    return redirect(reverse('custom_admin:index'))

@login_required(login_url='/login/')
def deny_all_request(request):
    pending_requests = Request.objects.filter(status="Pending")
    for indiv_request in pending_requests:
        indiv_request.status = "Denied"
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
        post.item_name = form['item_field'].value()
        post.user_name = User.objects.get(id=form['user_field'].value()).username
        post.time_disbursed = timezone.localtime(timezone.now())
        post.save()
        return super(DisburseFormView, self).form_valid(form)
    
################################################################