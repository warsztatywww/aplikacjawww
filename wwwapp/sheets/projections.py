"""Canonical administration-table projections for Django and Google Sheets."""

from dataclasses import dataclass
from typing import Optional, Tuple

from django.urls import reverse
from django.db.models import Prefetch

from wwwapp.models import Camp, UserProfile, Workshop
from wwwforms.models import FormQuestionAnswer


@dataclass(frozen=True)
class TableColumn:
    header: str


@dataclass(frozen=True)
class TableCell:
    value: object
    url: Optional[str] = None


@dataclass(frozen=True)
class TableProjection:
    columns: Tuple[TableColumn, ...]
    rows: Tuple[Tuple[TableCell, ...], ...]


def participant_projection(camp):
    """Return the participant table, excluding accepted lecturers."""
    participation_queryset = camp.participants.prefetch_related(
        'workshop_participation__solution', 'workshop_participation__workshop')
    participants = UserProfile.objects.filter(camp_participation__year=camp).exclude(
        lecturer_workshops__in=Workshop.objects.filter(
            year=camp, status=Workshop.STATUS_ACCEPTED)).select_related('user').prefetch_related(
                Prefetch('camp_participation', queryset=participation_queryset)).distinct()
    questions = _questions(camp)
    columns = _person_columns(questions, include_participation=True)
    rows = tuple(_person_row(profile, camp, questions, True) for profile in participants)
    return TableProjection(columns, rows)


def lecturer_projection(camp):
    """Return accepted lecturers and their accepted workshops."""
    profiles = UserProfile.objects.filter(
        lecturer_workshops__year=camp,
        lecturer_workshops__status=Workshop.STATUS_ACCEPTED,
    ).select_related('user').distinct()
    columns = (TableColumn('Imię i nazwisko'), TableColumn('Email'),
               TableColumn('Warsztaty'))
    rows = []
    for profile in profiles:
        workshops = profile.lecturer_workshops.filter(
            year=camp, status=Workshop.STATUS_ACCEPTED).order_by('title')
        rows.append((
            _profile_cell(profile),
            TableCell(profile.user.email),
            TableCell(', '.join(workshop.title for workshop in workshops)),
        ))
    return TableProjection(columns, tuple(rows))


def workshop_projection(camp):
    """Return the workshop administration table with its display semantics."""
    workshops = camp.workshops.with_counts().prefetch_related(
        'lecturer__user', 'category', 'type').order_by('title')
    columns = tuple(TableColumn(header) for header in (
        'Warsztaty', 'Prowadzący', 'Kategorie', 'Rodzaj', 'L.zak.', 'L.rozw.',
        'L.spr.rozw.', 'L.zap.', 'Próg?', 'Zadania?', 'Strona?', 'Status'))
    rows = []
    for workshop in workshops:
        visible = workshop.is_publicly_visible()
        qualifying = workshop.is_qualifying
        checked = '-' if not qualifying else '%s / %s' % (
            workshop.checked_solution_count, workshop.to_be_checked_solution_count)
        rows.append((
            TableCell(workshop.title, reverse('workshop_edit', args=[camp.pk, workshop.name])),
            TableCell(', '.join(profile.user.get_full_name() for profile in workshop.lecturer.all())),
            TableCell(', '.join(category.name for category in workshop.category.all())),
            TableCell(workshop.type.name),
            TableCell(workshop.qualified_count if qualifying and visible and workshop.qualification_threshold else '-'),
            TableCell(workshop.solution_count if qualifying and visible and workshop.solution_uploads_enabled and workshop.qualification_problems else '-'),
            TableCell(checked),
            TableCell(workshop.registered_count if visible else '-'),
            TableCell(_yes_no(workshop.qualification_threshold) if qualifying and visible else '-'),
            TableCell(_yes_no(bool(workshop.qualification_problems)) if qualifying and visible else '-'),
            TableCell(_yes_no(workshop.page_content_is_public) if visible else '-'),
            TableCell(workshop.get_status_display() or 'Brak'),
        ))
    return TableProjection(columns, tuple(rows))


def _questions(camp):
    return tuple(question for form in camp.forms.prefetch_related('questions') for question in form.questions.all())


def _person_columns(questions, include_participation):
    headers = ['Imię i nazwisko', 'Pełnoletni', 'Płeć', 'Email', 'Szkoła', 'Rok Matury']
    if include_participation:
        headers += ['Punkty', 'L.zap.', 'L.rozw.', 'L.spr.rozw.', 'L.zak.', 'List?', 'Status']
    headers += ['Skąd wiesz o WWW?']
    seen = {}
    for question in questions:
        base = '%s: %s' % (question.form.title, question.title)
        seen[base] = seen.get(base, 0) + 1
        headers.append(base if seen[base] == 1 else '%s (%s)' % (base, seen[base]))
    return tuple(TableColumn(header) for header in headers)


def _person_row(profile, camp, questions, include_participation):
    participation = next((item for item in profile.camp_participation.all()
                          if item.year_id == camp.pk), None)
    birth = _birth_date(camp, profile)
    adult = '-' if birth is None else _yes_no(camp.start_date >= birth.replace(year=birth.year + 18))
    values = [_profile_cell(profile), TableCell(adult), TableCell(profile.get_gender_display()),
              TableCell(profile.user.email), TableCell(profile.school),
              TableCell(profile.matura_exam_year or '')]
    if include_participation:
        values += [TableCell(participation.result_in_percent if participation else 0),
                   TableCell(participation.workshop_count if participation else 0),
                   TableCell(participation.solution_count if participation else 0),
                   TableCell('%s / %s' % (participation.checked_solution_count,
                                          participation.to_be_checked_solution_count) if participation else '0 / 0'),
                   TableCell(participation.accepted_workshop_count if participation else 0),
                   TableCell(_yes_no(len(participation.cover_letter) > 50) if participation else '-'),
                   TableCell(participation.get_status_display() if participation and participation.status else 'Brak')]
    values.append(TableCell(profile.how_do_you_know_about))
    answers = {answer.question_id: answer for answer in FormQuestionAnswer.objects.filter(
        user=profile.user, question__in=questions)}
    values.extend(TableCell(answers.get(question.pk).value if question.pk in answers else '') for question in questions)
    return tuple(values)


def _profile_cell(profile):
    return TableCell(profile.user.get_full_name(), reverse('profile', args=[profile.user.pk]))


def _birth_date(camp, profile):
    question = camp.form_question_birth_date
    if not question:
        return None
    answer = FormQuestionAnswer.objects.filter(user=profile.user, question=question).first()
    if not answer:
        return None
    return answer.pesel_extract_date() if question.data_type == 'P' else answer.value_date


def _yes_no(value):
    return 'TAK' if value else 'NIE'
