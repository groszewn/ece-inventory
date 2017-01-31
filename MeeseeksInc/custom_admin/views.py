from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User

from .forms import DisburseForm
from inventory.models import Instance, Request, Item, Disbursement
from django.contrib import messages

################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class AdminIndexView(LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/index.html'
    context_object_name = 'instance_list'
    
    def get_context_data(self, **kwargs):
        context = super(AdminIndexView, self).get_context_data(**kwargs)
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
def post_new_disburse(request):
    if request.method == "POST":
        form = DisburseForm(request.POST) # create request-form with the data from the request 
        if form.is_valid():
            post = form.save(commit=False)
            post.admin_name = request.user.username
            post.item_name = form['item_field'].value()
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
        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
    else:
        messages.error(request, ('Not enough stock available for ' + indiv_request.item_name + ' (' + indiv_request.user_id +')'))
        return redirect(reverse('custom_admin:index'))

    return redirect(reverse('custom_admin:index'))
#         ("Successfully disbursed " + indiv_request.request_quantity + " " + indiv_request.item_name + " to " + indiv_request.user_id))
        

#     return redirect('/')

@login_required(login_url='/login/')
def deny_request(self, pk):
    indiv_request = Request.objects.get(request_id=pk)
    indiv_request.status = "Denied"
    indiv_request.save()
    return redirect('/')

@login_required(login_url='/login/')
def deny_all_request(self):
    pending_requests = Request.objects.filter(status="Pending")
    for indiv_request in pending_requests:
        indiv_request.status = "Denied"
        indiv_request.save()
    return redirect('/')
