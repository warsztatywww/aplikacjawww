import datetime

from django.contrib.auth.models import User
from django.db.models import Max
from django.test.testcases import TestCase
from django.test.utils import override_settings

from wwwapp.models import Camp, Workshop, Solution, WorkshopType, WorkshopCategory, CampParticipant


class WorkshopCountTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.user1 = User.objects.create_user(
            username='user1', email='user1@example.com', password='user123')
        self.user2 = User.objects.create_user(
            username='user2', email='user2@example.com', password='user123')
        self.user3 = User.objects.create_user(
            username='user3', email='user3@example.com', password='user123')
        self.user4 = User.objects.create_user(
            username='user4', email='user4@example.com', password='user123')
        self.user5 = User.objects.create_user(
            username='user5', email='user5@example.com', password='user123')
        self.user6 = User.objects.create_user(
            username='user6', email='user6@example.com', password='user123')

        # TODO: This is weird because of the constraint that one Camp object needs to exist at all times
        Camp.objects.all().update(year=2020,
                                  proposal_end_date=datetime.date(2020, 4, 1),
                                  start_date=datetime.date(2020, 7, 3),
                                  end_date=datetime.date(2020, 7, 15),
                                  program_finalized=False)
        self.year_2020 = Camp.objects.get()
        WorkshopType.objects.create(year=self.year_2020, name='Type')
        WorkshopCategory.objects.create(year=self.year_2020, name='Category')

    def test_counts(self):
        # Add a test workshop
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            solution_uploads_enabled=True
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
        # user1 is not participating at all
        # user2 is participating, but not in this workshop
        cp2 = self.year_2020.participants.create(user_profile=self.user2.user_profile)
        # user3 is participating in this workshop, but did not submit a solution
        cp3 = self.year_2020.participants.create(user_profile=self.user3.user_profile)
        wp3 = workshop.participants.create(camp_participation=cp3)
        # user4 is participating in this workshop, and did submit a solution, but it's not graded
        cp4 = self.year_2020.participants.create(user_profile=self.user4.user_profile)
        wp4 = workshop.participants.create(camp_participation=cp4)
        Solution.objects.create(workshop_participant=wp4)
        # user5 is participating in this workshop, did submit a solution, and is accepted
        cp5 = self.year_2020.participants.create(user_profile=self.user5.user_profile)
        wp5 = workshop.participants.create(camp_participation=cp5, qualification_result=7.5)
        Solution.objects.create(workshop_participant=wp5)
        # user6 is participating in this workshop, did submit a solution, and is rejected
        cp6 = self.year_2020.participants.create(user_profile=self.user6.user_profile)
        wp6 = workshop.participants.create(camp_participation=cp6, qualification_result=2.5)
        Solution.objects.create(workshop_participant=wp6)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 4)
            self.assertEqual(workshop.solution_count, 3)
            self.assertEqual(workshop.checked_solution_count, 2)
            self.assertEqual(workshop.to_be_checked_solution_count, workshop.solution_count)
            self.assertEqual(workshop.checked_solution_percentage, 2/3 * 100)
            self.assertEqual(workshop.qualified_count, 1)
            self.assertEqual(workshop.max_entered_points, 7.5)
        # Test the participant qualification methods
        with self.assertNumQueries(4):
            wp3 = workshop.participants.get(camp_participation__user_profile__user=self.user3)
            wp4 = workshop.participants.get(camp_participation__user_profile__user=self.user4)
            wp5 = workshop.participants.get(camp_participation__user_profile__user=self.user5)
            wp6 = workshop.participants.get(camp_participation__user_profile__user=self.user6)
            self.assertEqual(wp3.result_in_percent, None)
            self.assertEqual(wp4.result_in_percent, None)
            self.assertEqual(wp5.result_in_percent, 75.0)
            self.assertEqual(wp6.result_in_percent, 25.0)
            self.assertEqual(wp3.is_qualified, None)
            self.assertEqual(wp4.is_qualified, None)
            self.assertEqual(wp5.is_qualified, True)
            self.assertEqual(wp6.is_qualified, False)

    def test_counts_with_no_solutions(self):
        # Add a test workshop from before we had solution uploads
        workshop = Workshop.objects.create(
            title='Stare warsztaty',
            name='stare',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            solution_uploads_enabled=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
        # user1 is not participating at all
        # user2 is participating, but not in this workshop
        cp2 = self.year_2020.participants.create(user_profile=self.user2.user_profile)
        # user4 is participating in this workshop, but is not graded
        cp4 = self.year_2020.participants.create(user_profile=self.user4.user_profile)
        wp4 = workshop.participants.create(camp_participation=cp4)
        # user5 is participating in this workshop, and is accepted
        cp5 = self.year_2020.participants.create(user_profile=self.user5.user_profile)
        wp5 = workshop.participants.create(camp_participation=cp5, qualification_result=7.5)
        # user6 is participating in this workshop, and is rejected
        cp6 = self.year_2020.participants.create(user_profile=self.user6.user_profile)
        wp6 = workshop.participants.create(camp_participation=cp6, qualification_result=2.5)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 3)
            self.assertEqual(workshop.solution_count, None)
            self.assertEqual(workshop.checked_solution_count, 2)
            self.assertEqual(workshop.to_be_checked_solution_count, workshop.registered_count)
            self.assertEqual(workshop.checked_solution_percentage, 2/3 * 100)
            self.assertEqual(workshop.qualified_count, 1)
            self.assertEqual(workshop.max_entered_points, 7.5)
        # Test the participant qualification methods
        with self.assertNumQueries(3):
            wp4 = workshop.participants.get(camp_participation__user_profile__user=self.user4)
            wp5 = workshop.participants.get(camp_participation__user_profile__user=self.user5)
            wp6 = workshop.participants.get(camp_participation__user_profile__user=self.user6)
            self.assertEqual(wp4.result_in_percent, None)
            self.assertEqual(wp5.result_in_percent, 75.0)
            self.assertEqual(wp6.result_in_percent, 25.0)
            self.assertEqual(wp4.is_qualified, None)
            self.assertEqual(wp5.is_qualified, True)
            self.assertEqual(wp6.is_qualified, False)

    def test_counts_with_no_max_points(self):
        # Add a test workshop from before we had max_points
        workshop = Workshop.objects.create(
            title='Bardzo stare warsztaty',
            name='bardzostare',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=None,
            qualification_threshold=5,
            solution_uploads_enabled=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
        # user1 is not participating at all
        # user2 is participating, but not in this workshop
        cp2 = self.year_2020.participants.create(user_profile=self.user2.user_profile)
        # user4 is participating in this workshop, but is not graded
        cp4 = self.year_2020.participants.create(user_profile=self.user4.user_profile)
        wp4 = workshop.participants.create(camp_participation=cp4)
        # user5 is participating in this workshop, and is accepted
        cp5 = self.year_2020.participants.create(user_profile=self.user5.user_profile)
        wp5 = workshop.participants.create(camp_participation=cp5, qualification_result=7.5)
        # user6 is participating in this workshop, and is rejected
        cp6 = self.year_2020.participants.create(user_profile=self.user6.user_profile)
        wp6 = workshop.participants.create(camp_participation=cp6, qualification_result=2.5)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 3)
            self.assertEqual(workshop.solution_count, None)
            self.assertEqual(workshop.checked_solution_count, 2)
            self.assertEqual(workshop.to_be_checked_solution_count, workshop.registered_count)
            self.assertEqual(workshop.checked_solution_percentage, 2/3 * 100)
            self.assertEqual(workshop.qualified_count, 1)
            self.assertEqual(workshop.max_entered_points, 7.5)
        # Test the participant qualification methods
        with self.assertNumQueries(3):
            wp4 = workshop.participants.get(camp_participation__user_profile__user=self.user4)
            wp5 = workshop.participants.get(camp_participation__user_profile__user=self.user5)
            wp6 = workshop.participants.get(camp_participation__user_profile__user=self.user6)
            self.assertEqual(wp4.result_in_percent, None)
            self.assertEqual(wp5.result_in_percent, 100.0)
            self.assertAlmostEqual(float(wp6.result_in_percent), 1/3*100)
            self.assertEqual(wp4.is_qualified, None)
            self.assertEqual(wp5.is_qualified, True)
            self.assertEqual(wp6.is_qualified, False)

    def test_counts_with_no_threshold(self):
        # Add a test workshop that does not have a qualification threshold set yet
        workshop = Workshop.objects.create(
            title='Bardzo stare warsztaty',
            name='bardzostare',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=None,
            qualification_threshold=None,
            solution_uploads_enabled=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
        # user1 is not participating at all
        # user2 is participating, but not in this workshop
        cp2 = self.year_2020.participants.create(user_profile=self.user2.user_profile)
        # user4 is participating in this workshop, but is not graded
        cp4 = self.year_2020.participants.create(user_profile=self.user4.user_profile)
        wp4 = workshop.participants.create(camp_participation=cp4)
        # user5 is participating in this workshop, and is accepted
        cp5 = self.year_2020.participants.create(user_profile=self.user5.user_profile)
        wp5 = workshop.participants.create(camp_participation=cp5, qualification_result=7.5)
        # user6 is participating in this workshop, and is rejected
        cp6 = self.year_2020.participants.create(user_profile=self.user6.user_profile)
        wp6 = workshop.participants.create(camp_participation=cp6, qualification_result=2.5)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 3)
            self.assertEqual(workshop.solution_count, None)
            self.assertEqual(workshop.checked_solution_count, 2)
            self.assertEqual(workshop.to_be_checked_solution_count, workshop.registered_count)
            self.assertEqual(workshop.checked_solution_percentage, 2/3 * 100)
            self.assertEqual(workshop.qualified_count, None)
            self.assertEqual(workshop.max_entered_points, 7.5)
        # Test the participant qualification methods
        with self.assertNumQueries(3):
            wp4 = workshop.participants.get(camp_participation__user_profile__user=self.user4)
            wp5 = workshop.participants.get(camp_participation__user_profile__user=self.user5)
            wp6 = workshop.participants.get(camp_participation__user_profile__user=self.user6)
            self.assertEqual(wp4.result_in_percent, None)
            self.assertEqual(wp5.result_in_percent, 100.0)
            self.assertAlmostEqual(float(wp6.result_in_percent), 1/3*100)
            self.assertEqual(wp4.is_qualified, None)
            self.assertEqual(wp5.is_qualified, None)
            self.assertEqual(wp6.is_qualified, None)

    def test_checked_percentage_with_nothing_to_check(self):
        # Add a test workshop
        workshop = Workshop.objects.create(
            title='Bardzo niepopularne',
            name='niepopularne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            solution_uploads_enabled=True
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
        # user1 is not participating at all
        # user2 is participating, but not in this workshop
        cp2 = self.year_2020.participants.create(user_profile=self.user2.user_profile)
        # user3 is participating in this workshop, but did not submit a solution
        cp3 = self.year_2020.participants.create(user_profile=self.user3.user_profile)
        wp3 = workshop.participants.create(camp_participation=cp3)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 1)
            self.assertEqual(workshop.solution_count, 0)
            self.assertEqual(workshop.checked_solution_count, 0)
            self.assertEqual(workshop.to_be_checked_solution_count, workshop.solution_count)
            self.assertEqual(workshop.checked_solution_percentage, -1)
            self.assertEqual(workshop.qualified_count, 0)
            self.assertEqual(workshop.max_entered_points, None)
        # Test the participant qualification methods
        with self.assertNumQueries(1):
            wp3 = workshop.participants.get(camp_participation__user_profile__user=self.user3)
            self.assertEqual(wp3.result_in_percent, None)
            self.assertEqual(wp3.is_qualified, None)

    def test_counts_with_solutions_disabled_later(self):
        # Test an edge case where solutions were disabled after some solutions were already uploaded
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            solution_uploads_enabled=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
        # user1 is not participating at all
        # user2 is participating, but not in this workshop
        cp2 = self.year_2020.participants.create(user_profile=self.user2.user_profile)
        # user3 is participating in this workshop, but did not submit a solution
        cp3 = self.year_2020.participants.create(user_profile=self.user3.user_profile)
        wp3 = workshop.participants.create(camp_participation=cp3)
        # user4 is participating in this workshop, and did submit a solution, but it's not graded
        cp4 = self.year_2020.participants.create(user_profile=self.user4.user_profile)
        wp4 = workshop.participants.create(camp_participation=cp4)
        Solution.objects.create(workshop_participant=wp4)
        # user5 is participating in this workshop, did submit a solution, and is accepted
        cp5 = self.year_2020.participants.create(user_profile=self.user5.user_profile)
        wp5 = workshop.participants.create(camp_participation=cp5, qualification_result=7.5)
        Solution.objects.create(workshop_participant=wp5)
        # user6 is participating in this workshop, did submit a solution, and is rejected
        cp6 = self.year_2020.participants.create(user_profile=self.user6.user_profile)
        wp6 = workshop.participants.create(camp_participation=cp6, qualification_result=2.5)
        Solution.objects.create(workshop_participant=wp6)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 4)
            self.assertEqual(workshop.solution_count, None)
            self.assertEqual(workshop.checked_solution_count, 2)
            self.assertEqual(workshop.to_be_checked_solution_count, workshop.registered_count)
            self.assertEqual(workshop.checked_solution_percentage, 50.0)
            self.assertEqual(workshop.qualified_count, 1)
            self.assertEqual(workshop.max_entered_points, 7.5)
        # Test the participant qualification methods
        with self.assertNumQueries(3):
            wp4 = workshop.participants.get(camp_participation__user_profile__user=self.user4)
            wp5 = workshop.participants.get(camp_participation__user_profile__user=self.user5)
            wp6 = workshop.participants.get(camp_participation__user_profile__user=self.user6)
            self.assertEqual(wp4.result_in_percent, None)
            self.assertEqual(wp5.result_in_percent, 75.0)
            self.assertEqual(wp6.result_in_percent, 25.0)
            self.assertEqual(wp4.is_qualified, None)
            self.assertEqual(wp5.is_qualified, True)
            self.assertEqual(wp6.is_qualified, False)

    def test_counts_with_no_qualification(self):
        # Test an edge case where qualification was disabled after some results were already added
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            solution_uploads_enabled=True,
            is_qualifying=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
        # user1 is not participating at all
        # user2 is participating, but not in this workshop
        cp2 = self.year_2020.participants.create(user_profile=self.user2.user_profile)
        # user3 is participating in this workshop, but did not submit a solution
        cp3 = self.year_2020.participants.create(user_profile=self.user3.user_profile)
        wp3 = workshop.participants.create(camp_participation=cp3)
        # user4 is participating in this workshop, and did submit a solution, but it's not graded
        cp4 = self.year_2020.participants.create(user_profile=self.user4.user_profile)
        wp4 = workshop.participants.create(camp_participation=cp4)
        Solution.objects.create(workshop_participant=wp4)
        # user5 is participating in this workshop, did submit a solution, and is accepted
        cp5 = self.year_2020.participants.create(user_profile=self.user5.user_profile)
        wp5 = workshop.participants.create(camp_participation=cp5, qualification_result=7.5)
        Solution.objects.create(workshop_participant=wp5)
        # user6 is participating in this workshop, did submit a solution, and is rejected
        cp6 = self.year_2020.participants.create(user_profile=self.user6.user_profile)
        wp6 = workshop.participants.create(camp_participation=cp6, qualification_result=2.5)
        Solution.objects.create(workshop_participant=wp6)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 4)
            self.assertEqual(workshop.solution_count, None)
            self.assertEqual(workshop.checked_solution_count, None)
            self.assertEqual(workshop.to_be_checked_solution_count, None)
            self.assertEqual(workshop.checked_solution_percentage, -1)
            self.assertEqual(workshop.qualified_count, None)
        # Test the participant qualification methods
        with self.assertNumQueries(3):
            wp4 = workshop.participants.get(camp_participation__user_profile__user=self.user4)
            wp5 = workshop.participants.get(camp_participation__user_profile__user=self.user5)
            wp6 = workshop.participants.get(camp_participation__user_profile__user=self.user6)
            self.assertEqual(wp4.result_in_percent, None)
            self.assertEqual(wp5.result_in_percent, None)
            self.assertEqual(wp6.result_in_percent, None)
            self.assertEqual(wp4.is_qualified, None)
            self.assertEqual(wp5.is_qualified, None)
            self.assertEqual(wp6.is_qualified, None)

    @override_settings(MAX_POINTS_PERCENT=200)
    def test_result_in_percent_range(self):
        # Test the min and max values for result_in_percent
        workshop = Workshop.objects.create(
            title='Ekstremalne',
            name='extreme',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            solution_uploads_enabled=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))

        # user5 has a lot of points
        cp5 = self.year_2020.participants.create(user_profile=self.user5.user_profile)
        wp5 = workshop.participants.create(camp_participation=cp5, qualification_result=2137)
        # user6 has negative points
        cp6 = self.year_2020.participants.create(user_profile=self.user6.user_profile)
        wp6 = workshop.participants.create(camp_participation=cp6, qualification_result=-2137)

        # Test the count methods
        with self.assertNumQueries(1):
            workshop = Workshop.objects.with_counts().annotate(max_entered_points=Max('participants__qualification_result')).get(pk=workshop.pk)
            self.assertEqual(workshop.registered_count, 2)
            self.assertEqual(workshop.checked_solution_count, 2)
            self.assertEqual(workshop.checked_solution_percentage, 100)
            self.assertEqual(workshop.qualified_count, 1)
            self.assertEqual(workshop.max_entered_points, 2137)
        # Test the participant qualification methods
        with self.assertNumQueries(2):
            wp5 = workshop.participants.get(camp_participation__user_profile__user=self.user5)
            wp6 = workshop.participants.get(camp_participation__user_profile__user=self.user6)
            self.assertEqual(wp5.result_in_percent, 200.0)
            self.assertEqual(wp6.result_in_percent, 0.0)
            self.assertEqual(wp5.is_qualified, True)
            self.assertEqual(wp6.is_qualified, False)


class ParticipantCountTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.user = User.objects.create_user(
            username='user', email='user@example.com', password='user123')

        # TODO: This is weird because of the constraint that one Camp object needs to exist at all times
        Camp.objects.all().update(year=2020,
                                  proposal_end_date=datetime.date(2020, 4, 1),
                                  start_date=datetime.date(2020, 7, 3),
                                  end_date=datetime.date(2020, 7, 15),
                                  program_finalized=False)
        self.year_2020 = Camp.objects.get()
        WorkshopType.objects.create(year=self.year_2020, name='Type')
        WorkshopCategory.objects.create(year=self.year_2020, name='Category')

    def test_counts(self):
        workshops = []
        for i in range(5):
            workshop = Workshop.objects.create(
                title=f'Bardzo fajne warsztaty {i}',
                name=f'bardzofajne{i}',
                year=self.year_2020,
                type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
                proposition_description='<p>Testowy opis</p>',
                status=Workshop.STATUS_ACCEPTED,
                page_content='<p>Testowa strona</p>',
                page_content_is_public=True,
                max_points=10,
                qualification_threshold=5,
                solution_uploads_enabled=True
            )
            workshop.lecturer.add(self.admin_user.user_profile)
            workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
            workshops.append(workshop)

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        # the user is not participating in workshops[0]
        # the user is participating in workshops[1], but did not submit a solution
        wp1 = workshops[1].participants.create(camp_participation=cp)
        # the user is participating in workshops[2], submitted a solution, but is not graded yet
        wp2 = workshops[2].participants.create(camp_participation=cp)
        Solution.objects.create(workshop_participant=wp2)
        # the user is participating in workshops[3], submitted a solution, and is accepted
        wp3 = workshops[3].participants.create(camp_participation=cp, qualification_result=7.5)
        Solution.objects.create(workshop_participant=wp3)
        # the user is participating in workshops[4], submitted a solution, and is rejected
        wp4 = workshops[4].participants.create(camp_participation=cp, qualification_result=2.5)
        Solution.objects.create(workshop_participant=wp4)

        # Test the count methods
        with self.assertNumQueries(4):  # SELECT FROM CampParticipant, WorkshopParticipant, Workshop, Solution
            cp = CampParticipant.objects.prefetch_related('workshop_participation', 'workshop_participation__workshop', 'workshop_participation__solution').get(pk=cp.pk)
            self.assertEqual(cp.workshop_count, 4)
            self.assertEqual(cp.accepted_workshop_count, 1)
            self.assertEqual(cp.to_be_checked_solution_count, 3)
            self.assertEqual(cp.checked_solution_count, 2)
            self.assertEqual(cp.solution_count, 3)
            self.assertEqual(cp.checked_solution_percentage, 2/3*100)
            self.assertEqual(cp.result_in_percent, 100)

    def test_counts_nothing_to_check(self):
        workshops = []
        for i in range(5):
            workshop = Workshop.objects.create(
                title=f'Bardzo fajne warsztaty {i}',
                name=f'bardzofajne{i}',
                year=self.year_2020,
                type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
                proposition_description='<p>Testowy opis</p>',
                status=Workshop.STATUS_ACCEPTED,
                page_content='<p>Testowa strona</p>',
                page_content_is_public=True,
                max_points=10,
                qualification_threshold=5,
                solution_uploads_enabled=True
            )
            workshop.lecturer.add(self.admin_user.user_profile)
            workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
            workshops.append(workshop)

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        # Test the count methods
        with self.assertNumQueries(2):  # SELECT FROM CampParticipant, WorkshopParticipant, realize that there are 0 entries and nothing else needs to be fetched
            cp = CampParticipant.objects.prefetch_related('workshop_participation', 'workshop_participation__workshop', 'workshop_participation__solution').get(pk=cp.pk)
            self.assertEqual(cp.workshop_count, 0)
            self.assertEqual(cp.accepted_workshop_count, 0)
            self.assertEqual(cp.to_be_checked_solution_count, 0)
            self.assertEqual(cp.checked_solution_count, 0)
            self.assertEqual(cp.solution_count, 0)
            self.assertEqual(cp.checked_solution_percentage, -1)
            self.assertEqual(cp.result_in_percent, 0)

    def test_counts_no_upload(self):
        workshops = []
        for i in range(4):
            workshop = Workshop.objects.create(
                title=f'Bardzo fajne warsztaty {i}',
                name=f'bardzofajne{i}',
                year=self.year_2020,
                type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
                proposition_description='<p>Testowy opis</p>',
                status=Workshop.STATUS_ACCEPTED,
                page_content='<p>Testowa strona</p>',
                page_content_is_public=True,
                max_points=10,
                qualification_threshold=5,
                solution_uploads_enabled=False
            )
            workshop.lecturer.add(self.admin_user.user_profile)
            workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
            workshops.append(workshop)

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        # the user is not participating in workshops[0]
        # the user is participating in workshops[1], but is not graded yet
        wp1 = workshops[1].participants.create(camp_participation=cp)
        # the user is participating in workshops[2], and is accepted
        wp2 = workshops[2].participants.create(camp_participation=cp, qualification_result=7.5)
        # the user is participating in workshops[3], and is rejected
        wp3 = workshops[3].participants.create(camp_participation=cp, qualification_result=2.5)

        # Test the count methods
        with self.assertNumQueries(4):  # SELECT FROM CampParticipant, WorkshopParticipant, Workshop, Solution
            cp = CampParticipant.objects.prefetch_related('workshop_participation', 'workshop_participation__workshop', 'workshop_participation__solution').get(pk=cp.pk)
            self.assertEqual(cp.workshop_count, 3)
            self.assertEqual(cp.accepted_workshop_count, 1)
            self.assertEqual(cp.to_be_checked_solution_count, 3)
            self.assertEqual(cp.checked_solution_count, 2)
            self.assertEqual(cp.solution_count, 0)
            self.assertEqual(cp.checked_solution_percentage, 2/3*100)
            self.assertEqual(cp.result_in_percent, 100)

    def test_counts_upload_disabled_later(self):
        # Test an edge case where uploads were disabled after some solutions were already uploaded
        workshops = []
        for i in range(5):
            workshop = Workshop.objects.create(
                title=f'Bardzo fajne warsztaty {i}',
                name=f'bardzofajne{i}',
                year=self.year_2020,
                type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
                proposition_description='<p>Testowy opis</p>',
                status=Workshop.STATUS_ACCEPTED,
                page_content='<p>Testowa strona</p>',
                page_content_is_public=True,
                max_points=10,
                qualification_threshold=5,
                solution_uploads_enabled=False
            )
            workshop.lecturer.add(self.admin_user.user_profile)
            workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))
            workshops.append(workshop)

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        # the user is not participating in workshops[0]
        # the user is participating in workshops[1], but did not submit a solution
        wp1 = workshops[1].participants.create(camp_participation=cp)
        # the user is participating in workshops[2], submitted a solution, but is not graded yet
        wp2 = workshops[2].participants.create(camp_participation=cp)
        Solution.objects.create(workshop_participant=wp2)
        # the user is participating in workshops[3], submitted a solution, and is accepted
        wp3 = workshops[3].participants.create(camp_participation=cp, qualification_result=7.5)
        Solution.objects.create(workshop_participant=wp3)
        # the user is participating in workshops[4], submitted a solution, and is rejected
        wp4 = workshops[4].participants.create(camp_participation=cp, qualification_result=2.5)
        Solution.objects.create(workshop_participant=wp4)

        # Test the count methods
        with self.assertNumQueries(4):  # SELECT FROM CampParticipant, WorkshopParticipant, Workshop, Solution
            cp = CampParticipant.objects.prefetch_related('workshop_participation', 'workshop_participation__workshop', 'workshop_participation__solution').get(pk=cp.pk)
            self.assertEqual(cp.workshop_count, 4)
            self.assertEqual(cp.accepted_workshop_count, 1)
            self.assertEqual(cp.to_be_checked_solution_count, 4)
            self.assertEqual(cp.checked_solution_count, 2)
            self.assertEqual(cp.solution_count, 0)
            self.assertEqual(cp.checked_solution_percentage, 50)
            self.assertEqual(cp.result_in_percent, 100)

    def test_counts_not_qualifying(self):
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            is_qualifying=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        wp = workshop.participants.create(camp_participation=cp)

        # Test the count methods
        with self.assertNumQueries(4):  # SELECT FROM CampParticipant, WorkshopParticipant, Workshop, Solution
            cp = CampParticipant.objects.prefetch_related('workshop_participation', 'workshop_participation__workshop', 'workshop_participation__solution').get(pk=cp.pk)
            self.assertEqual(cp.workshop_count, 1)
            self.assertEqual(cp.accepted_workshop_count, 0)
            self.assertEqual(cp.to_be_checked_solution_count, 0)
            self.assertEqual(cp.checked_solution_count, 0)
            self.assertEqual(cp.solution_count, 0)
            self.assertEqual(cp.checked_solution_percentage, -1)
            self.assertEqual(cp.result_in_percent, 0)

    def test_counts_qualification_disabled_later(self):
        # Test an edge case where the qualification was disabled after some scores were already entered
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5,
            is_qualifying=False
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        wp = workshop.participants.create(camp_participation=cp, qualification_result=7.5)

        # Test the count methods
        with self.assertNumQueries(4):  # SELECT FROM CampParticipant, WorkshopParticipant, Workshop, Solution
            cp = CampParticipant.objects.prefetch_related('workshop_participation', 'workshop_participation__workshop', 'workshop_participation__solution').get(pk=cp.pk)
            self.assertEqual(cp.workshop_count, 1)
            self.assertEqual(cp.accepted_workshop_count, 0)
            self.assertEqual(cp.to_be_checked_solution_count, 0)
            self.assertEqual(cp.checked_solution_count, 0)
            self.assertEqual(cp.solution_count, 0)
            self.assertEqual(cp.checked_solution_percentage, -1)
            self.assertEqual(cp.result_in_percent, 0)

    def test_counts_non_prefetched_exception(self):
        # Make sure that trying to access count methods without prefetching results in an error
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        wp = workshop.participants.create(camp_participation=cp, qualification_result=7.5)

        # Test the count methods
        with self.assertNumQueries(1):  # SELECT FROM CampParticipant
            cp = CampParticipant.objects.get(pk=cp.pk)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation before using the count methods', lambda: cp.workshop_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation before using the count methods', lambda: cp.accepted_workshop_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation before using the count methods', lambda: cp.to_be_checked_solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation before using the count methods', lambda: cp.checked_solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation before using the count methods', lambda: cp.solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation before using the count methods', lambda: cp.checked_solution_percentage)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation before using the count methods', lambda: cp.result_in_percent)

    def test_counts_non_prefetched_workshop_exception(self):
        # Make sure that trying to access count methods without prefetching results in an error
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        wp = workshop.participants.create(camp_participation=cp, qualification_result=7.5)

        # Test the count methods
        with self.assertNumQueries(2):  # SELECT FROM CampParticipant, WorkshopParticipant
            cp = CampParticipant.objects.prefetch_related('workshop_participation').get(pk=cp.pk)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__workshop before using the count methods', lambda: cp.workshop_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__workshop before using the count methods', lambda: cp.accepted_workshop_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__workshop before using the count methods', lambda: cp.to_be_checked_solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__workshop before using the count methods', lambda: cp.checked_solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__workshop before using the count methods', lambda: cp.solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__workshop before using the count methods', lambda: cp.checked_solution_percentage)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__workshop before using the count methods', lambda: cp.result_in_percent)

    def test_counts_non_prefetched_solution_exception(self):
        # Make sure that trying to access count methods without prefetching results in an error
        workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='Type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            page_content='<p>Testowa strona</p>',
            page_content_is_public=True,
            max_points=10,
            qualification_threshold=5
        )
        workshop.lecturer.add(self.admin_user.user_profile)
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='Category'))

        cp = self.year_2020.participants.create(user_profile=self.user.user_profile)

        wp = workshop.participants.create(camp_participation=cp, qualification_result=7.5)

        # Test the count methods
        with self.assertNumQueries(3):  # SELECT FROM CampParticipant, WorkshopParticipant, Workshop
            cp = CampParticipant.objects.prefetch_related('workshop_participation', 'workshop_participation__workshop').get(pk=cp.pk)
            self.assertEqual(cp.workshop_count, 1)
            self.assertEqual(cp.accepted_workshop_count, 1)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__solution before using the count methods', lambda: cp.to_be_checked_solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__solution before using the count methods', lambda: cp.checked_solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__solution before using the count methods', lambda: cp.solution_count)
            self.assertRaisesMessage(AttributeError, 'Please prefetch workshop_participation__solution before using the count methods', lambda: cp.checked_solution_percentage)
            self.assertEqual(cp.result_in_percent, 75)
