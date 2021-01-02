from django.core.exceptions import ValidationError
from django.test import TestCase

from wwwforms.forms import PESELField


class PESELValidationTest(TestCase):
    def test_pesel_validation(self):
        pesel_field = PESELField()
        pesel_field.clean('98101672714')
        self.assertRaisesMessage(ValidationError, 'Suma kontrolna PESEL się nie zgadza.', lambda: pesel_field.clean('98101672710'))
        self.assertRaisesMessage(ValidationError, 'Długość numeru PESEL jest niepoprawna (10).', lambda: pesel_field.clean('9810167271'))
        self.assertRaisesMessage(ValidationError, 'Długość numeru PESEL jest niepoprawna (12).', lambda: pesel_field.clean('981016727143'))
        self.assertRaisesMessage(ValidationError, 'PESEL nie składa się z samych cyfr.', lambda: pesel_field.clean('abcdefghijk'))
        self.assertRaisesMessage(ValidationError, 'Data urodzenia zawarta w numerze PESEL nie istnieje.', lambda: pesel_field.clean('12345678903'))