from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404 
from django.shortcuts import render_to_response, redirect
from django.template import context
from django.template.context import RequestContext
from django.urls import reverse
from django.views import generic

from .models import Question, Choice


################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class IndexView(generic.ListView):  ## ListView to display a list of objects
    template_name = 'inventory/index.html'
    context_object_name = 'latest_question_list'

    def get_queryset(self):
        """Return the last five published questions."""
        return Question.objects.order_by('-pub_date')[:5]
    
class DetailView(generic.DetailView): ## DetailView to display detail for the object
    model = Question
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html


class ResultsView(generic.DetailView):
    model = Question
    template_name = 'inventory/results.html' # w/o this line, default would've been inventory/<model_name>.html
#####################################################################

# def add_question(request):
#     # A HTTP POST?
#     if request.method == 'POST':
#         question = Question()
#         return render_to_response('inventory/results.html', RequestContext(request, {'question': question}))
#     # Bad form (or form details), no form supplied...
#     # Render the form with error messages (if any).
#     return render(request, 'inventory/detail.html', {})
#     
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
