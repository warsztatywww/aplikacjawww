from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from wwwforms.forms import FormForm
from wwwforms.models import Form


@login_required()
def form_view(request, name):
    form = get_object_or_404(Form.objects.prefetch_related('questions', 'arrival_date', 'departure_date'), name=name)

    if request.method == 'POST':
        formform = FormForm(form, request.user, request.POST)
        if formform.is_valid():
            formform.save()
            messages.info(request, 'Zapisano.')
            return redirect(reverse('form', args=[form.name]))
    else:
        formform = FormForm(form, request.user)

    context = {}
    context['title'] = form.title
    context['form'] = formform
    return render(request, 'form.html', context)


@login_required()
@permission_required('wwwforms.see_form_results', raise_exception=True)
def form_results_view(request, name):
    form = get_object_or_404(Form.objects.prefetch_related('questions', 'questions__answers', 'questions__answers__user'), name=name)

    all_questions = form.questions.all()
    all_answers = [answer for question in all_questions for answer in question.answers.all()]
    # Group the answers by users
    user_answers = {}
    for answer in all_answers:
        if answer.user not in user_answers:
            user_answers[answer.user] = []
        user_answers[answer.user].append(answer)
    # Make sure the user_answers array is arranged such that the answer at index i matches the question i
    for user in user_answers.keys():
        user_answers[user] = [next(filter(lambda a: a.question == question, user_answers[user]), None) for question in all_questions]

    context = {}
    context['title'] = form.title
    context['questions'] = all_questions
    context['answers'] = user_answers
    return render(request, 'formresults.html', context)
