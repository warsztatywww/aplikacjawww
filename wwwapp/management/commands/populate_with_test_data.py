import django.db.utils
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.text import slugify

from wwwapp.models import UserProfile, Article, ArticleContentHistory, Workshop, \
    WorkshopCategory, \
    WorkshopType, WorkshopParticipant, Camp, CampParticipant, Solution

from typing import Tuple, List, Union, Callable
from faker import Faker
from faker.providers import profile, person, date_time, internet
import datetime
import random
from wwwforms.models import Form, FormQuestion

"""
Command implementing database population. 
Useful for making test fixtures. 
"""


class Command(BaseCommand):
    args = ''
    help = 'Populate the database with data for development'
    LOCALE = 'pl_PL'
    NUM_OF_USERS = 200
    NUM_OF_WORKSHOPS = 40
    NUM_OF_ARTICLES = 2
    NUM_OF_CATEGORIES = 2
    NUM_OF_TYPES = 2

    """
    Constructor of the command
    """

    def __init__(self) -> None:
        fake = Faker(self.LOCALE)
        fake.add_provider(profile)
        fake.add_provider(person)
        fake.add_provider(date_time)
        fake.add_provider(internet)
        self.fake = fake

        super().__init__()

    """
    Create and returns a fake random user.
    """

    def fake_user(self) -> Tuple[User, UserProfile]:
        user = None
        
        while user is None:
            profile_data = self.fake.profile()
            username = profile_data['username']
            
            # Check if the username already exists
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username,
                                              profile_data['mail'],
                                              'password')
                user.first_name = self.fake.first_name()
                user.last_name = self.fake.last_name()
                user.save()

                user.user_profile.gender = profile_data['sex']
                user.user_profile.school = "TEST"
                user.user_profile.matura_exam_year = self.fake.date_this_year().year
                user.user_profile.how_do_you_know_about = self.fake.text()
                user.user_profile.profile_page = self.fake.text()
                user.user_profile.save()

                self.question_pesel.answers.create(user=user,
                                                value_string=profile_data['ssn'])
                self.question_address.answers.create(user=user,
                                                  value_string=profile_data['address'])
                
                # Add participant's phone number
                phone_number = "+48" + self.fake.numerify(text="#########") # Polish number format
                self.question_phone.answers.create(user=user,
                                               value_string=phone_number)
                
                # Add emergency phone number only for some participants (75% of them)
                if random.random() < 0.75:
                    emergency_phone = "+48" + self.fake.numerify(text="#########")
                    self.question_emergency_phone.answers.create(user=user,
                                                   value_string=emergency_phone)
                    
                    # Add description for some emergency phone numbers
                    if random.random() < 0.75:
                        emergency_contacts = ["Mama", "Tata", "Rodzice", "Opiekun", "Babcia", "Dziadek", "Siostra", "Brat"]
                        emergency_desc = self.fake.random_element(emergency_contacts)
                        self.question_emergency_phone_desc.answers.create(user=user,
                                                        value_string=emergency_desc)
                    
                self.question_comments.answers.create(user=user,
                                                   value_string=self.fake.text(100))
                

        return user, user.user_profile

    """
    Returns a zero padded string representation of the given number
    or an empty string if the argument is not present
    """

    @staticmethod
    def tail_for_sequence(sequence: Union[int, None]) -> str:
        if sequence is not None:
            return '{0:04d}'.format(sequence)
        else:
            return ''

    """
    Creates and returns a fake random article with a random edit history
    """

    def fake_article(self, users: List[User],
                     sequence: Union[str, None] = None) -> Article:
        article = Article(
            name=self.fake.uri_page() + self.tail_for_sequence(sequence),
            title=self.fake.text(50),
            content=self.fake.paragraph(),
            modified_by=self.fake.random_choices(users, length=1)[0],
            on_menubar=self.fake.pybool())

        article.save()

        for i in range(2, 4):
            ArticleContentHistory(version=i,
                                  article=article,
                                  content=self.fake.paragraph(),
                                  modified_by=
                                  self.fake.random_choices(users, length=1)[0],
                                  time=self.fake.date_time_this_year()).save()

        return article

    """
    Creates and returns a random category
    """

    def fake_category(self, year: Camp) -> WorkshopCategory:
        c = WorkshopCategory(year=year, name=self.fake.word())
        c.save()
        return c

    """
    Creates and returns a random type
    """

    def fake_type(self, year: Camp) -> WorkshopType:
        c = WorkshopType(year=year, name=self.fake.word())
        c.save()
        return c

    """
    Creates a fake random workshops with 5 random participants
    """

    def fake_workshop(self,
                      lecturers: List[UserProfile],
                      participants: List[UserProfile],
                      types: List[WorkshopType],
                      categories: List[WorkshopCategory],
                      sequence: Union[str, None] = None) -> Workshop:
        workshop_type = self.fake.random_choices(types, length=1)[0]
        title = self.fake.unique.text(50).replace(".", "")
        workshop = Workshop(
            name=slugify(title),
            title=title,
            proposition_description=self.fake.paragraph(),
            type=workshop_type,
            year=workshop_type.year,
            status=self.fake.random_choices(['Z', 'O', 'X', None], length=1)[0],
            page_content=self.fake.paragraph(),
            page_content_is_public=self.fake.boolean(chance_of_getting_true=80),
            is_qualifying=self.fake.boolean(chance_of_getting_true=70),
            short_description=self.fake.text(150) if self.fake.boolean(
                chance_of_getting_true=80) else ""
        )
        workshop.save()

        for participant in participants:
            camp_participant, _ = CampParticipant.objects.get_or_create(
                year=workshop.year, user_profile=participant)
            info = WorkshopParticipant(workshop=workshop,
                                       camp_participation=camp_participant,
                                       comment=self.fake.paragraph())
            info.save()

        for el in self.fake.random_choices(categories,
                                           length=self.fake.random_int(1, 4)):
            workshop.category.add(el)
        
        for lecturer in lecturers:
            workshop.lecturer.add(lecturer)
        workshop.save()

        return workshop

    def make_userinfo_form(self) -> None:
        self.form_userinfo, _ = Form.objects.get_or_create(name='user_info',
                                                           title='Informacje wyjazdowe',
                                                           description='Te informacje będą nam potrzebne dopiero, gdy zostaniesz zakwalifikowany na warsztaty.')
        self.question_pesel, _ = self.form_userinfo.questions.get_or_create(
            title='PESEL',
            data_type=FormQuestion.TYPE_PESEL,
            is_required=True,
            order=0)
        self.question_address, _ = self.form_userinfo.questions.get_or_create(
            title='Adres zameldowania', data_type=FormQuestion.TYPE_TEXTBOX,
            is_required=True, order=1)
        self.question_phone, _ = self.form_userinfo.questions.get_or_create(
            title='Numer telefonu do Ciebie', data_type=FormQuestion.TYPE_PHONE,
            is_required=True, order=2)
        self.question_emergency_phone, _ = self.form_userinfo.questions.get_or_create(
            title='Numer telefonu w sytuacjach awaryjnych (np. do rodziców)', data_type=FormQuestion.TYPE_PHONE,
            is_required=True, order=3)
        self.question_emergency_phone_desc, _ = self.form_userinfo.questions.get_or_create(
            title='Do kogo jest powyższy numer?', data_type=FormQuestion.TYPE_STRING,
            is_required=True, order=4)
        self.question_start_date, _ = self.form_userinfo.questions.get_or_create(
            title='Data przyjazdu :-)', data_type=FormQuestion.TYPE_DATE,
            is_required=True, order=5)
        self.question_end_date, _ = self.form_userinfo.questions.get_or_create(
            title='Data wyjazdu :-(', data_type=FormQuestion.TYPE_DATE,
            is_required=True, order=6)
        self.question_tshirt_size, _ = self.form_userinfo.questions.get_or_create(
            title='Rozmiar koszulki', data_type=FormQuestion.TYPE_SELECT,
            is_required=False, order=7)
        self.tshirt_sizes = {}
        for size in ['XS', 'S', 'M', 'L', 'XL', 'XXL']:
            self.tshirt_sizes[
                size], _ = self.question_tshirt_size.options.get_or_create(
                title=size)
        self.question_comments, _ = self.form_userinfo.questions.get_or_create(
            title='Dodatkowe uwagi (np. wegetarianin, uczulony na X, ale też inne)',
            data_type=FormQuestion.TYPE_TEXTBOX, is_required=False, order=8)
        self.form_userinfo.save()

    def do_ignore_integrity_error(self, task: Callable[[], None]) -> None:
        try:
            task()
        except django.db.utils.IntegrityError:
            pass

    """
    Handles the command
    """

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            print("Command not allowed in production")
            return

        self.make_userinfo_form()

        self.do_ignore_integrity_error(
            lambda: User.objects.create_superuser("admin", "admin@admin.admin",
                                                  "admin"))

        users = []
        user_profiles = []
        for i in range(self.NUM_OF_USERS):
            (user, user_profile) = self.fake_user()
            users.append(user)
            user_profiles.append(user_profile)

        articles = []
        for i in range(self.NUM_OF_ARTICLES):
            articles.append(self.fake_article(users, i))

        # Adding default years for start and end of camp
        current_date = datetime.date.today()

        if current_date.month < 7:
            target_year = current_date.year
        else:
            target_year = current_date.year + 1

        year, created = Camp.objects.get_or_create(year=target_year)
        year.start_date = datetime.datetime(year.year, 7, 1)
        year.end_date = datetime.datetime(year.year, 8, 1)
        year.save()
        year.forms.add(self.form_userinfo)
        year.form_question_arrival_date = self.question_start_date
        year.form_question_departure_date = self.question_end_date
        year.save()

        types = []
        for i in range(self.NUM_OF_TYPES):
            types.append(self.fake_type(year))

        categories = []
        for i in range(self.NUM_OF_CATEGORIES):
            categories.append(self.fake_category(year))

        lecturers = user_profiles[:self.NUM_OF_WORKSHOPS // 2]  # Use fewer lecturers to ensure some get multiple workshops
        participants = user_profiles[self.NUM_OF_WORKSHOPS // 2:]
        participants_per_workshop = len(participants) // self.NUM_OF_WORKSHOPS
        participants = [participants[
                        participants_per_workshop * i:participants_per_workshop * (
                                i + 1)]
                        for i in range(self.NUM_OF_WORKSHOPS)]

        workshops = []
        for i in range(self.NUM_OF_WORKSHOPS):
            # Randomly select 1-2 lecturers for each workshop
            workshop_lecturers = self.fake.random_choices(lecturers, length=self.fake.random_int(1, 2))
            workshop_participants = participants[i]
            workshops.append(
                self.fake_workshop(workshop_lecturers, workshop_participants, types, categories, i))

        # Get all WorkshopParticipant objects for the created year
        wps = WorkshopParticipant.objects.filter(workshop__year=year)
        
        # Pick a random subset (e.g., 30%) to submit solutions
        for wp in wps:
            if wp.workshop.is_qualifying and wp.workshop.solution_uploads_enabled:
                if random.random() < 0.3:  # 30% chance
                    # Only add if not already present
                    if not hasattr(wp, 'solution'):
                        Solution.objects.create(workshop_participant=wp, message="Testowa odpowiedź na zadanie.")
