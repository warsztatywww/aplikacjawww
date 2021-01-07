import datetime

from django.contrib.auth.models import User, Permission
from django.contrib.messages.api import get_messages
from django.test.testcases import TestCase
from django.urls import reverse

from wwwapp.models import Camp, WorkshopType, WorkshopCategory, Workshop, WorkshopParticipant, Article, \
    WorkshopUserProfile


class TestArticleViews(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.normal_user = User.objects.create_user(
            username='user', email='user@example.com', password='user123')
        self.editor_user = User.objects.create_user(
            username='editor', email='editor@example.com', password='user123')
        self.supereditor_user = User.objects.create_user(
            username='supereditor', email='supereditor@example.com', password='user123')
        self.supermegaeditor_user = User.objects.create_user(
            username='supermegaeditor', email='supermegaeditor@example.com', password='user123')

        self.editor_user.user_permissions.add(Permission.objects.get(codename='change_article'))
        self.supereditor_user.user_permissions.add(Permission.objects.get(codename='change_article'))
        self.supereditor_user.user_permissions.add(Permission.objects.get(codename='add_article'))
        self.supermegaeditor_user.user_permissions.add(Permission.objects.get(codename='change_article'))
        self.supermegaeditor_user.user_permissions.add(Permission.objects.get(codename='add_article'))
        self.supermegaeditor_user.user_permissions.add(Permission.objects.get(codename='can_put_on_menubar'))

        self.article = Article.objects.create(name='test_article', title='Testowy artykuł', content='<p>Test</p>',
                                              modified_by=self.admin_user, on_menubar=False)
        self.article2 = Article.objects.create(name='test_article_on_menubar', title='Drugi artykuł', content='<p>Test</p>',
                                               modified_by=self.admin_user, on_menubar=True)

    def test_index_works(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.editor_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.supereditor_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.supermegaeditor_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

    def test_article_view_works(self):
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.editor_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.supereditor_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.supermegaeditor_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

    def test_create_article(self):
        self.client.force_login(self.supermegaeditor_user)

        response = self.client.get(reverse('article_add'))
        self.assertContains(response, 'Nazwa')
        self.assertContains(response, 'Tytuł')
        self.assertContains(response, 'Umieść w menu')
        self.assertContains(response, '<input type="checkbox" name="on_menubar" class="checkboxinput custom-control-input" id="id_on_menubar"')
        self.assertContains(response, 'Treść')

        response = self.client.post(reverse('article_add'), {
            'name': 'created_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertRedirects(response, reverse('article', args=['created_article']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        article = Article.objects.get(name='created_article')
        self.assertEqual(article.title, 'Utworzony artykuł')
        self.assertHTMLEqual(article.content, '<p>Treść</p>')
        self.assertEqual(article.on_menubar, True)
        self.assertEqual(article.modified_by, self.supermegaeditor_user)

        article_history = article.content_history()
        self.assertEqual(len(article_history), 1)
        self.assertHTMLEqual(article_history[0].content, '<p>Treść</p>')
        self.assertEqual(article_history[0].modified_by, self.supermegaeditor_user)
        self.assertEqual(article_history[0].version, 1)

    def test_create_article_no_menubar(self):
        # This user doesn't have the can_put_on_menubar permission
        self.client.force_login(self.supereditor_user)

        response = self.client.get(reverse('article_add'))
        self.assertContains(response, 'Nazwa')
        self.assertContains(response, 'Tytuł')
        self.assertContains(response, 'Umieść w menu')
        self.assertContains(response, '<input type="checkbox" name="on_menubar" class="checkboxinput custom-control-input" disabled id="id_on_menubar"')  # Exists, but is disabled
        self.assertContains(response, 'Treść')

        response = self.client.post(reverse('article_add'), {
            'name': 'created_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertRedirects(response, reverse('article', args=['created_article']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        article = Article.objects.get(name='created_article')
        self.assertEqual(article.title, 'Utworzony artykuł')
        self.assertHTMLEqual(article.content, '<p>Treść</p>')
        self.assertEqual(article.on_menubar, False)  # This should not be set!
        self.assertEqual(article.modified_by, self.supereditor_user)

        article_history = article.content_history()
        self.assertEqual(len(article_history), 1)
        self.assertHTMLEqual(article_history[0].content, '<p>Treść</p>')
        self.assertEqual(article_history[0].modified_by, self.supereditor_user)
        self.assertEqual(article_history[0].version, 1)

    def test_create_article_without_permissions(self):
        # This user doesn't have the add_article permission
        self.client.force_login(self.editor_user)

        response = self.client.get(reverse('article_add'))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse('article_add'), {
            'name': 'created_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Article.objects.filter(name='created_article').exists())

    def test_create_article_unauthenticated(self):
        response = self.client.get(reverse('article_add'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('article_add'))

        response = self.client.post(reverse('article_add'), {
            'name': 'created_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('article_add'))
        self.assertFalse(Article.objects.filter(name='created_article').exists())

    def test_edit_article(self):
        self.client.force_login(self.supermegaeditor_user)

        response = self.client.get(reverse('article_edit', args=['test_article']))
        self.assertContains(response, 'Nazwa')
        self.assertContains(response, 'Tytuł')
        self.assertContains(response, 'Umieść w menu')
        self.assertContains(response, '<input type="checkbox" name="on_menubar" class="checkboxinput custom-control-input" id="id_on_menubar"')
        self.assertContains(response, 'Treść')

        response = self.client.post(reverse('article_edit', args=['test_article']), {
            'name': 'edited_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertRedirects(response, reverse('article', args=['edited_article']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        article = Article.objects.get(name='edited_article')
        self.assertEqual(article.title, 'Utworzony artykuł')
        self.assertHTMLEqual(article.content, '<p>Treść</p>')
        self.assertEqual(article.on_menubar, True)
        self.assertEqual(article.modified_by, self.supermegaeditor_user)

        article_history = article.content_history()
        self.assertEqual(len(article_history), 2)
        self.assertHTMLEqual(article_history[0].content, '<p>Treść</p>')
        self.assertEqual(article_history[0].modified_by, self.supermegaeditor_user)
        self.assertEqual(article_history[0].version, 2)
        self.assertHTMLEqual(article_history[1].content, '<p>Test</p>')
        self.assertEqual(article_history[1].modified_by, self.admin_user)
        self.assertEqual(article_history[1].version, 1)

    def test_edit_article_no_menubar(self):
        # This user doesn't have the can_put_on_menubar permission
        self.client.force_login(self.editor_user)

        response = self.client.get(reverse('article_edit', args=['test_article']))
        self.assertContains(response, 'Nazwa')
        self.assertContains(response, 'Tytuł')
        self.assertContains(response, 'Umieść w menu')
        self.assertContains(response, '<input type="checkbox" name="on_menubar" class="checkboxinput custom-control-input" disabled id="id_on_menubar"')  # Exists, but is disabled
        self.assertContains(response, 'Treść')

        response = self.client.post(reverse('article_edit', args=['test_article']), {
            'name': 'edited_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertRedirects(response, reverse('article', args=['edited_article']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        article = Article.objects.get(name='edited_article')
        self.assertEqual(article.title, 'Utworzony artykuł')
        self.assertHTMLEqual(article.content, '<p>Treść</p>')
        self.assertEqual(article.on_menubar, False)  # This should not be set!
        self.assertEqual(article.modified_by, self.editor_user)

        article_history = article.content_history()
        self.assertEqual(len(article_history), 2)
        self.assertHTMLEqual(article_history[0].content, '<p>Treść</p>')
        self.assertEqual(article_history[0].modified_by, self.editor_user)
        self.assertEqual(article_history[0].version, 2)
        self.assertHTMLEqual(article_history[1].content, '<p>Test</p>')
        self.assertEqual(article_history[1].modified_by, self.admin_user)
        self.assertEqual(article_history[1].version, 1)

    def test_edit_article_without_permissions(self):
        # This user doesn't have the change_article permission
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('article_edit', args=['test_article']))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse('article_edit', args=['test_article']), {
            'name': 'edited_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Article.objects.filter(name='edited_article').exists())
        self.assertEqual(len(Article.objects.get(name='test_article').content_history()), 1)

    def test_edit_article_unauthenticated(self):
        response = self.client.get(reverse('article_edit', args=['test_article']))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('article_edit', args=['test_article']))

        response = self.client.post(reverse('article_edit', args=['test_article']), {
            'name': 'edited_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('article_edit', args=['test_article']))
        self.assertFalse(Article.objects.filter(name='edited_article').exists())
        self.assertEqual(len(Article.objects.get(name='test_article').content_history()), 1)

    def test_edit_special_article(self):
        # Trying to edit name, title or menubar for index page should fail
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('article_edit', args=['index']))
        self.assertNotContains(response, 'Nazwa')
        self.assertNotContains(response, 'Tytuł')
        self.assertNotContains(response, 'Umieść w menu')
        self.assertContains(response, 'Treść')

        response = self.client.post(reverse('article_edit', args=['index']), {
            'name': 'edited_article',
            'title': 'Utworzony artykuł',
            'on_menubar': 'on',
            'content': '<p>Treść</p>',
        })
        self.assertRedirects(response, reverse('article', args=['index']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        self.assertFalse(Article.objects.filter(name='edited_article').exists())
        article = Article.objects.get(name='index')
        self.assertEqual(article.title, None)  # This should not be set!
        self.assertHTMLEqual(article.content, '<p>Treść</p>')
        self.assertEqual(article.on_menubar, False)  # This should not be set!
        self.assertEqual(article.modified_by, self.admin_user)

        article_history = article.content_history()
        self.assertEqual(len(article_history), 2)
        self.assertHTMLEqual(article_history[0].content, '<p>Treść</p>')
        self.assertEqual(article_history[0].modified_by, self.admin_user)
        self.assertEqual(article_history[0].version, 2)
        self.assertHTMLEqual(article_history[1].content, '')
        self.assertEqual(article_history[1].modified_by, None)
        self.assertEqual(article_history[1].version, 1)

    def test_article_on_menubar(self):
        response = self.client.get(reverse('index'))
        self.assertNotContains(response, 'Testowy artykuł')
        self.assertContains(response, 'Drugi artykuł')
