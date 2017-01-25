import random

from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import RequestForm
from .models import Question, Choice, Instance, Request, Item


################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class IndexView(LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'inventory/index.html'
    context_object_name = 'instance_list'
    
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['request_list'] = Request.objects.all()
        context['item_list'] = Item.objects.all()
        # And so on for more models
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
    
class DetailView(LoginRequiredMixin, generic.DetailView): ## DetailView to display detail for the object
    login_url = "/login/"
    model = Instance
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html

## FROM THE DJANGO TUTORIAL ##
class ResultsView(LoginRequiredMixin, generic.DetailView):
    login_url = "/login/"
    model = Question
    template_name = 'inventory/results.html' # w/o this line, default would've been inventory/<model_name>.html
#####################################################################

# create table request_table (
# request_id serial PRIMARY KEY, 
# user_id varchar NOT NULL, 
# item_name varchar NOT NULL, 
# request_quantity smallint NOT NULL, 
# status varchar NOT NULL, 
# comment varchar, 
# time_requested timestamp );
@login_required(login_url='/login/')
def post_new_request(request):
    if request.method == "POST":
        form = RequestForm(request.POST) # create request-form with the data from the request 
        if form.is_valid():
            post = form.save(commit=False)
            post.status = "Pending"
            post.time_requested = timezone.localtime(timezone.now())
            post.save()
            return redirect('/')
#             return redirect('detail', pk=post.pk)
    else:
        form = RequestForm() # blank request form with no data yet
    return render(request, 'inventory/request_edit.html', {'form': form})


## FROM THE DJANGO TUTORIAL ##
@login_required(login_url='/login/')
def vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    try:
        selected_choice = question.choice_set.get(pk=request.POST['choice'])
    except (KeyError, Choice.DoesNotExist):
        # Redisplay the question voting form.
        return render(request, 'inventory/detail.html', {
            'question': question,
            'error_message': "You didn't select a choice.",
        })
    else:
#         selected_choice.update(votes=F('votes') + 1)

        selected_choice.votes = F('votes') + 1
        selected_choice.save()
        # Always return an HttpResponseRedirect after successfully dealing
        # with POST data. This prevents data from being posted twice if a
        # user hits the Back button.
        return HttpResponseRedirect(reverse('inventory:results', args=(question.id,)))
