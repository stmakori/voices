import base64
import json as _json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


def _make_far_future_token():
    """Build a minimal fake JWT whose exp is safely in the future (year 2286)."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b'=').decode()
    payload = base64.urlsafe_b64encode(
        _json.dumps({"exp": 9999999999, "sub": "testuser"}).encode()
    ).rstrip(b'=').decode()
    return f"{header}.{payload}.fakesig"

from Voices.models import GBVReport, UserProfile


class MyProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='profileuser',
            email='profile@example.com',
            password='StrongPassword123!'
        )
        UserProfile.objects.create(user=self.user, phone_number='+254700000000', user_type='victim')

    def test_myprofile_requires_auth(self):
        response = self.client.get(reverse('myprofile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_myprofile_renders_for_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('myprofile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Profile')
        self.assertContains(response, 'My Reports Progress')

    def test_profile_update_saves_local_user_and_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('myprofile'), {
            'update_profile': '1',
            'email': 'updated@example.com',
            'phone_number': '+254711111111',
            'user_type': 'contributor',
        })
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.profile.phone_number, '+254711111111')
        self.assertEqual(self.user.profile.user_type, 'contributor')

    def test_change_password_requires_active_cognito_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('myprofile'), {
            'change_password': '1',
            'current_password': 'StrongPassword123!',
            'new_password': 'StrongerPassword123!@#',
            'confirm_password': 'StrongerPassword123!@#',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))


class ReportOwnershipTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='usera', password='StrongPassword123!')
        self.user_b = User.objects.create_user(username='userb', password='StrongPassword123!')

        self.report_a = GBVReport.objects.create(
            report_type='physical',
            location='Nairobi',
            description='Owned by A',
            consent=True,
            submitted_by=self.user_a,
        )
        self.report_b = GBVReport.objects.create(
            report_type='physical',
            location='Nakuru',
            description='Owned by B',
            consent=True,
            submitted_by=self.user_b,
        )

    def test_myprofile_shows_only_owned_report_timeline_links(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('myprofile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('report_timeline', args=[self.report_a.id]))
        self.assertNotContains(response, reverse('report_timeline', args=[self.report_b.id]))


class RoleAccessTests(TestCase):
    def setUp(self):
        self.victim = User.objects.create_user(username='victim_user', password='StrongPassword123!')
        self.contributor = User.objects.create_user(username='contributor_user', password='StrongPassword123!')
        UserProfile.objects.create(user=self.victim, user_type='victim')
        UserProfile.objects.create(user=self.contributor, user_type='contributor')

    def test_contributor_cannot_access_report_form(self):
        self.client.force_login(self.contributor)
        session = self.client.session
        session['user_type'] = 'contributor'
        session.save()

        response = self.client.get(reverse('report_gbv'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_victim_cannot_access_contribute_page(self):
        self.client.force_login(self.victim)
        session = self.client.session
        session['user_type'] = 'victim'
        session.save()

        response = self.client.get(reverse('contribute'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_change_role_toggles_user_type(self):
        self.client.force_login(self.victim)
        response = self.client.post(reverse('change_role'), {'next': reverse('home')})
        self.assertEqual(response.status_code, 302)

        self.victim.refresh_from_db()
        self.assertEqual(self.victim.profile.user_type, 'contributor')


class CognitoErrorPathTests(TestCase):
    """Verify that local state persists and correct feedback shows when Cognito errors occur."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cognitotest',
            email='cognitotest@example.com',
            password='StrongPassword123!',
        )
        from Voices.models import UserProfile
        UserProfile.objects.create(user=self.user, user_type='victim')

    def _login_with_token(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['access_token'] = _make_far_future_token()
        session['user_type'] = 'victim'
        session.save()

    def test_profile_saves_locally_when_cognito_sync_fails(self):
        """Profile must be persisted to DB even if Cognito update_user_attributes fails."""
        self._login_with_token()
        with patch('Voices.views.CognitoService') as MockCognito:
            inst = MockCognito.return_value
            inst.update_user_attributes.return_value = {
                'success': False, 'error': 'ServiceUnavailable',
            }
            self.client.post(reverse('myprofile'), {
                'update_profile': '1',
                'email': 'updated_locally@example.com',
                'phone_number': '+254799999999',
                'user_type': 'victim',
            })

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated_locally@example.com')

    def test_password_unchanged_when_cognito_rejects_change(self):
        """Local password must NOT be updated if Cognito rejects the change."""
        self._login_with_token()
        original_hash = User.objects.get(pk=self.user.pk).password

        with patch('Voices.views.CognitoService') as MockCognito:
            inst = MockCognito.return_value
            inst.change_password.return_value = {
                'success': False,
                'error': 'Incorrect username or password.',
            }
            response = self.client.post(reverse('myprofile'), {
                'change_password': '1',
                'current_password': 'StrongPassword123!',
                'new_password': 'StrongerP@ssword99!',
                'confirm_password': 'StrongerP@ssword99!',
            })

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original_hash)

    def test_role_change_persists_locally_when_cognito_fails(self):
        """Role switch must be committed to DB and session even if Cognito sync fails."""
        self._login_with_token()

        with patch('Voices.views.CognitoService') as MockCognito:
            inst = MockCognito.return_value
            inst.update_user_attributes.return_value = {
                'success': False, 'error': 'TokenExpiredException',
            }
            response = self.client.post(reverse('change_role'), {'next': '/'})

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.user_type, 'contributor')
