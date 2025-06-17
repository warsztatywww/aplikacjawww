import django.db.utils
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.text import slugify

from wwwapp.models import UserProfile, Article, ArticleContentHistory, Workshop, \
    WorkshopCategory, \
    WorkshopType, WorkshopParticipant, Camp, CampParticipant, Solution

from typing import Tuple, List, Union, Callable, Dict
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
    NUM_OF_WORKSHOPS_CURRENT = 40  # Current year workshops
    NUM_OF_WORKSHOPS_PREVIOUS = 20  # Previous year workshops
    NUM_OF_WORKSHOPS_OLDEST = 10  # Oldest year workshops
    NUM_OF_ARTICLES = 2
    NUM_OF_CATEGORIES = 2
    NUM_OF_TYPES = 2
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output messages',
        )

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
        self.quiet = False

        super().__init__()

    def debug_print(self, message):
        """Print debug messages if not in quiet mode"""
        if not self.quiet:
            print(message)

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
                # Polish number format
                phone_number = "+48" + self.fake.numerify(text="#########")
                self.question_phone.answers.create(user=user,
                                                   value_string=phone_number)

                # Add emergency phone number only for some participants (75% of them)
                if random.random() < 0.75:
                    emergency_phone = "+48" + \
                        self.fake.numerify(text="#########")
                    self.question_emergency_phone.answers.create(user=user,
                                                                 value_string=emergency_phone)

                    # Add description for some emergency phone numbers
                    if random.random() < 0.75:
                        emergency_contacts = [
                            "Mama", "Tata", "Rodzice", "Opiekun", "Babcia", "Dziadek", "Siostra", "Brat"]
                        emergency_desc = self.fake.random_element(
                            emergency_contacts)
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
                     sequence: int) -> Article:
        article = Article(
            name=self.fake.unique.uri_page() + self.tail_for_sequence(sequence),
            title=self.fake.text(50),
            content=self.fake.paragraph(),
            modified_by=self.fake.random_choices(users, length=1)[0],
            on_menubar=self.fake.pybool())

        article.save()

        for i in range(2, 4):
            ArticleContentHistory(version=i,
                                  article=article,
                                  content=self.fake.paragraph(),
                                  modified_by=self.fake.random_choices(
                                      users, length=1)[0],
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
            status=self.fake.random_choices(
                ['Z', 'O', 'X', None], length=1)[0],
            page_content=self.fake.paragraph(),
            page_content_is_public=self.fake.boolean(
                chance_of_getting_true=80),
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

    def _setup_camp(self, year_number: int) -> Camp:
        """
        Create and configure a Camp object for the given year
        """
        camp, _ = Camp.objects.get_or_create(year=year_number)
        camp.start_date = datetime.datetime(year_number, 7, 1)
        camp.end_date = datetime.datetime(year_number, 8, 1)
        camp.save()
        camp.forms.add(self.form_userinfo)
        camp.form_question_arrival_date = self.question_start_date
        camp.form_question_departure_date = self.question_end_date
        camp.save()
        return camp

    def _create_workshop_metadata(self, camp: Camp) -> Tuple[List[WorkshopType], List[WorkshopCategory]]:
        """
        Create workshop types and categories for a camp year
        """
        types = [self.fake_type(camp) for _ in range(self.NUM_OF_TYPES)]
        categories = [self.fake_category(camp)
                      for _ in range(self.NUM_OF_CATEGORIES)]
        return types, categories

    def _select_camp_participants(self, user_profiles: List[UserProfile]) -> List[UserProfile]:
        """
        Select 50% of users to participate in this camp year
        """
        # Randomly select 50% of all users for this camp
        return random.sample(user_profiles, k=len(user_profiles) // 2)

    def _generate_cover_letter(self) -> str:
        """
        Generate a cover letter for a camp participant using Faker
        """
        # Generate 1-3 paragraphs for the cover letter
        num_paragraphs = random.randint(1, 3)
        paragraphs = [self.fake.paragraph() for _ in range(num_paragraphs)]

        # Join paragraphs with newlines
        return "\n\n".join(paragraphs)

    def _create_camp_participants(self, camp: Camp, selected_profiles: List[UserProfile]) -> Dict[UserProfile, CampParticipant]:
        """
        Create CampParticipant objects for the selected user profiles
        """
        camp_participants = {}
        cover_letter_count = 0

        for i, profile in enumerate(selected_profiles):
            if i > 0 and i % 50 == 0:
                self.debug_print(
                    f"    Created {i}/{len(selected_profiles)} camp participants...")

            # Create camp participant with 80% chance of having a cover letter
            has_cover_letter = random.random() < 0.8
            if has_cover_letter:
                cover_letter_count += 1
                cover_letter = self._generate_cover_letter()
            else:
                cover_letter = ""

            camp_participant, created = CampParticipant.objects.get_or_create(
                year=camp,
                user_profile=profile,
                defaults={'cover_letter': cover_letter}
            )

            # If not created now but exists from before, maybe update the cover letter
            if not created and has_cover_letter and not camp_participant.cover_letter:
                camp_participant.cover_letter = cover_letter
                camp_participant.save()

            camp_participants[profile] = camp_participant

        self.debug_print(
            f"    Created {len(camp_participants)} camp participants ({cover_letter_count} with cover letters)")
        return camp_participants

    def _assign_random_workshops(self, camp: Camp, camp_participants: Dict[UserProfile, CampParticipant],
                                 num_workshops: int, types: List[WorkshopType], categories: List[WorkshopCategory]) -> List[Workshop]:
        """
        Create workshops and randomly assign participants and lecturers
        """
        workshops = []
        profiles = list(camp_participants.keys())

        # Divide profiles into potential lecturers and participants
        # Anyone can be a lecturer or participant for different workshops
        # All profiles can potentially be lecturers
        potential_lecturers = profiles.copy()
        self.debug_print(
            f"    Found {len(profiles)} potential participants for workshops")

        for workshop_index in range(num_workshops):
            if workshop_index > 0 and workshop_index % 10 == 0:
                self.debug_print(
                    f"    Created {workshop_index}/{num_workshops} workshops...")

            # For each workshop, randomly select 1-2 lecturers
            if potential_lecturers:
                num_lecturers = min(random.randint(
                    1, 2), len(potential_lecturers))
                workshop_lecturers = random.sample(
                    potential_lecturers, num_lecturers)
            else:
                # Fallback if we somehow ran out of lecturers
                workshop_lecturers = random.sample(
                    profiles, min(2, len(profiles)))

            # Exclude the lecturers from being participants in their own workshop
            potential_participants = [
                p for p in profiles if p not in workshop_lecturers]

            # Randomly determine how many participants for this workshop (3-15)
            num_participants = min(random.randint(
                3, 15), len(potential_participants))

            # Randomly select participants for this workshop
            workshop_participants = random.sample(
                potential_participants, num_participants) if potential_participants else []

            # Create unique workshop name with year prefix
            workshop_name = f"{camp.year}-{workshop_index}"

            # Create the workshop
            try:
                workshop = self.fake_workshop(
                    workshop_lecturers, workshop_participants, types, categories, workshop_name)
                workshops.append(workshop)
            except django.db.utils.IntegrityError as e:
                self.debug_print(
                    f"    Error creating workshop {workshop_name}: {e}")

        self.debug_print(
            f"    Successfully created {len(workshops)} workshops for year {camp.year}")
        return workshops

    def _assign_participant_statuses(self, camp: Camp, is_past_year: bool) -> None:
        """
        Assign statuses to camp participants for past years
        """
        if not is_past_year:
            return

        # Get all CampParticipants for this year
        camp_participants = CampParticipant.objects.filter(year=camp)
        self.debug_print(
            f"    Assigning statuses to {camp_participants.count()} participants for year {camp.year}")

        # Status distribution weights - more acceptances than rejections
        status_weights = {
            CampParticipant.STATUS_ACCEPTED: 0.7,  # 70% accepted
            CampParticipant.STATUS_REJECTED: 0.2,  # 20% rejected
            CampParticipant.STATUS_CANCELLED: 0.1   # 10% cancelled
        }

        statuses = list(status_weights.keys())
        weights = list(status_weights.values())
        status_counts = {status: 0 for status in statuses}

        for cp in camp_participants:
            # Assign a random non-None status based on weights
            assigned_status = random.choices(statuses, weights=weights, k=1)[0]
            cp.status = assigned_status
            cp.save()
            status_counts[assigned_status] += 1

        self.debug_print(
            f"    Status assignment complete: {status_counts}")

    def _add_solutions_and_results(self, camp: Camp, is_past_year: bool) -> None:
        """
        Add solutions and qualification results for workshop participants
        """
        # Get all workshop participants for this year
        wps = WorkshopParticipant.objects.filter(workshop__year=camp)
        self.debug_print(
            f"    Adding solutions for {wps.count()} workshop participants in year {camp.year}")

        # Sample solution messages for variety
        solution_messages = [
            "Testowa odpowiedź na zadanie.",
            "Moje rozwiązanie zadania kwalifikacyjnego.",
            "Przesyłam rozwiązanie, mam nadzieję że jest poprawne.",
            "Rozwiązałem/am to w następujący sposób...",
            "Proszę o sprawdzenie mojego rozwiązania."
        ]

        solutions_added = 0
        results_added = 0

        for wp in wps:
            if wp.workshop.is_qualifying and wp.workshop.solution_uploads_enabled:
                # Higher chance of solutions for past years
                solution_chance = 0.8 if is_past_year else 0.5

                if random.random() < solution_chance:
                    # Only add if not already present
                    if not hasattr(wp, 'solution'):
                        message = random.choice(solution_messages)
                        Solution.objects.create(
                            workshop_participant=wp, message=message)
                        solutions_added += 1

                    # For past years, add qualification results to most solutions
                    if is_past_year and random.random() < 0.9:  # 90% chance for past years
                        # More realistic distribution of scores
                        if random.random() < 0.7:  # 70% get higher scores
                            wp.qualification_result = round(
                                random.uniform(60, 100), 2)
                        else:  # 30% get lower scores
                            wp.qualification_result = round(
                                random.uniform(0, 59), 2)
                        wp.save()
                        results_added += 1

        self.debug_print(
            f"    Added {solutions_added} solutions and {results_added} qualification results")

    def create_camp_year(self, year_number: int, num_workshops: int, users: List[User], user_profiles: List[UserProfile]) -> Tuple[Camp, List[Workshop]]:
        """
        Create a camp year with workshops, categories, and types
        """
        # Setup the camp object
        self.debug_print(f"  Setting up camp for year {year_number}...")
        camp = self._setup_camp(year_number)

        # Create workshop types and categories
        self.debug_print(
            f"  Creating workshop metadata for year {year_number}...")
        types, categories = self._create_workshop_metadata(camp)

        # Select 50% of users to participate in this camp
        self.debug_print(f"  Selecting participants for year {year_number}...")
        selected_profiles = self._select_camp_participants(user_profiles)
        self.debug_print(
            f"  Selected {len(selected_profiles)} participants for year {year_number}")

        # Create camp participants with cover letters
        self.debug_print(f"  Creating camp participants with cover letters...")
        camp_participants = self._create_camp_participants(
            camp, selected_profiles)

        # Create workshops with randomly assigned lecturers and participants
        self.debug_print(
            f"  Creating {num_workshops} workshops with random assignments for year {year_number}...")
        workshops = self._assign_random_workshops(
            camp, camp_participants, num_workshops, types, categories)

        # Determine if this is a past year
        is_past_year = year_number < datetime.date.today().year

        # Assign statuses to camp participants for past years
        if is_past_year:
            self.debug_print(
                f"  Assigning statuses to participants for past year {year_number}...")
            self._assign_participant_statuses(camp, is_past_year)

        # Add solutions and qualification results
        self.debug_print(f"  Adding solutions and qualification results...")
        self._add_solutions_and_results(camp, is_past_year)

        return camp, workshops

    def handle(self, *args, **options) -> None:
        # Set quiet mode from options
        self.quiet = options.get('quiet', False)

        if not settings.DEBUG:
            print("Command not allowed in production")
            return

        self.debug_print("Initializing userinfo form...")
        self.make_userinfo_form()

        self.debug_print("Creating admin user...")
        self.do_ignore_integrity_error(
            lambda: User.objects.create_superuser("admin", "admin@admin.admin",
                                                  "admin"))

        self.debug_print(f"Creating {self.NUM_OF_USERS} fake users...")
        users = []
        user_profiles = []
        for i in range(self.NUM_OF_USERS):
            if i > 0 and i % 50 == 0:
                self.debug_print(f"Created {i}/{self.NUM_OF_USERS} users...")
            (user, user_profile) = self.fake_user()
            users.append(user)
            user_profiles.append(user_profile)
        self.debug_print(f"Created all {self.NUM_OF_USERS} users successfully")

        self.debug_print(f"Creating {self.NUM_OF_ARTICLES} articles...")
        articles = []
        previously_existing_articles = Article.objects.count()
        for i in range(previously_existing_articles, previously_existing_articles + self.NUM_OF_ARTICLES):
            articles.append(self.fake_article(users, i))
        self.debug_print("Articles created successfully")

        # Calculate years for camps
        current_date = datetime.date.today()
        if current_date.month < 7:
            current_year = current_date.year
        else:
            current_year = current_date.year + 1

        # Create 3 camp years: current, previous, and oldest
        camp_years = [
            (current_year, self.NUM_OF_WORKSHOPS_CURRENT),
            (current_year - 1, self.NUM_OF_WORKSHOPS_PREVIOUS),
            (current_year - 2, self.NUM_OF_WORKSHOPS_OLDEST)
        ]

        self.debug_print("Starting camp creation process...")
        all_workshops = []
        for year_number, num_workshops in camp_years:
            self.debug_print(
                f"Creating camp for year {year_number} with {num_workshops} workshops...")
            _, workshops = self.create_camp_year(
                year_number, num_workshops, users, user_profiles)
            all_workshops.extend(workshops)
            self.debug_print(
                f"Completed camp for year {year_number} with {len(workshops)} workshops")

        self.debug_print(
            f"Data population complete. Created {len(all_workshops)} total workshops across {len(camp_years)} years.")
        self.debug_print(
            f"User count: {User.objects.count()}, Workshop count: {Workshop.objects.count()}")
