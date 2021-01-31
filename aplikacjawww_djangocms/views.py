from django.shortcuts import redirect


def legacy_article_url_redirect(request, name):
    return redirect('/{}'.format(name))
