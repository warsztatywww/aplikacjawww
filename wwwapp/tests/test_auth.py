import mock
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SOCIAL_AUTH_FACEBOOK_KEY='1',
                   SOCIAL_AUTH_FACEBOOK_SECRET='2',
                   SOCIAL_AUTH_GOOGLE_OAUTH2_KEY='3',
                   SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET='4',
                   AUTHENTICATION_BACKENDS=('django.contrib.auth.backends.ModelBackend',
                                            'social_core.backends.google.GoogleOAuth2',
                                            'social_core.backends.facebook.FacebookOAuth2',),)
class AuthViews(TestCase):
    def setUp(self):
        self.supported_backends = ['facebook', 'google-oauth2']

    def test_available_backends(self):
        for backend in self.supported_backends:
            response = self.client.get(reverse('social:begin', kwargs={'backend': backend}))
            self.assertEqual(response.status_code, 302, msg=backend)

        not_supported_backends = ['linkedin', 'your_mom', 'furaffinity']
        for backend in not_supported_backends:
            url = reverse('social:begin', kwargs={'backend': backend})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404, msg=backend)

    def login_page_anonymous(self):
        response = self.client.get(reverse('login'))
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wybierz metodę logowania:")
        self.assertTrue("alt=\"Continue with Facebook\"" in content)
        self.assertTrue("alt=\"Sign in with Google\"" in content)
        for backend in self.supported_backends:
            self.assertTrue("href=\"{}\"".format(reverse('social:begin', kwargs={'backend': backend})) in content, msg=backend)

    def login_page_user(self, first_name, last_name):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'Zalogowany jako {} {}'.format(first_name, last_name),
                            status_code=200)

    def test_login_page_anonymous(self):
        self.login_page_anonymous()

    def facebook_login(self, uid, first_name, last_name, email, test_login=True, test_merge=False):
        fake_responses = [mock.Mock(), mock.Mock()]
        fake_responses[0].json.return_value = {'access_token': '123'}
        fake_responses[1].json.return_value = {'id': uid, 'first_name': first_name, 'last_name': last_name, 'email': email}
        with mock.patch('social_core.backends.base.BaseAuth.request', side_effect=fake_responses):
            response = self.client.get(reverse('login'))
            self.assertEqual(response.status_code, 200)
            response = self.client.get(reverse('social:begin', kwargs={'backend': 'facebook'}))
            self.assertEqual(response.status_code, 302)

            url = reverse('social:complete', kwargs={'backend': 'facebook'})
            url += '?code=2&state=XXX'

            session = self.client.session
            session['facebook_state'] = 'XXX'
            session.save()

            with mock.patch('django.contrib.sessions.backends.base.SessionBase'
                            '.set_expiry', side_effect=[OverflowError, None]):
                response = self.client.get(url)
                if test_merge:
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, 'loginMerge.html')
                else:
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response.url, reverse('login'))

                    if test_login:
                        self.login_page_user(first_name, last_name)
                return response

    def google_login(self, uid, first_name, last_name, email, test_login=True, test_merge=False):
        fake_responses = [mock.Mock(), mock.Mock()]
        fake_responses[0].json.return_value = {'access_token': '123'}
        fake_responses[1].json.return_value = {'sub': uid, 'name': first_name + " " + last_name, 'email': email}
        with mock.patch('social_core.backends.base.BaseAuth.request', side_effect=fake_responses):
            response = self.client.get(reverse('login'))
            self.assertEqual(response.status_code, 200)
            response = self.client.get(reverse('social:begin', kwargs={'backend': 'google-oauth2'}))
            self.assertEqual(response.status_code, 302)

            url = reverse('social:complete', kwargs={'backend': 'google-oauth2'})
            url += '?code=2&state=XXX'

            session = self.client.session
            session['google-oauth2_state'] = 'XXX'
            session.save()

            with mock.patch('django.contrib.sessions.backends.base.SessionBase'
                            '.set_expiry', side_effect=[OverflowError, None]):
                response = self.client.get(url)
                if test_merge:
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, 'loginMerge.html')
                else:
                    if test_login:
                        self.assertEqual(response.status_code, 302)
                        self.assertEqual(response.url, reverse('login'))
                        self.login_page_user(first_name, last_name)
                return response

    def logout(self):
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.login_page_anonymous()

    def register_and_login(self, method, uid, first_name, second_name, email):
        start = len(User.objects.all())
        # Registration and relogin
        for i in range(3):
            if i == 0:
                user_id = method(uid, first_name, second_name, email).wsgi_request.user.id
            else:
                self.assertEqual(method(uid, first_name, second_name, email).wsgi_request.user.id, user_id)
            self.logout()
            self.assertEqual(len(User.objects.all()), start + 1)

        # Should still work when user changes his data completely in the provider
        self.assertEqual(method(uid, first_name+'A', second_name+'A', email+'A', test_login=False).wsgi_request.user.id, user_id)
        self.logout()
        self.assertEqual(len(User.objects.all()), start + 1)

        self.assertEqual(
            method(uid, first_name, second_name, email).wsgi_request.user.id,
            user_id)
        self.logout()
        self.assertEqual(len(User.objects.all()), start + 1)

    def test_login_and_merge_triggering(self):
        # Standalone login
        uid = 0
        for i in range(4):
            self.register_and_login(self.facebook_login, uid, "facebook_name_{}".format(i), "facebook_surname_{}".format(i), "facebook_email_{}".format(i))
            uid += 1

        for i in range(4):
            self.register_and_login(self.google_login, uid, "google_name_{}".format(i), "google_surname_{}".format(i), "google_email_{}".format(i))
            uid += 1

        # Weird names
        self.register_and_login(self.facebook_login, uid, "żółć", "ńą",
                                         "random1")
        uid += 1
        self.register_and_login(self.google_login, uid, "żółty", "ńąa",
                                         "random2")
        uid += 1

        # Check when merging is triggered
        for i in range(4):
            # Exact matches
            self.google_login(uid, "facebook_name_{}".format(i), "facebook_surname_{}".format(i), "facebook_email_{}".format(i), test_merge=True)
            self.facebook_login(uid, "google_name_{}".format(i), "google_surname_{}".format(i), "google_email_{}".format(i), test_merge=True)

        # Matching emails
        self.google_login(uid, "A", "A", "facebook_email_0", test_merge=True)
        self.facebook_login(uid, "A", "A", "google_email_0", test_merge=True)

        # Matching surnames and first names
        self.google_login(uid, "facebook_name_0", "facebook_surname_0", "random3", test_merge=True)
        self.facebook_login(uid, "google_name_0", "google_surname_0", "random3", test_merge=True)

        # Matching surnames but first names differ should result in account creation
        self.register_and_login(self.google_login, uid, "A", "facebook_surname_0", "random5")
        uid += 1
        self.register_and_login(self.facebook_login, uid, "A", "google_surname_0", "random4")
        uid += 1

    def google_merge_verification(self, uid, name, surname, email):
        self.google_login(uid, name, surname, email, test_login=False)
        resp = self.client.get(reverse('finish_merge_verification'))
        self.assertEqual(resp.status_code, 302)

        fake_responses = [mock.Mock(), mock.Mock()]
        fake_responses[0].json.return_value = {'access_token': '123'}
        fake_responses[1].json.return_value = {'sub': uid,
                                               'name': name + " " + surname,
                                               'email': email}
        with mock.patch('social_core.backends.base.BaseAuth.request',
                        side_effect=fake_responses):
            url = reverse('social:complete',
                          kwargs={'backend': 'google-oauth2'})
            url += '?code=2&state=XXX'

            session = self.client.session
            session['google-oauth2_state'] = 'XXX'
            session.save()

            with mock.patch('django.contrib.sessions.backends.base.SessionBase'
                            '.set_expiry', side_effect=[OverflowError, None]):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse('login'))

    def test_account_merging(self):
        start = len(User.objects.all())

        hacker_user_id = self.google_login(0,
                                           "google_hacker_name",
                                           "google_hacker_surname",
                                           "google_hacker_email").wsgi_request.user.id
        self.logout()
        self.assertEqual(len(User.objects.all()), start + 1)

        google_user_id = self.google_login(1,
                                           "google_name",
                                           "google_surname",
                                           "google_email").wsgi_request.user.id
        self.logout()
        self.assertEqual(len(User.objects.all()), start + 2)

        # here we check for attempted fraud. We should get merge with hacker_user_id
        self.facebook_login(2, "google_name", "google_surname", "google_email", test_merge=True)
        self.google_merge_verification(0, "google_name", "google_surname", "google_email")
        self.assertEqual(self.client.get(reverse('login')).wsgi_request.user.id, hacker_user_id)

    # The following things were tested manually a LOT:
    # TODO: check redirects
    # TODO: check if account merging works
    # TODO: migrate -> create_accounts and merge some of them -> rollback migration -> migrate -> check if login still works
