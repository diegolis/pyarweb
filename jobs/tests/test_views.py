import bleach

from django.utils import timezone
from django.test import TestCase, Client
from django.core.urlresolvers import reverse

from jobs.models import Job
from jobs.tests.factories import JobFactory
from events.tests.factories import UserFactory
from pycompanies.tests.factories import CompanyFactory


class JobsTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.login(username=self.user.username, password='secret')

    def test_jobs_view_list(self):
        job = JobFactory(owner=self.user)
        company = CompanyFactory(owner=self.user, rank=3)
        sponsored_job = JobFactory(owner=self.user, company=company)
        sponsored_job2 = JobFactory(owner=self.user, company=company)

        response = self.client.get(reverse('jobs_list_all'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(job, response.context["job_list"])
        self.assertEqual(len(response.context["job_list"]), 1)
        self.assertIn(sponsored_job, response.context["sponsored_jobs"])
        self.assertIn(sponsored_job2, response.context["sponsored_jobs"])
        self.assertEqual(len(response.context["sponsored_jobs"]), 2)

    def test_jobs_view_list_regular_and_sponsored(self):
        sponsored_company = CompanyFactory(name='Name', owner=self.user, rank=3)
        sponsored_job = JobFactory(owner=self.user, company=sponsored_company)
        sponsored_job_2 = JobFactory(owner=self.user, company=sponsored_company)

        company = CompanyFactory(name='Other name', owner=self.user, rank=0)
        job = JobFactory(owner=self.user, company=company)
        job_2 = JobFactory(owner=self.user, company=company)

        response = self.client.get(reverse('jobs_list_all'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(job, response.context["job_list"])
        self.assertIn(job_2, response.context["job_list"])
        self.assertEqual(len(response.context["job_list"]), 2)
        self.assertIn(sponsored_job, response.context["sponsored_jobs"])
        self.assertIn(sponsored_job_2, response.context["sponsored_jobs"])
        self.assertEqual(len(response.context["sponsored_jobs"]), 2)

    def _create_job(self, days_ago):
        date = timezone.now() - timezone.timedelta(days=days_ago)
        date = date.replace(hour=0, minute=0, second=0)
        return JobFactory(owner=self.user, set_created=date)

    def _test_jobs_filter_by_created(self, filter_value, jobs_in_range, jobs_out_of_range):
        response = self.client.get(
            reverse('jobs_list_all'), {'created': filter_value})
        self.assertEqual(response.status_code, 200)
        for job in jobs_in_range:
            self.assertIn(job, response.context["job_list"])
        self.assertEqual(len(response.context["job_list"]), len(jobs_in_range))

    def test_jobs_filter_today(self):
        self._test_jobs_filter_by_created(
            filter_value='today',
            jobs_in_range=[self._create_job(days_ago=0)],
            jobs_out_of_range=[self._create_job(days_ago=1)])

    def test_jobs_filter_yesterday(self):
        self._test_jobs_filter_by_created(
            filter_value='yesterday',
            jobs_in_range=[self._create_job(days_ago=1)],
            jobs_out_of_range=[self._create_job(days_ago=2)])

    def test_jobs_filter_last_3_days(self):
        self._test_jobs_filter_by_created(
            filter_value='last_3_days',
            jobs_in_range=[self._create_job(days_ago=1), self._create_job(days_ago=2)],
            jobs_out_of_range=[self._create_job(days_ago=3)])

    def test_jobs_filter_last_week(self):
        self._test_jobs_filter_by_created(
            filter_value='last_week',
            jobs_in_range=[self._create_job(days_ago=1), self._create_job(days_ago=6)],
            jobs_out_of_range=[self._create_job(days_ago=7)])

    def test_jobs_filter_month_ago(self):
        self._test_jobs_filter_by_created(
            filter_value='month_ago',
            jobs_in_range=[self._create_job(days_ago=28)],
            jobs_out_of_range=[self._create_job(days_ago=38)])

    def test_jobs_filter_title(self):
        self._test_jobs_filter('title', 'A', 'B')

    def test_jobs_filter_company(self):
        company1 = CompanyFactory(owner=self.user, name='A')
        company2 = CompanyFactory(owner=self.user, name='B')
        self._test_jobs_filter('company', company1, company2, filter_value=company1.id)

    def test_jobs_filter_seniority(self):
        self._test_jobs_filter('seniority', 'Junior', 'Senior')

    def test_jobs_filter_location(self):
        self._test_jobs_filter('location', 'Córdoba', 'Bs As')

    def test_jobs_filter_remote_work(self):
        self._test_jobs_filter('remote_work', True, False, filter_value='remote')

    def _test_jobs_filter(self, filter_name, case1, case2, filter_value=None):
        job1 = JobFactory(
            **{'owner': self.user, filter_name: case1})
        JobFactory(
            **{'owner': self.user, filter_name: case2})
        if filter_value is None:
            filter_value = case1
        response = self.client.get(
            reverse('jobs_list_all'), {filter_name: filter_value})
        self.assertEqual(response.status_code, 200)
        self.assertIn(job1, response.context["job_list"])
        self.assertEqual(len(response.context["job_list"]), 1)

    def test_jobs_view_create(self):
        response = self.client.get(reverse('jobs_add'))
        job = {
            'title': 'Python Dev',
            'location': 'Bahia Blanca',
            'email': 'info@undominio.com',
            'tags': 'python,remoto,django',
            'description': 'Buscamos desarrollador python freelance.'
        }
        response = self.client.post(reverse('jobs_add'), job)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Job.objects.filter(title='Python Dev').count(), 1)

    def test_jobs_view_create_avoiding_repeated_tags(self):
        response = self.client.get(reverse('jobs_add'))
        job = {
            'title': 'Python Dev',
            'location': 'Bahia Blanca',
            'email': 'info@undominio.com',
            'tags': 'python,remoto,DJANGO,django',
            'description': 'Buscamos desarrollador python freelance.'
        }
        response = self.client.post(reverse('jobs_add'), job)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Job.objects.filter(title='Python Dev').count(), 1)
        self.assertEqual(Job.objects.all()[0].tags.all().count(), 3)

    def test_jobs_view_edit(self):
        job = JobFactory(
            owner=self.user, title='Python Dev',
            description='Buscamos desarrollador python freelance',
            location='Bahia Blanca', email='info@undominio')

        response = self.client.get(reverse('jobs_update', args=(job.pk, )))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["object"], job)
        job_data = {
            'title': 'Python Dev 2',
            'location': 'Azul',
            'email': 'info@undominio.com',
            'tags': 'python,remoto,django',
            'description': 'Buscamos desarrollador python freelance.'
        }
        response = self.client.post(reverse('jobs_update', args=(job.pk, )), job_data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Job.objects.filter(title='Python Dev').exists())
        edit_job = Job.objects.get(pk=job.pk)
        self.assertEqual(edit_job.location, "Azul")
        self.assertEqual(edit_job.title, "Python Dev 2")

    def test_jobs_view_idelete(self):
        job = JobFactory(
            owner=self.user, title='Python/Django Dev',
            description='Buscamos desarrollador python freelance',
            location='General Pico', email='info@fdq.com')

        response = self.client.get(reverse('jobs_delete', args=(job.pk, )))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["object"], job)

        response = self.client.post(reverse('jobs_delete', args=(job.pk, )))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Job.objects.filter(title='Python/Django Dev').exists())

    def test_html_sanitizer_in_description_field(self):
        response = self.client.get(reverse('jobs_add'))
        job = {
            'title': 'Python Dev',
            'location': 'Cruz del Eje',
            'email': 'info@undominio.com',
            'tags': 'python,remoto,django',
            'description': 'an <script>evil()</script> example'
        }
        response = self.client.post(reverse('jobs_add'), job)
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(title='Python Dev')
        self.assertEqual(job.description, bleach.clean('an <script>evil()</script> example'))
