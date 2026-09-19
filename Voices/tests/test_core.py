import json
from datetime import timedelta
from unittest.mock import patch
import urllib.error

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from Voices.forms import ContactForm, GBVReportForm, ArticleSubmissionForm, StorySubmissionForm, ResourceSubmissionForm, IdeaSubmissionForm
from Voices.models import GBVReport, Resource, Article, Blog, SupportFeedback, UserProfile


class ReportGBVViewTests(TestCase):
	def test_report_gbv_valid_submission_redirects_and_saves(self):
		payload = {
			'report_type': 'physical',
			'location': 'Kisumu',
			'description': 'Incident description',
			'consent': 'on',
		}
		response = self.client.post(reverse('report_gbv'), payload, follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(GBVReport.objects.count(), 1)
		self.assertContains(response, 'submitted successfully', status_code=200)


class ResourceNavigateViewTests(TestCase):
	def test_resource_navigate_returns_404_for_missing_resource(self):
		response = self.client.get(reverse('resource_navigate', args=[99999]))
		self.assertEqual(response.status_code, 404)

	def test_resource_navigate_renders_existing_resource(self):
		resource = Resource.objects.create(
			resource_type='police',
			name='Central Police',
			location='Nairobi',
		)
		response = self.client.get(reverse('resource_navigate', args=[resource.id]))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Central Police')


class RouteApiTests(TestCase):
	def test_route_api_requires_origin_and_destination(self):
		response = self.client.get(reverse('route_api'))
		self.assertEqual(response.status_code, 400)

	@patch('Voices.views.urllib.request.urlopen')
	def test_route_api_success(self, mock_urlopen):
		class DummyResponse:
			def __enter__(self):
				return self

			def __exit__(self, exc_type, exc_val, exc_tb):
				return False

			def read(self):
				payload = {'code': 'Ok', 'routes': [{'geometry': {'type': 'LineString', 'coordinates': []}}]}
				return json.dumps(payload).encode('utf-8')

		mock_urlopen.return_value = DummyResponse()

		response = self.client.get(
			reverse('route_api'),
			{'origin': '36.8,-1.2', 'destination': '36.9,-1.3'}
		)
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertEqual(body.get('code'), 'Ok')
		self.assertEqual(body.get('profile_used'), 'driving')
		self.assertTrue(body.get('routes'))

	@patch('Voices.views.urllib.request.urlopen')
	def test_route_api_timeout_returns_fallback_route(self, mock_urlopen):
		mock_urlopen.side_effect = urllib.error.URLError('timed out')
		response = self.client.get(
			reverse('route_api'),
			{'origin': '36.8,-1.2', 'destination': '36.9,-1.3'}
		)
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertEqual(body.get('code'), 'Ok')
		self.assertTrue(body.get('fallback'))
		self.assertTrue(body.get('routes'))


class FormsValidationTests(TestCase):
	def test_contact_form_valid(self):
		form = ContactForm(data={
			'name': 'Jane Doe',
			'email': 'jane@example.com',
			'subject': 'Help',
			'message': 'Need assistance with resources',
		})
		self.assertTrue(form.is_valid())

	def test_gbv_form_rejects_future_date(self):
		form = GBVReportForm(data={
			'report_type': 'physical',
			'location': 'Nairobi',
			'incident_date': '2999-01-01',
			'description': 'Valid description content',
			'consent': True,
		})
		self.assertFalse(form.is_valid())
		self.assertIn('incident_date', form.errors)

	def test_article_form_min_length(self):
		form = ArticleSubmissionForm(data={
			'title': 'Hi',
			'author': 'Jane Doe',
			'category': 'education',
			'content': 'short',
			'anonymous': False,
		})
		self.assertFalse(form.is_valid())
		self.assertIn('title', form.errors)
		self.assertIn('content', form.errors)

	def test_story_form_requires_consent(self):
		form = StorySubmissionForm(data={
			'story': 'This is a sufficiently long story for validation purposes.',
			'name': 'Jane Doe',
			'consent': False,
		})
		self.assertFalse(form.is_valid())
		self.assertIn('consent', form.errors)

	def test_resource_form_valid(self):
		form = ResourceSubmissionForm(data={
			'resource_type': 'police',
			'name': 'Central Police',
			'location': 'Nairobi',
			'address': 'CBD',
			'phone': '+254700000000',
			'description': 'Open 24/7',
		})
		self.assertTrue(form.is_valid())

	def test_idea_form_requires_min_description(self):
		form = IdeaSubmissionForm(data={
			'title': 'Better alerts',
			'category': 'feature',
			'description': 'short',
			'name': 'Jane Doe',
			'email': 'jane@example.com',
		})
		self.assertFalse(form.is_valid())
		self.assertIn('description', form.errors)


class ContributionApprovalWorkflowTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='contrib', password='StrongPassword123!')
		UserProfile.objects.create(user=self.user, user_type='contributor')
		self.client.force_login(self.user)
		session = self.client.session
		session['user_type'] = 'contributor'
		session.save()

	def test_submitted_article_is_pending_by_default(self):
		payload = {
			'title': 'Understanding Prevention Strategies',
			'author': 'Contributor Name',
			'category': 'prevention',
			'content': 'This is a long enough article body to satisfy minimum length validation for submission.'
		}
		response = self.client.post(reverse('contribute_article'), payload, follow=True)
		self.assertEqual(response.status_code, 200)
		article = Article.objects.get(title='Understanding Prevention Strategies')
		self.assertFalse(article.published)


class ResourcesMapViewTests(TestCase):
	def test_resources_map_page_loads(self):
		Resource.objects.create(resource_type='police', name='Central Police', location='Nairobi')
		response = self.client.get(reverse('resources_map'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'All Resources Map')
		self.assertContains(response, 'resources-data')


class PublicPagesSmokeTests(TestCase):
	def setUp(self):
		self.blog = Blog.objects.create(
			title='Published blog',
			author='Author',
			content='Blog content long enough for rendering checks',
			published=True,
		)
		self.article = Article.objects.create(
			title='Published article',
			author='Author',
			category='education',
			content='Article content long enough for rendering checks and smoke testing.',
			published=True,
		)

	def test_primary_public_pages_load(self):
		for name in [
			'home', 'report_gbv', 'education', 'resources', 'resources_map',
			'contribute', 'about', 'contact', 'emergency', 'login',
			'signup', 'forgot_password', 'reset_password'
		]:
			response = self.client.get(reverse(name))
			self.assertIn(response.status_code, [200, 302], msg=f'{name} returned {response.status_code}')

	def test_detail_pages_load(self):
		blog_response = self.client.get(reverse('blog_detail', args=[self.blog.id]))
		article_response = self.client.get(reverse('article_detail', args=[self.article.id]))
		self.assertEqual(blog_response.status_code, 200)
		self.assertEqual(article_response.status_code, 200)

	def test_detail_pages_increment_views(self):
		self.assertEqual(self.blog.views, 0)
		self.assertEqual(self.article.views, 0)

		self.client.get(reverse('blog_detail', args=[self.blog.id]))
		self.client.get(reverse('article_detail', args=[self.article.id]))

		self.blog.refresh_from_db()
		self.article.refresh_from_db()

		self.assertEqual(self.blog.views, 1)
		self.assertEqual(self.article.views, 1)

	def test_education_page_shows_updated_view_counts(self):
		Blog.objects.filter(id=self.blog.id).update(views=7)
		Article.objects.filter(id=self.article.id).update(views=11)

		response = self.client.get(reverse('education'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '7 views')
		self.assertContains(response, '11 views')


class SignupVerificationTests(TestCase):
	@patch('Voices.views.CognitoService')
	def test_signup_and_verification_persists_first_and_last_name(self, MockCognito):
		cognito = MockCognito.return_value
		cognito.email_exists.return_value = False
		cognito.phone_exists.return_value = False
		cognito.register_user.return_value = {
			'success': True,
			'delivery': {'medium': 'EMAIL', 'destination': 'jane@example.com'},
		}
		cognito.confirm_email.return_value = {'success': True}

		signup_payload = {
			'first_name': 'Jane',
			'last_name': 'Doe',
			'username': 'janedoe',
			'email': 'jane@example.com',
			'phone_number': '+254700000000',
			'user_type': 'victim',
			'gender': 'female',
			'password1': 'StrongPassword123!',
			'password2': 'StrongPassword123!',
		}

		signup_response = self.client.post(reverse('signup'), signup_payload)
		self.assertEqual(signup_response.status_code, 302)
		self.assertEqual(signup_response.url, reverse('verify_email'))

		user = User.objects.get(username='janedoe')
		self.assertEqual(user.first_name, 'Jane')
		self.assertEqual(user.last_name, 'Doe')
		self.assertFalse(user.is_active)

		verify_response = self.client.post(reverse('verify_email'), {'code': '123456'})
		self.assertEqual(verify_response.status_code, 302)
		self.assertEqual(verify_response.url, reverse('login'))

		user.refresh_from_db()
		self.assertEqual(user.first_name, 'Jane')
		self.assertEqual(user.last_name, 'Doe')
		self.assertTrue(user.is_active)


class AdminMetricsApiTests(TestCase):
	def test_admin_metrics_labels_are_unique_and_bounded(self):
		admin_user = User.objects.create_superuser(
			username='admin1',
			email='admin1@example.com',
			password='StrongPassword123!'
		)

		report = GBVReport.objects.create(
			report_type='physical',
			location='Nairobi',
			description='Metrics seed report',
			consent=True,
		)
		SupportFeedback.objects.create(report=report, score=4, comment='Helpful support.')
		self.client.force_login(admin_user)

		response = self.client.get(reverse('admin_metrics_api'))
		self.assertEqual(response.status_code, 200)
		body = response.json()

		labels = body.get('labels', [])
		self.assertEqual(len(labels), 6)
		self.assertEqual(len(set(labels)), 6)
		self.assertTrue(isinstance(body.get('y_max'), int))
		self.assertGreaterEqual(body.get('y_max'), 0)
		self.assertIn('support_feedback', body.get('summary', {}))
		self.assertIn('feedback_avg', body.get('summary', {}))
		self.assertIn('status_breakdown', body.get('summary', {}))
		self.assertEqual(body['summary']['support_feedback'], 1)
		self.assertEqual(body['summary']['feedback_avg'], 4.0)
		self.assertEqual(body['summary']['status_breakdown']['received'], 1)
		self.assertEqual(len(body.get('series', {}).get('support_feedback', [])), 6)


class AdminReportExportsTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_superuser(
			username='admin_export',
			email='admin_export@example.com',
			password='StrongPassword123!'
		)
		self.regular_user = User.objects.create_user(
			username='regular_export',
			email='regular_export@example.com',
			password='StrongPassword123!'
		)
		self.report = GBVReport.objects.create(
			report_type='emotional',
			location='Kisumu',
			description='Export test report',
			consent=True,
			submitted_by=self.regular_user,
		)
		self.closed_report = GBVReport.objects.create(
			report_type='physical',
			location='Nairobi',
			description='Closed export report',
			consent=True,
			submitted_by=self.regular_user,
			status=GBVReport.STATUS_CLOSED,
		)
		SupportFeedback.objects.create(report=self.report, score=5, comment='Excellent follow-up')
		SupportFeedback.objects.create(report=self.closed_report, score=1, comment='Poor follow-up')

	def test_gbv_export_requires_staff(self):
		self.client.force_login(self.regular_user)
		response = self.client.get(reverse('export_gbv_reports_csv'))
		self.assertEqual(response.status_code, 302)

	def test_gbv_export_returns_csv_for_staff(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('export_gbv_reports_csv'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'text/csv')
		self.assertIn('gbv_reports_export.csv', response['Content-Disposition'])
		content = response.content.decode('utf-8')
		self.assertIn('id,created_at,status,report_type,location,incident_date,anonymous,followup_opt_in,followup_email,submitted_by', content)
		self.assertIn('emotional', content)

	def test_support_feedback_export_returns_csv_for_staff(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('export_support_feedback_csv'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'text/csv')
		self.assertIn('support_feedback_export.csv', response['Content-Disposition'])
		content = response.content.decode('utf-8')
		self.assertIn('id,created_at,report_id,report_status,report_type,score,comment', content)
		self.assertIn('Excellent follow-up', content)

	def test_gbv_export_filters_by_status(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('export_gbv_reports_csv'), {'status': 'closed'})
		self.assertEqual(response.status_code, 200)
		content = response.content.decode('utf-8')
		self.assertIn('closed', content)
		self.assertNotIn('received', content)

	def test_feedback_export_filters_by_score(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('export_support_feedback_csv'), {'min_score': 1, 'max_score': 2})
		self.assertEqual(response.status_code, 200)
		content = response.content.decode('utf-8')
		self.assertIn('Poor follow-up', content)
		self.assertNotIn('Excellent follow-up', content)


class ReportTimelineEnhancementTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='timeline_user', password='StrongPassword123!')
		self.report = GBVReport.objects.create(
			report_type='physical',
			location='Nakuru',
			description='Timeline insight report',
			consent=True,
			submitted_by=self.user,
			status=GBVReport.STATUS_ASSIGNED,
		)

	def test_report_timeline_includes_status_insight(self):
		self.client.force_login(self.user)
		response = self.client.get(reverse('report_timeline', args=[self.report.id]))
		self.assertEqual(response.status_code, 200)
		self.assertIn('status_insight', response.context)
		insight = response.context['status_insight']
		self.assertEqual(insight['next_step'], 'Case worker engagement')
		self.assertIn('Estimated next update', insight['eta_text'])


class AdminSlaReportTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_superuser(
			username='admin_sla',
			email='admin_sla@example.com',
			password='StrongPassword123!'
		)
		self.regular_user = User.objects.create_user(
			username='regular_sla',
			email='regular_sla@example.com',
			password='StrongPassword123!'
		)

		now = timezone.now()
		self.received_report = GBVReport.objects.create(
			report_type='emotional',
			location='Kisumu',
			description='Received case for SLA API',
			consent=True,
			submitted_by=self.regular_user,
			status=GBVReport.STATUS_RECEIVED,
			status_updated_at=now - timedelta(hours=30),
		)
		self.in_progress_report = GBVReport.objects.create(
			report_type='physical',
			location='Nairobi',
			description='In progress case for SLA API',
			consent=True,
			submitted_by=self.regular_user,
			status=GBVReport.STATUS_IN_PROGRESS,
			status_updated_at=now - timedelta(hours=10),
		)

	def test_sla_api_requires_staff(self):
		self.client.force_login(self.regular_user)
		response = self.client.get(reverse('admin_gbv_sla_api'))
		self.assertEqual(response.status_code, 302)

	def test_sla_api_returns_expected_summary_for_staff(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('admin_gbv_sla_api'))
		self.assertEqual(response.status_code, 200)

		body = response.json()
		self.assertIn('generated_at', body)
		self.assertIn('summary', body)
		summary = body['summary']
		self.assertEqual(summary['total_reports'], 2)
		self.assertEqual(summary['open_reports'], 2)
		self.assertEqual(summary['overdue_total'], 1)
		self.assertEqual(summary['overdue_by_status']['received'], 1)
		self.assertIn('age_buckets', summary)
		self.assertIn('median_age_hours_by_status', summary)

	def test_sla_api_respects_status_filter(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('admin_gbv_sla_api'), {'status': 'received'})
		self.assertEqual(response.status_code, 200)

		summary = response.json()['summary']
		self.assertEqual(summary['total_reports'], 1)
		self.assertEqual(summary['overdue_total'], 1)

	def test_sla_csv_requires_staff(self):
		self.client.force_login(self.regular_user)
		response = self.client.get(reverse('export_gbv_sla_csv'))
		self.assertEqual(response.status_code, 302)

	def test_sla_csv_returns_expected_columns_for_staff(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('export_gbv_sla_csv'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'text/csv')
		self.assertIn('gbv_sla_export.csv', response['Content-Disposition'])

		content = response.content.decode('utf-8')
		self.assertIn('id,created_at,status,status_updated_at,age_hours,sla_target_hours,is_overdue,overdue_hours,report_type,location,incident_date,submitted_by', content)
		self.assertIn('yes', content)

	def test_sla_csv_respects_status_filter(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('export_gbv_sla_csv'), {'status': 'in_progress'})
		self.assertEqual(response.status_code, 200)

		content = response.content.decode('utf-8')
		self.assertIn('in_progress', content)
		self.assertNotIn('received', content)

	def test_sla_csv_filters_only_overdue_when_requested(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('export_gbv_sla_csv'), {'overdue_only': '1'})
		self.assertEqual(response.status_code, 200)

		content = response.content.decode('utf-8')
		self.assertIn('Kisumu', content)
		self.assertNotIn('Nairobi', content)
		self.assertIn('yes', content)
		self.assertNotIn('no', content)


class AdminDashboardSlaQuickActionTests(TestCase):
	def test_admin_index_shows_sla_export_quick_action(self):
		admin_user = User.objects.create_superuser(
			username='admin_dashboard_sla',
			email='admin_dashboard_sla@example.com',
			password='StrongPassword123!'
		)
		self.client.force_login(admin_user)

		response = self.client.get(reverse('admin:index'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Export GBV SLA CSV')
		self.assertContains(response, reverse('export_gbv_sla_csv'))
		self.assertContains(response, 'SLA Watchlist')
		self.assertContains(response, 'qa-open-cases')
		self.assertContains(response, 'qa-overdue-cases')
