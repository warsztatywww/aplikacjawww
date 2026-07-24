from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from wwwapp.models import Camp, CostItem, Invoice, SettlementDetails, Workshop, WorkshopType


class CostModelTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2027)
        self.user = User.objects.create_user(username='user')
        self.invoice = Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            document_number='FV/1/2026',
            issue_date='2026-07-24',
            amount=Decimal('10.00'),
            invoice_type=Invoice.Type.KSEF,
            attachment='invoices/fv-1.pdf',
            description='Materiały do warsztatów',
            internal_number='WWW_2026_FP_0001',
        )
        workshop_type = WorkshopType.objects.create(year=self.other_camp, name='Type')
        self.other_workshop = Workshop.objects.create(
            year=self.other_camp,
            type=workshop_type,
            name='other-workshop',
            title='Other workshop',
        )

    def test_cost_item_rejects_workshop_from_another_camp(self):
        item = CostItem(invoice=self.invoice, workshop=self.other_workshop,
                        amount=Decimal('1.00'), category=CostItem.Category.WORKSHOPS)

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_settlement_details_are_unique_per_user_and_camp(self):
        SettlementDetails.objects.create(user=self.user, camp=self.camp,
                                         account_number='PL61109010140000071219812874')

        with self.assertRaises(IntegrityError):
            SettlementDetails.objects.create(user=self.user, camp=self.camp,
                                             account_number='PL27114020040000300201355387')
