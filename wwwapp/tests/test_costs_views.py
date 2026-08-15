import csv
import io
import os
import zipfile
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse
from freezegun import freeze_time

from wwwapp.forms import (
    CostItemForm,
    CostItemFormSet,
    InvoiceForm,
    ReimbursementForm,
    SettlementDetailsForm,
)
from wwwapp.models import (
    Camp,
    CostItem,
    Invoice,
    Reimbursement,
    SettlementDetails,
    UploadStorage,
    Workshop,
    WorkshopType,
)


CSV_HEADER = [
    'internal_number', 'document_number', 'issue_date', 'user', 'invoice_type', 'status',
    'invoice_amount', 'category', 'workshop', 'item_amount',
    'description',
]


class InvoiceFormTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2027)
        self.user = User.objects.create_user(username='user')
        self.invoice = Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            attachment='invoices/existing.pdf',
            document_number='FV/1/2026',
            issue_date='2026-07-24',
            amount=Decimal('10.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Workshop materials',
            internal_number='WWW_2026_K_0001',
        )
        workshop_type = WorkshopType.objects.create(year=self.camp, name='Type')
        self.workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='workshop',
            title='Workshop',
        )
        other_type = WorkshopType.objects.create(year=self.other_camp, name='Other type')
        self.other_workshop = Workshop.objects.create(
            year=self.other_camp,
            type=other_type,
            name='other-workshop',
            title='Other workshop',
        )
        self.data = {
            'document_number': 'FV/2/2026',
            'issue_date': '2026-07-24',
            'amount': '10.00',
            'invoice_type': Invoice.Type.KSEF,
            'description': 'Workshop materials',
        }
        self.split_post = {
            'cost_items-TOTAL_FORMS': '2',
            'cost_items-INITIAL_FORMS': '0',
            'cost_items-MIN_NUM_FORMS': '0',
            'cost_items-MAX_NUM_FORMS': '1000',
            'cost_items-0-workshop': str(self.workshop.pk),
            'cost_items-0-amount': '4.00',
            'cost_items-0-category': CostItem.Category.WORKSHOPS,
            'cost_items-1-workshop': '',
            'cost_items-1-amount': '5.99',
            'cost_items-1-category': CostItem.Category.REGULAR_PURCHASES,
        }

    def test_attachment_rejects_non_pdf_content_even_with_a_pdf_filename(self):
        form = InvoiceForm(
            data=self.data,
            files={
                'attachment': SimpleUploadedFile(
                    'invoice.pdf', b'not a document', content_type='application/pdf'
                )
            },
            user=self.user,
            camp=self.camp,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)

    def test_attachment_accepts_pdf_jpeg_and_png_signatures(self):
        for name, content, content_type in (
            ('invoice.pdf', b'%PDF-1.7', 'application/pdf'),
            ('invoice.jpeg', b'\xff\xd8\xff\xe0', 'image/jpeg'),
            ('invoice.png', b'\x89PNG\r\n\x1a\n', 'image/png'),
        ):
            with self.subTest(name=name):
                form = InvoiceForm(
                    data=self.data,
                    files={
                        'attachment': SimpleUploadedFile(name, content, content_type=content_type)
                    },
                    user=self.user,
                    camp=self.camp,
                )

                self.assertTrue(form.is_valid(), form.errors)

    def test_attachment_rejects_unrecognized_or_oversize_uploads(self):
        cases = (
            ('invoice.pdf', b'plain text without a signature', 'application/pdf'),
            ('invoice.pdf', b'%PDF-' + b'x' * (50 * 1024 * 1024), 'application/pdf'),
        )
        for name, content, content_type in cases:
            with self.subTest(name=name, content_type=content_type):
                form = InvoiceForm(
                    data=self.data,
                    files={
                        'attachment': SimpleUploadedFile(name, content, content_type=content_type)
                    },
                    user=self.user,
                    camp=self.camp,
                )

                self.assertFalse(form.is_valid())
                self.assertIn('attachment', form.errors)

    def test_numbered_invoice_type_cannot_be_changed(self):
        form = InvoiceForm(
            data={**self.data, 'invoice_type': Invoice.Type.NON_ACCOUNTING_RECEIPT},
            instance=self.invoice,
            user=self.user,
            camp=self.camp,
        )

        self.assertTrue(form.is_valid())
        invoice = form.save()
        self.assertEqual(invoice.invoice_type, Invoice.Type.KSEF)

    def test_cost_item_formset_rejects_unequal_total(self):
        formset = CostItemFormSet(
            self.split_post,
            instance=self.invoice,
            invoice_amount=Decimal('10.00'),
        )

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_cost_item_formset_accepts_a_complete_allocation(self):
        formset = CostItemFormSet(
            self.split_post,
            instance=self.invoice,
            invoice_amount=Decimal('9.99'),
        )

        self.assertTrue(formset.is_valid(), formset.non_form_errors())

    def test_cost_item_formset_requires_a_non_deleted_row(self):
        data = {
            **self.split_post,
            'cost_items-0-DELETE': 'on',
            'cost_items-1-DELETE': 'on',
        }
        formset = CostItemFormSet(data, instance=self.invoice)

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_cost_item_formset_rejects_workshop_from_another_camp(self):
        data = {
            **self.split_post,
            'cost_items-0-workshop': str(self.other_workshop.pk),
            'cost_items-0-amount': '10.00',
            'cost_items-1-DELETE': 'on',
        }
        formset = CostItemFormSet(data, instance=self.invoice)

        self.assertFalse(formset.is_valid())
        self.assertIn('workshop', formset.forms[0].errors)


class SettlementAndReimbursementFormTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.user = User.objects.create_user(username='user')
        self.registered_by = User.objects.create_user(username='admin')

    def test_settlement_details_form_is_scoped_to_user_and_camp(self):
        form = SettlementDetailsForm(
            data={'account_number': 'PL61109010140000071219812874'},
            user=self.user,
            camp=self.camp,
        )

        self.assertEqual(form.instance.user, self.user)
        self.assertEqual(form.instance.camp, self.camp)
        self.assertTrue(form.is_valid(), form.errors)
        details = form.save()
        self.assertEqual(details.user, self.user)
        self.assertEqual(details.camp, self.camp)

    def test_reimbursement_form_sets_the_registration_context(self):
        form = ReimbursementForm(
            data={
                'amount': '10.00',
                'type': Reimbursement.Type.ASSOCIATION,
                'comment': 'Transfer',
                'execution_date': '2026-07-24',
            },
            user=self.user,
            camp=self.camp,
            registered_by=self.registered_by,
        )

        self.assertTrue(form.is_valid(), form.errors)
        reimbursement = form.save()
        self.assertEqual(reimbursement.user, self.user)
        self.assertEqual(reimbursement.camp, self.camp)
        self.assertEqual(reimbursement.registered_by, self.registered_by)

    def test_reimbursement_form_uses_polish_labels(self):
        form = ReimbursementForm(
            user=self.user,
            camp=self.camp,
            registered_by=self.registered_by,
        )

        self.assertEqual(
            {name: field.label for name, field in form.fields.items()},
            {
                'amount': 'Kwota',
                'type': 'Typ zwrotu',
                'comment': 'Komentarz',
                'execution_date': 'Data wykonania',
            },
        )

    def test_positive_money_inputs_have_a_minimum_html_value(self):
        invoice_form = InvoiceForm(user=self.user, camp=self.camp)
        reimbursement_form = ReimbursementForm(
            user=self.user,
            camp=self.camp,
            registered_by=self.registered_by,
        )
        cost_item_form = CostItemForm(camp=self.camp)

        for form in (invoice_form, reimbursement_form, cost_item_form):
            with self.subTest(form=form.__class__.__name__):
                self.assertEqual(form.fields['amount'].widget.attrs['min'], '0.01')

    def test_invoice_date_uses_the_standard_date_picker_widget(self):
        form = InvoiceForm(user=self.user, camp=self.camp)

        self.assertEqual(form.fields['issue_date'].widget.input_type, 'text')
        self.assertNotIn('type', form.fields['issue_date'].widget.attrs)

    def test_amount_inputs_use_number_constraints(self):
        form = InvoiceForm(user=self.user, camp=self.camp)

        self.assertEqual(form.fields['amount'].widget.input_type, 'number')
        self.assertEqual(form.fields['amount'].widget.attrs['step'], '0.01')
        self.assertIn('data-amount-input', form.fields['amount'].widget.attrs)

class OwnCostsViewsTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.user = User.objects.create_user(username='user')
        self.other_user = User.objects.create_user(username='other-user')
        self.invoice = Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            attachment='invoices/fv-1.pdf',
            document_number='FV/1/2026',
            issue_date='2026-07-24',
            amount=Decimal('10.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Workshop materials',
            internal_number='WWW_2026_K_0001',
        )

    def invoice_post_data(self, **overrides):
        data = {
            'document_number': 'FV/2/2026',
            'issue_date': '2026-07-24',
            'amount': '10.00',
            'invoice_type': Invoice.Type.KSEF,
            'description': 'Workshop materials',
            'cost_items-TOTAL_FORMS': '1',
            'cost_items-INITIAL_FORMS': '0',
            'cost_items-MIN_NUM_FORMS': '0',
            'cost_items-MAX_NUM_FORMS': '1000',
            'cost_items-0-workshop': '',
            'cost_items-0-amount': '10.00',
            'cost_items-0-category': CostItem.Category.REGULAR_PURCHASES,
        }
        return {**data, **overrides}

    def test_cost_list_shows_own_confirmed_and_pending_totals(self):
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save()
        Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            attachment='invoices/fv-2.pdf',
            document_number='FV/2/2026',
            issue_date='2026-07-24',
            amount=Decimal('4.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Pending invoice',
            internal_number='WWW_2026_K_0002',
        )
        Invoice.objects.create(
            user=self.other_user,
            camp=self.camp,
            attachment='invoices/fv-3.pdf',
            document_number='FV/3/2026',
            issue_date='2026-07-24',
            amount=Decimal('99.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Other user invoice',
            internal_number='WWW_2026_K_0003',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)
        pending_invoice = Invoice.objects.get(internal_number='WWW_2026_K_0002')
        self.assertEqual(list(response.context['invoices']), [pending_invoice, self.invoice])
        self.assertEqual(response.context['approved_total'], Decimal('10.00'))
        self.assertEqual(response.context['reimbursed_total'], Decimal('0.00'))
        self.assertEqual(response.context['remaining_total'], Decimal('10.00'))
        self.assertEqual(response.context['pending_total'], Decimal('4.00'))
        self.assertContains(
            response,
            reverse('costs_invoice_edit', args=[self.camp.pk, pending_invoice.pk]),
        )
        self.assertContains(response, 'Podsumowanie rozliczenia')
        self.assertContains(response, 'id="invoices-heading">Faktury</h2>')
        self.assertContains(response, '4,00 zł')

    def test_cost_list_uses_datatables(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        self.assertContains(response, '<span class="sr-only">Wiersz</span>')
        self.assertContains(response, '<span class="sr-only">Załącznik</span>')
        self.assertContains(response, 'fas fa-download')
        self.assertContains(response, '/static/dist/datatables.css')
        self.assertContains(response, '/static/dist/datatables.js')
        self.assertContains(response, 'data-searchable="false"')
        self.assertContains(response, 'data-visible="false"', count=4)
        for column in ('Opis i pozycje', 'Warsztaty', 'Kategoria', 'Data dodania',
                       'Typ dokumentu'):
            with self.subTest(column=column):
                self.assertContains(response, column)
        self.assertContains(response, 'data-order="')

    def test_invoice_add_requires_settlement_details(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))

        self.assertRedirects(
            response,
            f"{reverse('costs_mine', args=[self.camp.pk])}?add_invoice=1",
        )

    def test_mine_page_saves_account_and_returns_to_invoice_form(self):
        self.client.force_login(self.user)

        response = self.client.post(
            f"{reverse('costs_mine', args=[self.camp.pk])}?add_invoice=1",
            {'account_number': 'PL61109010140000071219812874'},
        )

        self.assertRedirects(response, reverse('costs_invoice_add', args=[self.camp.pk]))
        self.assertEqual(
            SettlementDetails.objects.get(user=self.user, camp=self.camp).account_number,
            'PL61109010140000071219812874',
        )

    def test_mine_page_displays_saved_account_details(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        self.assertContains(response, 'Dane rachunku bankowego')
        self.assertContains(response, 'PL 61 1090 1014 0000 0712 1981 2874')

    def test_invalid_account_edit_keeps_saved_value_and_reveals_errors(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('costs_mine', args=[self.camp.pk]),
            {'account_number': 'PL001234'},
        )

        self.assertContains(response, 'PL 61 1090 1014 0000 0712 1981 2874')
        self.assertContains(response, '<details open>')
        self.assertContains(response, 'Nieprawidłowy format')

    def test_mydata_navigation_shows_own_costs_after_first_invoice(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('mydata_forms'))

        page = response.content.decode()
        self.assertIn(reverse('costs_mine', args=[self.camp.pk]), page)
        self.assertLess(page.index('Formularze'), page.index(reverse('costs_mine', args=[self.camp.pk])))

    def test_mydata_navigation_hides_own_costs_without_an_invoice_or_lecturer_role(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('mydata_forms'))

        self.assertNotContains(response, 'Moje koszty')

    def test_mydata_navigation_shows_own_costs_to_a_lecturer_without_an_invoice(self):
        workshop_type = WorkshopType.objects.create(year=self.camp, name='Lecturer type')
        workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='lecturer-workshop',
            title='Lecturer workshop',
        )
        workshop.lecturer.add(self.other_user.user_profile)
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('mydata_forms'))

        self.assertContains(response, 'Moje koszty')

    def test_own_cost_urls_are_nested_under_the_profile(self):
        self.assertEqual(reverse('costs_mine', args=[self.camp.pk]), f'/me/costs/{self.camp.pk}/')
        self.assertEqual(
            reverse('costs_invoice_add', args=[self.camp.pk]),
            f'/me/costs/{self.camp.pk}/invoices/add/',
        )

    def test_cost_list_uses_the_profile_navigation_shell(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        self.assertTemplateUsed(response, 'mydata_base.html')
        self.assertEqual(response.context['title'], 'Mój profil')
        self.assertContains(response, 'nav-pills')
        self.assertContains(response, 'Moje koszty')

    def test_invoice_add_explains_fields_and_links_back_to_own_costs(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))

        self.assertContains(response, 'Wróć do moich kosztów')
        self.assertContains(response, 'Załącz skan lub plik PDF dokumentu')
        self.assertContains(response, 'Łączna kwota brutto dokumentu')
        self.assertContains(response, 'pozostałej bez przypisania do warsztatu')

    def test_cost_forms_render_polish_labels_and_submit_control(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        invoice_response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))
        settlement_response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        for label in (
            'Załącznik',
            'Numer dokumentu',
            'Data wystawienia',
            'Kwota',
            'Typ dokumentu',
            'Opis',
            'Warsztat',
            'Kategoria',
        ):
            self.assertContains(invoice_response, label)
        self.assertContains(settlement_response, 'Numer rachunku bankowego')
        self.assertContains(settlement_response, 'Zapisz')

    def test_invoice_add_allows_adding_multiple_cost_items(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))

        self.assertContains(response, 'id="cost-item-forms"')
        self.assertContains(response, 'data-sync-invoice-amount')
        self.assertContains(response, 'id="cost-item-empty-form"')
        self.assertContains(response, 'name="cost_items-__prefix__-amount"')
        self.assertContains(response, 'id="add-cost-item"')
        self.assertContains(response, 'class="alert alert-info" id="cost-item-total"')
        self.assertContains(response, 'class="cost-item-form card mb-2"')

    def test_invoice_amount_uses_a_number_input(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))

        self.assertContains(response, 'data-amount-input')
        self.assertContains(response, 'type="number"')

    def test_invoice_add_displays_allocation_errors(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('costs_invoice_add', args=[self.camp.pk]),
            {
                **self.invoice_post_data(**{'cost_items-0-amount': '9.00'}),
                'attachment': SimpleUploadedFile(
                    'invoice.pdf', b'%PDF-1.7', content_type='application/pdf',
                ),
            },
        )

        self.assertContains(response, 'Suma pozycji kosztowych musi być równa kwocie faktury.')

    def test_invoice_add_displays_attachment_error_without_allocation_error(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('costs_invoice_add', args=[self.camp.pk]),
            {
                **self.invoice_post_data(),
                'attachment': SimpleUploadedFile(
                    'invoice.gif', b'GIF89a', content_type='image/gif',
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Załącznik musi być plikiem PDF, JPG, JPEG lub PNG.')
        self.assertNotContains(
            response,
            'Suma pozycji kosztowych musi być równa kwocie faktury.',
        )

    def test_invoice_edit_displays_allocation_error_and_remaining_amount_action(self):
        cost_item = CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('10.00'),
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]),
            self.invoice_post_data(**{
                'cost_items-INITIAL_FORMS': '1',
                'cost_items-0-id': str(cost_item.pk),
                'cost_items-0-amount': '9.00',
            }),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Suma pozycji kosztowych musi być równa kwocie faktury.')
        self.assertContains(response, 'data-fill-remaining-cost-item')

    @freeze_time('2026-08-09 12:34:56.123456')
    def test_invoice_add_creates_unnumbered_invoice_with_internal_attachment_name(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)
        field = Invoice._meta.get_field('attachment')
        original_storage = field.storage

        with TemporaryDirectory() as sendfile_root:
            with override_settings(SENDFILE_ROOT=sendfile_root):
                field.storage = UploadStorage()
                try:
                    response = self.client.post(
                        reverse('costs_invoice_add', args=[self.camp.pk]),
                        {
                            **self.invoice_post_data(),
                            'attachment': SimpleUploadedFile(
                                'invoice.pdf', b'%PDF-1.7', content_type='application/pdf'
                            ),
                        },
                    )
                finally:
                    field.storage = original_storage

                self.assertRedirects(response, reverse('costs_mine', args=[self.camp.pk]))
                invoice = Invoice.objects.get(document_number='FV/2/2026')
                self.assertEqual(invoice.user, self.user)
                self.assertIsNone(invoice.internal_number)
                self.assertEqual(
                    invoice.attachment.name,
                    'invoices/WWW_2026_20260809123456123456.pdf',
                )
                self.assertEqual(invoice.cost_items.get().amount, Decimal('10.00'))

    def test_invoice_add_does_not_allocate_non_accounting_receipt_number(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.post(reverse('costs_invoice_add', args=[self.camp.pk]), {
            **self.invoice_post_data(invoice_type=Invoice.Type.NON_ACCOUNTING_RECEIPT),
            'attachment': SimpleUploadedFile(
                'receipt.pdf', b'%PDF-1.7', content_type='application/pdf'
            ),
        })

        self.assertRedirects(response, reverse('costs_mine', args=[self.camp.pk]))
        invoice = Invoice.objects.get(document_number='FV/2/2026')
        self.assertIsNone(invoice.internal_number)

    def test_rejected_invoice_edit_resets_it_to_received(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.invoice.status = Invoice.Status.REJECTED
        self.invoice.save()
        CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('10.00'),
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]),
            self.invoice_post_data(),
        )

        self.assertRedirects(response, reverse('costs_mine', args=[self.camp.pk]))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.RECEIVED)

    def test_invoice_edit_replaces_an_attachment_with_the_same_filename(self):
        CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('10.00'),
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        self.client.force_login(self.user)
        field = Invoice._meta.get_field('attachment')
        original_storage = field.storage

        with TemporaryDirectory() as sendfile_root:
            with override_settings(SENDFILE_ROOT=sendfile_root):
                test_storage = UploadStorage()
                field.storage = test_storage
                self.invoice.attachment.save(
                    'old.pdf',
                    SimpleUploadedFile('old.pdf', b'%PDF-old', content_type='application/pdf'),
                    save=True,
                )
                old_attachment_path = self.invoice.attachment.path

                try:
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.client.post(
                            reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]),
                            {
                                **self.invoice_post_data(
                                    **{
                                        'cost_items-INITIAL_FORMS': '1',
                                        'cost_items-0-id': self.invoice.cost_items.get().pk,
                                    }
                                ),
                                'attachment': SimpleUploadedFile(
                                    'old.pdf', b'%PDF-new', content_type='application/pdf',
                                ),
                            },
                        )
                finally:
                    field.storage = original_storage

                self.assertRedirects(response, reverse('costs_mine', args=[self.camp.pk]))
                self.invoice.refresh_from_db()
                self.assertNotEqual(self.invoice.attachment.name, 'invoices/old.pdf')
                self.assertFalse(os.path.exists(old_attachment_path))
                with test_storage.open(self.invoice.attachment.name, 'rb') as attachment:
                    self.assertEqual(attachment.read(), b'%PDF-new')

    def test_invoice_edit_is_not_available_to_another_user(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]))

        self.assertEqual(response.status_code, 404)

    def test_invoice_edit_does_not_render_year_switches_without_an_invoice_id(self):
        invoice = Invoice.objects.create(
            user=self.user,
            camp=Camp.objects.create(year=2027),
            attachment='invoices/fv-2027.pdf',
            document_number='FV/1/2027',
            issue_date='2027-07-24',
            amount=Decimal('10.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Workshop materials',
            internal_number='WWW_2027_K_0001',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_edit', args=[invoice.camp_id, invoice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'year-navigation')
        self.assertEqual(response.context['formset'].total_form_count(), 1)

    def test_invoice_add_keeps_the_year_navigation_footer(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'year-navigation')

    def test_approved_and_processed_invoices_cannot_be_edited(self):
        self.client.force_login(self.user)

        for status in (Invoice.Status.APPROVED, Invoice.Status.PROCESSED):
            with self.subTest(status=status):
                self.invoice.status = status
                self.invoice.save()

                response = self.client.get(reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]))

                self.assertEqual(response.status_code, 404)

    @patch('wwwapp.views.sendfile', return_value=HttpResponse())
    def test_owner_can_get_attachment(self, _sendfile_response):
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_attachment', args=[self.camp.pk, self.invoice.pk]))

        self.assertEqual(response.status_code, 200)

    @patch('wwwapp.views.sendfile', return_value=HttpResponse())
    def test_approved_invoice_download_uses_invoice_number(self, sendfile_mock):
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save(update_fields=['status'])
        self.client.force_login(self.user)

        self.client.get(reverse(
            'costs_invoice_attachment',
            args=[self.camp.pk, self.invoice.pk],
        ))

        self.assertEqual(
            sendfile_mock.call_args.kwargs['attachment_filename'],
            'WWW_2026_K_0001.pdf',
        )

    @patch('wwwapp.views.sendfile', return_value=HttpResponse())
    def test_unnumbered_invoice_download_uses_internal_filename(self, sendfile_mock):
        self.invoice.internal_number = None
        self.invoice.attachment = 'invoices/WWW_2026_20260809123456123456.pdf'
        self.invoice.save(update_fields=['internal_number', 'attachment'])
        self.client.force_login(self.user)

        self.client.get(reverse(
            'costs_invoice_attachment',
            args=[self.camp.pk, self.invoice.pk],
        ))

        self.assertEqual(
            sendfile_mock.call_args.kwargs['attachment_filename'],
            'WWW_2026_20260809123456123456.pdf',
        )

    @patch('wwwapp.views.sendfile', return_value=HttpResponse())
    def test_only_all_costs_permission_can_get_another_users_attachment(self, _sendfile_response):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('costs_invoice_attachment', args=[self.camp.pk, self.invoice.pk]))

        self.assertEqual(response.status_code, 404)
        self.other_user.user_permissions.add(Permission.objects.get(codename='view_all_costs'))
        response = self.client.get(reverse('costs_invoice_attachment', args=[self.camp.pk, self.invoice.pk]))
        self.assertEqual(response.status_code, 200)


class CostAdministrationViewsTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2027)
        self.owner = User.objects.create_user(username='cost-owner')
        self.admin = User.objects.create_user(username='cost-admin')
        self.csv_user = User.objects.create_user(username='cost-csv')
        self.process_user = User.objects.create_user(username='cost-process')
        self.approve_permission = Permission.objects.get(codename='approve_costs')
        self.view_permission = Permission.objects.get(codename='view_all_costs')
        self.process_permission = Permission.objects.get(codename='process_costs')
        self.admin.user_permissions.add(self.view_permission, self.approve_permission)
        self.csv_user.user_permissions.add(self.view_permission)
        self.process_user.user_permissions.add(self.view_permission, self.process_permission)
        SettlementDetails.objects.create(
            user=self.owner,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.received_invoice = self.create_invoice(
            document_number='FV/received', internal_number='WWW_2026_K_0001',
        )
        self.approved_invoice = self.create_invoice(
            document_number='FV/approved', internal_number='WWW_2026_K_0002',
            status=Invoice.Status.APPROVED,
        )
        self.split_invoice = self.create_invoice(
            document_number='FV/split', internal_number='WWW_2026_K_0003',
            status=Invoice.Status.APPROVED,
            first_item_amount=Decimal('6.00'),
        )
        self.processed_invoice = self.create_invoice(
            document_number='FV/processed', internal_number='WWW_2027_K_0002',
            status=Invoice.Status.PROCESSED,
            camp=self.other_camp,
        )
        CostItem.objects.create(
            invoice=self.split_invoice,
            amount=Decimal('4.00'),
            category=CostItem.Category.OUTINGS,
        )

    def create_invoice(
        self,
        *,
        document_number,
        internal_number,
        amount=Decimal('10.00'),
        camp=None,
        first_item_amount=None,
        invoice_type=Invoice.Type.KSEF,
        status=Invoice.Status.RECEIVED,
        user=None,
    ):
        invoice = Invoice.objects.create(
            user=user or self.owner,
            camp=camp or self.camp,
            attachment='invoices/cost.pdf',
            document_number=document_number,
            issue_date='2026-07-24',
            amount=amount,
            invoice_type=invoice_type,
            description='Cost administration test',
            internal_number=internal_number,
            status=status,
        )
        CostItem.objects.create(
            invoice=invoice,
            amount=first_item_amount or amount,
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        return invoice

    def test_administration_requires_view_permission(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 403)

    def test_administration_uses_datatables(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        self.assertContains(response, '<span class="sr-only">Wiersz</span>')
        self.assertContains(response, '<span class="sr-only">Załącznik</span>')
        self.assertContains(response, 'fas fa-download')
        self.assertContains(response, '/static/dist/datatables.css')
        self.assertContains(response, '/static/dist/datatables.js')
        self.assertContains(response, 'data-searchable="false"')
        self.assertContains(response, 'data-visible="false"', count=4)
        self.assertContains(response, 'data-search-panes=', count=3)
        self.assertContains(response, 'data-order="')
        for column in ('Opis i pozycje', 'Warsztaty', 'Kategoria', 'Data dodania',
                       'Typ dokumentu'):
            with self.subTest(column=column):
                self.assertContains(response, column)

    def test_administration_lists_all_invoices_without_server_side_filters(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['invoices']),
            [self.split_invoice, self.approved_invoice, self.received_invoice],
        )

    def test_administration_links_to_protected_invoice_attachments(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        self.assertContains(
            response,
            reverse('costs_invoice_attachment', args=[self.camp.pk, self.received_invoice.pk]),
        )

    def test_invoice_archive_contains_all_documents_for_the_selected_camp(self):
        field = Invoice._meta.get_field('attachment')
        original_storage = field.storage
        duplicate_name_invoice = self.create_invoice(
            document_number='FV/duplicate-name',
            internal_number=None,
        )

        with TemporaryDirectory() as sendfile_root:
            with override_settings(SENDFILE_ROOT=sendfile_root):
                field.storage = UploadStorage()
                try:
                    for invoice in (
                        self.received_invoice,
                        self.approved_invoice,
                        self.split_invoice,
                        self.processed_invoice,
                        duplicate_name_invoice,
                    ):
                        invoice.attachment.storage = field.storage
                    self.received_invoice.attachment.save(
                        'received.pdf', ContentFile(b'received document'), save=True,
                    )
                    self.approved_invoice.attachment.save(
                        'approved.jpg', ContentFile(b'approved document'), save=True,
                    )
                    self.split_invoice.internal_number = None
                    self.split_invoice.attachment.save(
                        'pending.png', ContentFile(b'pending document'), save=True,
                    )
                    self.split_invoice.save(update_fields=['internal_number'])
                    duplicate_name_invoice.attachment.save(
                        'nested/pending.png',
                        ContentFile(b'duplicate name document'),
                        save=True,
                    )
                    self.processed_invoice.attachment.save(
                        'other-year.pdf', ContentFile(b'other year document'), save=True,
                    )
                    self.client.force_login(self.csv_user)

                    response = self.client.get(
                        reverse('costs_invoice_archive', args=[self.camp.pk]),
                    )
                finally:
                    field.storage = original_storage

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="faktury-2026.zip"',
        )
        archive_content = b''.join(response.streaming_content)
        response.close()
        with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    'WWW_2026_K_0001.pdf',
                    'WWW_2026_K_0002.jpg',
                    'pending.png',
                    'pending (2).png',
                },
            )
            self.assertEqual(archive.read('WWW_2026_K_0001.pdf'), b'received document')
            self.assertEqual(archive.read('WWW_2026_K_0002.jpg'), b'approved document')
            self.assertEqual(archive.read('pending.png'), b'pending document')
            self.assertEqual(archive.read('pending (2).png'), b'duplicate name document')

    def test_invoice_archive_requires_view_all_costs_permission(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('costs_invoice_archive', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 403)

    def test_admin_with_change_invoice_permission_can_edit_another_users_invoice(self):
        self.admin.user_permissions.add(Permission.objects.get(codename='change_invoice'))
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('costs_admin_invoice_edit', args=[self.camp.pk, self.received_invoice.pk]),
            {
                'document_number': 'FV/corrected',
                'issue_date': '2026-07-24',
                'amount': '12.00',
                'invoice_type': Invoice.Type.KSEF,
                'description': 'Corrected cost administration test',
                'cost_items-TOTAL_FORMS': '1',
                'cost_items-INITIAL_FORMS': '1',
                'cost_items-MIN_NUM_FORMS': '0',
                'cost_items-MAX_NUM_FORMS': '1000',
                'cost_items-0-id': self.received_invoice.cost_items.get().pk,
                'cost_items-0-workshop': '',
                'cost_items-0-amount': '12.00',
                'cost_items-0-category': CostItem.Category.REGULAR_PURCHASES,
            },
        )

        self.assertRedirects(response, reverse('costs_admin', args=[self.camp.pk]))
        self.received_invoice.refresh_from_db()
        self.assertEqual(self.received_invoice.document_number, 'FV/corrected')
        self.assertEqual(self.received_invoice.amount, Decimal('12.00'))
        self.assertEqual(self.received_invoice.admin_modified_by, self.admin)
        self.assertIsNotNone(self.received_invoice.admin_modified_at)

    def test_admin_cost_list_links_unnumbered_invoice_document_number_to_edit_form(self):
        self.received_invoice.internal_number = None
        self.received_invoice.save(update_fields=['internal_number'])
        self.admin.user_permissions.add(Permission.objects.get(codename='change_invoice'))
        self.client.force_login(self.admin)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        change_url = reverse(
            'costs_admin_invoice_edit',
            args=[self.camp.pk, self.received_invoice.pk],
        )
        self.assertContains(
            response,
            f'<a href="{change_url}">{self.received_invoice.document_number}</a>',
            html=True,
        )

    def test_admin_invoice_edit_does_not_render_year_switches_without_an_invoice_id(self):
        self.admin.user_permissions.add(Permission.objects.get(codename='change_invoice'))
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('costs_admin_invoice_edit', args=[self.camp.pk, self.received_invoice.pk]),
        )

        self.assertEqual(response.status_code, 200)

    def test_admin_cost_list_links_to_invoice_owner_profile_by_full_name(self):
        self.received_invoice.user.first_name = 'Jan'
        self.received_invoice.user.last_name = 'Kowalski'
        self.received_invoice.user.save()
        self.client.force_login(self.admin)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        self.assertContains(
            response,
            reverse('profile', args=[self.received_invoice.user_id]),
        )
        self.assertContains(response, 'Jan Kowalski')

    def test_approval_transition_requires_approval_permission(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {'invoice_ids': [self.received_invoice.pk], 'status': Invoice.Status.APPROVED},
        )

        self.assertEqual(response.status_code, 403)
        self.received_invoice.refresh_from_db()
        self.assertEqual(self.received_invoice.status, Invoice.Status.RECEIVED)

    def test_batch_transition_rolls_back_when_any_invoice_cannot_transition(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {
                'invoice_ids': [self.received_invoice.pk, self.approved_invoice.pk],
                'status': Invoice.Status.APPROVED,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.received_invoice.refresh_from_db()
        self.assertEqual(self.received_invoice.status, Invoice.Status.RECEIVED)

    def test_approved_invoice_cannot_be_rejected(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {
                'invoice_ids': [self.approved_invoice.pk],
                'status': Invoice.Status.REJECTED,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.approved_invoice.refresh_from_db()
        self.assertEqual(self.approved_invoice.status, Invoice.Status.APPROVED)
        self.assertEqual(self.approved_invoice.internal_number, 'WWW_2026_K_0002')

    def test_processed_transition_requires_processing_permission(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {'invoice_ids': [self.approved_invoice.pk], 'status': Invoice.Status.PROCESSED},
        )

        self.assertEqual(response.status_code, 403)

    def test_processing_transition_processes_approved_invoice(self):
        self.client.force_login(self.process_user)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {'invoice_ids': [self.approved_invoice.pk], 'status': Invoice.Status.PROCESSED},
        )

        self.assertRedirects(response, reverse('costs_admin', args=[self.camp.pk]))
        self.approved_invoice.refresh_from_db()
        self.assertEqual(self.approved_invoice.status, Invoice.Status.PROCESSED)

    def test_processed_invoice_cannot_be_edited_or_reverted(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('costs_invoice_edit', args=[self.other_camp.pk, self.processed_invoice.pk]),
            {
                'document_number': 'FV/processed',
                'issue_date': '2026-07-24',
                'amount': '10.00',
                'invoice_type': Invoice.Type.KSEF,
                'description': 'Cost administration test',
                'cost_items-TOTAL_FORMS': '1',
                'cost_items-INITIAL_FORMS': '1',
                'cost_items-MIN_NUM_FORMS': '0',
                'cost_items-MAX_NUM_FORMS': '1000',
                'cost_items-0-id': self.processed_invoice.cost_items.get().pk,
                'cost_items-0-workshop': '',
                'cost_items-0-amount': '10.00',
                'cost_items-0-category': CostItem.Category.REGULAR_PURCHASES,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.processed_invoice.refresh_from_db()
        self.assertEqual(self.processed_invoice.status, Invoice.Status.PROCESSED)

    def test_default_csv_exports_only_approved_invoice_cost_items(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(reverse('costs_csv_export', args=[self.camp.pk]))
        rows = list(csv.reader(response.content.decode().splitlines()))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows[0], CSV_HEADER)
        self.assertEqual(len(rows), 4)
        self.assertNotIn(self.received_invoice.internal_number, [row[0] for row in rows[1:]])

    def test_selected_csv_exports_only_selected_invoice_cost_items(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(
            reverse('costs_csv_export', args=[self.camp.pk]), {'invoice_ids': [self.split_invoice.pk]},
        )
        rows = list(csv.reader(response.content.decode().splitlines()))

        self.assertEqual(rows[0], CSV_HEADER)
        self.assertEqual(len(rows), 3)
        self.assertEqual({row[0] for row in rows[1:]}, {self.split_invoice.internal_number})

    def test_csv_export_requires_view_permission(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('costs_csv_export', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)

    def test_csv_export_does_not_mutate_invoice_status(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(reverse('costs_csv_export', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)
        self.approved_invoice.refresh_from_db()
        self.assertEqual(self.approved_invoice.status, Invoice.Status.APPROVED)


class ReimbursementAndStatisticsViewsTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2025)
        self.recipient = User.objects.create_user(username='reimbursement-recipient')
        self.reimbursement_user = User.objects.create_user(username='reimbursement-user')
        self.statistics_user = User.objects.create_user(username='statistics-user')
        self.reimbursement_user.user_permissions.add(
            Permission.objects.get(codename='register_reimbursements'),
        )
        self.statistics_user.user_permissions.add(
            Permission.objects.get(codename='view_all_costs'),
        )
        self.details = SettlementDetails.objects.create(
            user=self.recipient,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.approved_invoice = self.create_invoice(
            amount=Decimal('30.00'),
            status=Invoice.Status.APPROVED,
        )
        self.over_balance_post = {
            'user_id': self.recipient.pk,
            'amount': '40.00',
            'type': Reimbursement.Type.ASSOCIATION,
            'comment': 'Transfer',
            'execution_date': '2026-07-24',
        }

    def create_invoice(
        self,
        *,
        amount,
        status,
        camp=None,
        category=CostItem.Category.WORKSHOPS,
    ):
        invoice = Invoice.objects.create(
            user=self.recipient,
            camp=camp or self.camp,
            attachment='invoices/statistics.pdf',
            document_number=f'FV/{Invoice.objects.count() + 1}/2026',
            issue_date='2026-07-24',
            amount=amount,
            invoice_type=Invoice.Type.KSEF,
            description='Statistics test',
            internal_number=f'WWW_2026_K_{Invoice.objects.count() + 1:04d}',
            status=status,
        )
        CostItem.objects.create(invoice=invoice, amount=amount, category=category)
        return invoice

    def test_reimbursement_uses_current_account_and_warns_above_balance(self):
        self.client.force_login(self.reimbursement_user)

        response = self.client.post(
            reverse('costs_reimbursements', args=[self.camp.pk]),
            self.over_balance_post,
        )

        reimbursement = Reimbursement.objects.get()
        expected_url = (
            f"{reverse('costs_reimbursements', args=[self.camp.pk])}?user={self.recipient.pk}"
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

        follow_response = self.client.get(expected_url)

        self.assertEqual(follow_response.context['balance_before'], Decimal('-10.00'))
        self.assertIsNone(follow_response.context['balance_after'])
        self.assertContains(follow_response, 'przekracza saldo')
        self.assertContains(follow_response, self.details.account_number)
        self.assertEqual(Reimbursement.objects.count(), 1)

        self.client.get(expected_url)

        self.assertEqual(Reimbursement.objects.count(), 1)

    def test_reimbursement_page_lists_each_recipient_summary(self):
        self.client.force_login(self.reimbursement_user)

        response = self.client.get(reverse('costs_reimbursements', args=[self.camp.pk]))

        self.assertEqual(
            response.context['reimbursement_summary'],
            [
                {
                    'user': self.recipient,
                    'account_number': self.details.account_number,
                    'has_account_number': True,
                    'approved_receipts_total': Decimal('0.00'),
                    'unapproved_receipts_total': Decimal('0.00'),
                    'approved_other_total': Decimal('30.00'),
                    'unapproved_other_total': Decimal('0.00'),
                    'approved_total': Decimal('30.00'),
                    'reimbursed_total': Decimal('0.00'),
                    'remaining_total': Decimal('30.00'),
                },
            ],
        )
        self.assertContains(
            response,
            f'?user={self.recipient.pk}',
        )

    def test_reimbursements_use_datatables(self):
        self.client.force_login(self.reimbursement_user)

        response = self.client.get(reverse('costs_reimbursements', args=[self.camp.pk]))

        self.assertContains(response, '<span class="sr-only">Wiersz</span>', count=2)
        self.assertContains(response, '/static/dist/datatables.css')
        self.assertContains(response, '/static/dist/datatables.js')
        self.assertContains(response, 'Brak osób oczekujących na zwrot.')
        self.assertContains(response, 'Brak zarejestrowanych zwrotów.')

    def test_selected_reimbursement_recipient_is_highlighted(self):
        self.client.force_login(self.reimbursement_user)

        response = self.client.get(
            reverse('costs_reimbursements', args=[self.camp.pk]),
            {'user': self.recipient.pk},
        )

        self.assertContains(response, 'class="table-primary"')
        self.assertContains(response, f'name="user_id" value="{self.recipient.pk}"')

    def test_reimbursements_require_registration_permission(self):
        self.client.force_login(self.recipient)

        response = self.client.get(reverse('costs_reimbursements', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 403)

    def test_statistics_sum_split_cost_items_once(self):
        split_invoice = self.create_invoice(
            amount=Decimal('20.00'),
            status=Invoice.Status.PROCESSED,
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        split_invoice.cost_items.update(amount=Decimal('10.00'))
        CostItem.objects.create(
            invoice=split_invoice,
            amount=Decimal('10.00'),
            category=CostItem.Category.WORKSHOPS,
        )
        self.client.force_login(self.statistics_user)

        response = self.client.get(reverse('costs_statistics', args=[self.camp.pk]))

        self.assertEqual(
            response.context['category_totals'][CostItem.Category.WORKSHOPS],
            Decimal('40.00'),
        )
        self.assertEqual(
            response.context['category_percentages'][CostItem.Category.WORKSHOPS],
            Decimal('80.00'),
        )

    def test_statistics_default_to_approved_and_processed_items(self):
        self.create_invoice(
            amount=Decimal('100.00'),
            status=Invoice.Status.RECEIVED,
            category=CostItem.Category.OUTINGS,
        )
        self.client.force_login(self.statistics_user)

        response = self.client.get(reverse('costs_statistics', args=[self.camp.pk]))

        self.assertEqual(response.context['total'], Decimal('30.00'))
        self.assertEqual(
            response.context['category_totals'][CostItem.Category.OUTINGS],
            Decimal('0.00'),
        )

    def test_statistics_filter_applies_to_summary_and_workshop_costs(self):
        workshop_type = WorkshopType.objects.create(year=self.camp, name='Statistics type')
        expensive_workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='expensive-workshop',
            title='Expensive workshop',
        )
        inexpensive_workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='inexpensive-workshop',
            title='Inexpensive workshop',
        )
        Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='workshop-without-costs',
            title='Workshop without costs',
        )
        non_accounting_invoice = self.create_invoice(
            amount=Decimal('40.00'),
            status=Invoice.Status.RECEIVED,
        )
        non_accounting_invoice.invoice_type = Invoice.Type.NON_ACCOUNTING_RECEIPT
        non_accounting_invoice.save(update_fields=['invoice_type'])
        non_accounting_invoice.cost_items.update(workshop=expensive_workshop)
        accounting_invoice = self.create_invoice(
            amount=Decimal('15.00'),
            status=Invoice.Status.RECEIVED,
        )
        accounting_invoice.cost_items.update(workshop=inexpensive_workshop)
        self.client.force_login(self.statistics_user)

        response = self.client.get(
            reverse('costs_statistics', args=[self.camp.pk]),
            {'status': Invoice.Status.RECEIVED},
        )

        self.assertEqual(response.context['total'], Decimal('55.00'))
        self.assertEqual(response.context.get('non_accounting_total'), Decimal('40.00'))
        self.assertEqual(response.context.get('accounting_total'), Decimal('15.00'))
        self.assertEqual(
            response.context.get('workshop_rows'),
            [
                {
                    'workshop_id': expensive_workshop.pk,
                    'workshop__title': expensive_workshop.title,
                    'total': Decimal('40.00'),
                },
                {
                    'workshop_id': inexpensive_workshop.pk,
                    'workshop__title': inexpensive_workshop.title,
                    'total': Decimal('15.00'),
                },
            ],
        )
        self.assertContains(response, 'Podsumowanie kosztów')
        self.assertContains(response, 'Paragony nieksięgowe')
        self.assertContains(response, 'Pozostałe koszty')
        self.assertNotContains(response, 'Workshop without costs')

    def test_statistics_ignores_removed_context_filter(self):
        workshop_type = WorkshopType.objects.create(year=self.camp, name='Statistics type')
        workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='statistics-workshop',
            title='Statistics workshop',
        )
        workshop_item = self.approved_invoice.cost_items.get()
        workshop_item.workshop = workshop
        workshop_item.save()
        other_category_invoice = self.create_invoice(
            amount=Decimal('5.00'),
            status=Invoice.Status.APPROVED,
            category=CostItem.Category.OUTINGS,
        )
        other_category_invoice.cost_items.update(workshop=workshop)
        camp_context_invoice = self.create_invoice(
            amount=Decimal('7.00'),
            status=Invoice.Status.APPROVED,
            category=CostItem.Category.WORKSHOPS,
        )
        processed_invoice = self.create_invoice(
            amount=Decimal('11.00'),
            status=Invoice.Status.PROCESSED,
            category=CostItem.Category.WORKSHOPS,
        )
        processed_invoice.cost_items.update(workshop=workshop)
        other_workshop_type = WorkshopType.objects.create(
            year=self.other_camp,
            name='Other statistics type',
        )
        other_workshop = Workshop.objects.create(
            year=self.other_camp,
            type=other_workshop_type,
            name='other-statistics-workshop',
            title='Other statistics workshop',
        )
        other_camp_invoice = self.create_invoice(
            amount=Decimal('13.00'),
            status=Invoice.Status.APPROVED,
            camp=self.other_camp,
            category=CostItem.Category.WORKSHOPS,
        )
        other_camp_invoice.cost_items.update(workshop=other_workshop)
        self.client.force_login(self.statistics_user)

        response = self.client.get(
            reverse('costs_statistics', args=[self.camp.pk]),
            {
                'status': Invoice.Status.APPROVED,
                'context': 'workshop',
            },
        )

        self.assertEqual(response.context['total'], Decimal('42.00'))
        self.assertNotContains(response, 'Zakres')

    def test_statistics_render_empty_chart_for_no_matching_items(self):
        self.client.force_login(self.statistics_user)

        response = self.client.get(
            reverse('costs_statistics', args=[self.camp.pk]),
            {
                'status': Invoice.Status.RECEIVED,
            },
        )

        self.assertFalse(response.context['has_statistics_data'])
        self.assertContains(response, 'Brak danych do wyświetlenia wykresu.')

    def test_statistics_require_permission(self):
        self.client.force_login(self.recipient)

        response = self.client.get(reverse('costs_statistics', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 403)
