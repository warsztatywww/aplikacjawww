from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
