# -*- coding: utf-8 -*-
"""
Presence analyzer unit tests.
"""
# pylint: disable=maybe-no-member, too-many-public-methods, invalid-name

from datetime import datetime, date, timedelta
import os.path
import unittest
from unittest.mock import Mock, patch

from .main import app, db, mail
from . import main, utils
from .fixtures import fill_db, fill_company
from .models import Order, Food, MailText


MOCK_ADMIN = Mock()
MOCK_ADMIN.is_admin.return_value = True
MOCK_ADMIN.username = 'test_user'
MOCK_ADMIN.is_anonymous.return_value = False
MOCK_ADMIN.email = 'mock@mock.com'
MOCK_ADMIN.id = 1
MOCK_ADMIN.rate_timestamp = date.today() - timedelta(1)


def setUp():
    """
    Main setup.
    """
    test_config = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'parts', 'etc', 'test.cfg',
    )
    app.config.from_pyfile(test_config)
    main.init()


class LunchBackendViewsTestCase(unittest.TestCase):
    """
    Views tests.
    """

    def setUp(self):
        """
        Before each test, set up a environment.
        """
        self.client = main.app.test_client()
        db.create_all()

    def tearDown(self):
        """
        Get rid of unused objects after each test.
        """
        db.session.remove()
        db.drop_all()

    def test_mainpage_view(self):
        """
        Test main page view.
        """
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)

    def test_info_view(self):
        """
        Test info page view.
        """
        fill_db()
        resp = self.client.get('/info')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("CATERING - menu na co dzi" in resp.data.__str__())
        mailtxt = MailText.query.first()
        mailtxt.info_page_text = "To jest nowa firma \n ze strna\n www.wp.pl"
        db.session.commit()
        resp = self.client.get('/info')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("www.wp.pl" in resp.data.__str__())

    @patch('lunch_app.views.current_user', new=MOCK_ADMIN)
    def test_my_orders_view(self):
        """
        Test my orders page view.
        """
        resp = self.client.get('/my_orders')
        self.assertEqual(resp.status_code, 200)

    @patch('lunch_app.views.current_user', new=MOCK_ADMIN)
    def test_overview_view(self):
        """
        Test overview page.
        """
        resp = self.client.get('/overview')
        self.assertEqual(resp.status_code, 200)

    @patch('lunch_app.views.current_user', new=MOCK_ADMIN)
    def test_create_order_view(self):
        """
        Test create order page.
        """
        fill_company()
        resp = self.client.get('/order')
        self.assertEqual(resp.status_code, 200)
        data = {
            'cost': '12',
            'company': 'Pod Koziołkiem',
            'description': 'dobre_jedzonko',
            'send_me_a_copy': 'false',
            'arrival_time': '12:00',
        }
        resp = self.client.post('/order', data=data)
        order_db = Order.query.first()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(order_db.cost, 12)
        self.assertEqual(order_db.company, 'Pod Koziołkiem')
        self.assertEqual(order_db.description, 'dobre_jedzonko')
        self.assertAlmostEqual(
            order_db.date,
            datetime.now(),
            delta=timedelta(seconds=1),
        )
        self.assertEqual(order_db.arrival_time, '12:00')

    @patch('lunch_app.views.current_user', new=MOCK_ADMIN)
    def test_create_order_with_email(self):
        """
        Test create order with send me an email.
        """
        fill_company()
        with mail.record_messages() as outbox:
            data = {
                'cost': '13',
                'company': 'Pod Koziołkiem',
                'description': 'To jest TESTow zamowienie dla emaila',
                'send_me_a_copy': 'true',
                'date': '2015-01-02',
                'arrival_time': '13:00',
            }
            resp = self.client.post('/order', data=data)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(len(outbox), 1)
            msg = outbox[0]
            self.assertTrue(msg.subject.startswith('Lunch order'))
            self.assertIn('To jest TESTow zamowienie dla emaila', msg.body)
            self.assertIn('Pod Koziołkiem', msg.body)
            self.assertIn('13.0 PLN', msg.body)
            self.assertIn('at 13:00', msg.body)
            self.assertEqual(msg.recipients, ['mock@mock.com'])

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_add_food_view(self):
        """
        Test add food page.
        """
        fill_company()
        resp = self.client.get('/add_food')
        self.assertEqual(resp.status_code, 200)
        data = {
            'cost': '333',
            'description': 'dobre_jedzonko',
            'date_available_to': '2015-01-01',
            'company': 'Pod Koziołkiem',
            'date_available_from': '2015-01-01',
            'o_type': 'daniednia',
            'add_meal': 'add',
        }
        resp_2 = self.client.post('/add_food', data=data,)
        food_db = Food.query.first()
        self.assertEqual(resp_2.status_code, 302)
        self.assertEqual(food_db.cost, 333)
        self.assertEqual(food_db.description, 'dobre_jedzonko')
        self.assertEqual(food_db.date_available_to, datetime(2015, 1, 1, 0, 0))
        self.assertEqual(food_db.company, 'Pod Koziołkiem')
        self.assertEqual(food_db.o_type, 'daniednia')
        self.assertEqual(
            food_db.date_available_from,
            datetime(2015, 1, 1, 0, 0)
        )

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_add_food__bulk_view(self):
        """
        Test bulk add food page.
        """
        fill_company()
        data = {
            'cost': '333',
            'description': 'dobre_jedzonko\r\nciekawe_jedzonko\r\npies',
            'date_available_to': '2015-01-01',
            'company': 'Pod Koziołkiem',
            'date_available_from': '2015-01-01',
            'o_type': 'daniednia',
            'add_meal': 'bulk',
        }
        resp = self.client.post('/add_food', data=data,)
        food_db = Food.query.get(1)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(food_db.cost, 333)
        self.assertEqual(food_db.description, 'dobre_jedzonko')
        self.assertEqual(food_db.date_available_to, datetime(2015, 1, 1, 0, 0))
        self.assertEqual(food_db.company, 'Pod Koziołkiem')
        self.assertEqual(food_db.o_type, 'daniednia')
        self.assertEqual(
            food_db.date_available_from,
            datetime(2015, 1, 1, 0, 0)
        )
        food_db = Food.query.get(2)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(food_db.cost, 333)
        self.assertEqual(food_db.description, 'ciekawe_jedzonko')
        self.assertEqual(food_db.date_available_to, datetime(2015, 1, 1, 0, 0))
        self.assertEqual(food_db.company, 'Pod Koziołkiem')
        self.assertEqual(food_db.o_type, 'daniednia')
        self.assertEqual(
            food_db.date_available_from,
            datetime(2015, 1, 1, 0, 0)
        )
        food_db = Food.query.get(3)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(food_db.cost, 333)
        self.assertEqual(food_db.description, 'pies')
        self.assertEqual(food_db.date_available_to, datetime(2015, 1, 1, 0, 0))
        self.assertEqual(food_db.company, 'Pod Koziołkiem')
        self.assertEqual(food_db.o_type, 'daniednia')
        self.assertEqual(
            food_db.date_available_from,
            datetime(2015, 1, 1, 0, 0)
        )

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_day_summary_view(self):
        """
        Test day summary page.
        """
        fill_db()
        resp = self.client.get('/day_summary')
        self.assertIn('Maly Gruby Nalesnik', str(resp.data))
        self.assertIn('Duzy Gruby Nalesnik', str(resp.data))
        db.session.close()

    def test_order_list_view(self):
        """
        Test order list page.
        """
        resp = self.client.get('/order_list')
        self.assertEqual(resp.status_code, 200)
        fill_db()
        data = {'year': '2015', 'user': '1'}
        resp = self.client.post('/order_list', data=data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.location, 'http://localhost/order_list/1/2015')
        data = {'year': '2015', 'month': '1', 'user': '1'}
        resp = self.client.post('/order_list', data=data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.location,
            'http://localhost/order_list/1/2015/1'
        )

    def test_order_list_view_month(self):
        """
        Test order list month page.
        """
        fill_db()
        resp = self.client.get('/order_list/1/2015/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Duzy Gruby Nalesnik', str(resp.data))
        self.assertIn('test_user', str(resp.data))
        self.assertIn('Tomas', str(resp.data))
        self.assertIn('2015-01-05', str(resp.data))

    def test_order_list_view_year(self):
        """
        Test order list year page.
        """
        fill_db()
        resp = self.client.get('/order_list/1/2015/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('January', str(resp.data))
        self.assertIn('test_user', str(resp.data))
        self.assertIn('Tomas', str(resp.data))
        self.assertIn('123', str(resp.data))

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_edit_order_view(self):
        """
        Test edit order page.
        """
        fill_db()
        resp = self.client.get('/order_edit/1/')
        self.assertEqual(resp.status_code, 200)
        data = {
            'cost': '12',
            'company': 'Pod Koziołkiem',
            'description': 'wyedytowane_dobre_jedzonko',
            'send_me_a_copy': 'false',
            'date': '2015-01-01',
            'arrival_time': '12:00',
        }
        resp = self.client.post('/order_edit/1/', data=data)
        order_db = Order.query.first()
        self.assertTrue(resp.status_code == 302)
        self.assertEqual(order_db.cost, 12)
        self.assertEqual(order_db.company, 'Pod Koziołkiem')
        self.assertEqual(order_db.description, 'wyedytowane_dobre_jedzonko')
        self.assertEqual(order_db.date, datetime(2015, 1, 1, 0, 0))
        self.assertEqual(order_db.arrival_time, '12:00')
        self.assertEqual(order_db.date, datetime(2015, 1, 1))

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_delete_order(self):
        """
        Test delete order.
        """
        fill_db()
        resp = self.client.post('/delete_order/1')
        self.assertEqual(resp.status_code, 302)
        order = Order.query.get(1)
        self.assertTrue(order is None)

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_company_summary_view(self):
        """
        Test company summary page.
        """
        resp = self.client.get('/company_summary')
        self.assertEqual(resp.status_code, 200)
        data = {'year': '2015', 'month': '1'}
        resp = self.client.post('/company_summary', data=data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.location,
            'http://localhost/company_summary/2015/1',
        )
        resp = self.client.get('/company_summary/2015/1')
        self.assertEqual(resp.status_code, 200)

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_company_summary_month_view(self):
        """
        Test company summary month page.
        """
        fill_db()
        resp = self.client.get('/company_summary/2015/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('123', str(resp.data))
        resp = self.client.get('/company_summary/2015/2')
        self.assertIn('489', str(resp.data))
        db.session.close()

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_finance_view(self):
        """
        Test finance page.
        """
        fill_db()
        # all users test
        resp = self.client.get('/finance/2015/2/0')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('test_user', str(resp.data))
        self.assertIn('test@user.pl', str(resp.data))
        self.assertIn('checked="checked"', str(resp.data))
        self.assertIn('x@x.pl', str(resp.data))

        # paid user test
        resp = self.client.get('/finance/2015/2/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('test_user', str(resp.data))
        self.assertIn('checked="checked"', str(resp.data))

        # unpaid user test
        resp = self.client.get('/finance/2015/2/2')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('test@user.pl', str(resp.data))
        self.assertIn('x@x.pl', str(resp.data))
        self.assertNotIn('checked=checked', str(resp.data))

        # unpaid user changed to paid test
        data = {
            'did_user_pay_test@user.pl': 'on',
        }
        resp = self.client.post('/finance/2015/2/2', data=data)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get('/finance/2015/2/2')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('test@user.pl', str(resp.data))
        resp = self.client.get('/finance/2015/2/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('test@user.pl', str(resp.data))
        db.session.close()

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_finance_mail_text_view(self):
        """
        Test finance emial text page.
        """
        fill_db()
        resp = self.client.get('/finance_mail_text')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('daili1', str(resp.data))
        self.assertIn('monthly2', str(resp.data))
        self.assertIn('reminder3', str(resp.data))
        self.assertIn('slacker4', str(resp.data))
        data = {
            'daily_reminder': 'Nowy Daily Reminder',
            'monthly_pay_summary': 'Ciekawszy Montlhy Reminder',
            'pay_reminder': 'Fajniejszy Reminder',
            'pay_slacker_reminder': 'Leniwy przypominacz',
            'info_page_text': 'Nowa strona Tomasa www.wp.pl',
            'daily_reminder_subject': 'STX Lunch nowy temat',
        }
        resp = self.client.post('/finance_mail_text', data=data)
        self.assertEqual(resp.status_code, 302)
        msg_text_db = MailText.query.get(1)
        self.assertEqual(
            msg_text_db.daily_reminder,
            'Nowy Daily Reminder',
        )
        self.assertEqual(
            msg_text_db.monthly_pay_summary,
            'Ciekawszy Montlhy Reminder',
        )
        self.assertEqual(
            msg_text_db.pay_reminder,
            'Fajniejszy Reminder',
        )
        self.assertEqual(
            msg_text_db.pay_slacker_reminder,
            'Leniwy przypominacz',
        )

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_finance_mail_all_view(self):
        """
        Test finance emial to all view.
        """
        fill_db()
        resp = self.client.get('/finance_mail_all')
        self.assertEqual(resp.status_code, 200)
        with mail.record_messages() as outbox:
            resp = self.client.post('/finance_mail_all')
            self.assertTrue(resp.status_code == 302)
            self.assertEqual(len(outbox), 2)
            msg = outbox[0]
            self.assertTrue(msg.subject.startswith('Lunch'))
            self.assertIn('February', msg.body)

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_payment_remind_view(self):
        """
        Test finance remind send email.
        """
        fill_db()
        with mail.record_messages() as outbox:
            resp = self.client.post('/payment_remind/x@x.pl/0')
            self.assertTrue(resp.status_code == 302)
            self.assertEqual(len(outbox), 1)
            msg = outbox[0]
            self.assertTrue(msg.subject.startswith('Lunch'))
            self.assertIn('reminder3', msg.body)
            self.assertEqual(msg.recipients, ['x@x.pl'])

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_finance_search_view(self):
        """
        Test finance serach view.
        """
        fill_db()
        resp = self.client.get('/finance_search')
        self.assertEqual(resp.status_code, 200)
        data = {'year': '2015', 'month': '1', 'did_pay': '0'}
        resp = self.client.post('/finance_search', data=data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.location,
            'http://localhost/finance/2015/1/0',
        )

    @patch('lunch_app.views.current_user', new=MOCK_ADMIN)
    def test_random_food(self):
        """
        Test random food.
        """
        fill_db()
        for i in range(4):
            order = Order()
            order.description = 'Kebab'
            order.company = 'Pod Koziołkiem'
            order.cost = i
            order.user_name = 'test@user.pl'
            order.arrival_time = '12:00'
            db.session.add(order)
        for i in range(4):
            order = Order()
            order.description = 'Burger'
            order.company = 'Pod Koziołkiem'
            order.cost = i
            order.user_name = 'test@user.pl'
            order.arrival_time = '12:00'
            db.session.add(order)
        for i in range(3):
            order = Order()
            order.description = 'Cieply_jamnik'
            order.company = 'Pod Koziołkiem'
            order.cost = i
            order.user_name = 'test@user.pl'
            order.arrival_time = '12:00'
            db.session.add(order)
        for i in range(3):
            order = Order()
            order.description = 'Kosmata_szynka'
            order.company = 'Pod Koziołkiem'
            order.cost = i
            order.user_name = 'test@user.pl'
            order.arrival_time = '12:00'
            db.session.add(order)
        order = Order()
        order.description = 'szpinak'
        order.company = 'Pod Koziołkiem'
        order.cost = 1
        order.user_name = 'test@user.pl'
        order.arrival_time = '12:00'
        db.session.add(order)
        db.session.commit()
        resp = self.client.get('/random_meal/1')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.location,
            'http://localhost/order'
        )
        resp = self.client.get('/random_meal/2')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.location,
            'http://localhost/order'
        )
        for i in range(10):
            self.client.get('/random_meal/2')
            orders = Order.query.filter(
                Order.user_name == 'test_user'
            ).all()
            for user_order in orders:
                self.assertNotEqual(
                    'szpinak',
                    user_order.description,
                )

    @patch('lunch_app.views.current_user', new=MOCK_ADMIN)
    def test_send_daily_reminder(self):
        """
        Test sends daili reminder to all users.
        """
        fill_db()
        with mail.record_messages() as outbox:
            resp = self.client.get('/send_daily_reminder')
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(len(outbox), 1)
            msg = outbox[0]
            self.assertTrue(msg.subject.startswith('STX Lunch'))
            self.assertIn('daili1', msg.body)
            self.assertEqual(msg.recipients, ['reminder@user.pl'])

    @patch('lunch_app.permissions.current_user', new=MOCK_ADMIN)
    def test_add_company(self):
        """
        Test adding new companies.
        """
        fill_db()
        resp = self.client.get('/finance_companies')
        self.assertEqual(resp.status_code, 200)
        data = {
            'name': 'SwietaKrowa',
            'web_page': 'http://www.swietakrowa.pl',
            'address': 'ul. Mickiewicza 7 92-200 Poznan',
            'telephone': '48618255256',
        }
        resp = self.client.post('/finance_companies', data=data)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get('/finance_companies')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(data['name'], str(resp.data))
        self.assertIn(data['web_page'], str(resp.data))
        self.assertIn(data['address'], str(resp.data))
        self.assertIn(data['telephone'], str(resp.data))
        resp = self.client.get('/add_food')
        self.assertIn(data['name'], str(resp.data))
        resp = self.client.get('/order')
        self.assertIn(data['name'], str(resp.data))
        resp = self.client.get('/order_edit/1/')
        self.assertIn(data['name'], str(resp.data))
        resp = self.client.get('/company_summary/2015/2')
        self.assertIn(data['name'], str(resp.data))
        order = Order()
        order.description = 'niewazne'
        order.cost = 29
        order.arrival_time = "12:00"
        order.company = data['name']
        order.user_name = 'test_user'
        db.session.add(order)
        db.session.commit()
        # resp = self.client.get('/day_summary')
        # self.assertIn(data['name'], str(resp.data))

    @patch('lunch_app.views.current_user', new=MOCK_ADMIN)
    def test_rating(self):
        """
        Test rating mechanism.
        """
        fill_db()
        data = {
            'cost': '12',
            'company': 'Pod Koziołkiem',
            'description': 'dobre_jedzonko',
            'send_me_a_copy': 'false',
            'arrival_time': '12:00',
        }
        resp = self.client.post('/order', data=data)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get('/food_rate')
        self.assertEqual(resp.status_code, 200)
        data = {'food': '1', 'rate': '1'}
        resp = self.client.post('/food_rate', data=data)
        self.assertEqual(resp.status_code, 302)
        food = Food.query.get(1)
        self.assertEqual(food.rating, 1.0)
        data = {'food': '1', 'rate': '5'}
        self.client.post('/food_rate', data=data)
        self.assertEqual(resp.status_code, 302)
        food = Food.query.get(1)
        self.assertEqual(food.rating, 3.0)
        # test if redirected after rating
        MOCK_ADMIN.rate_timestamp = date.today()
        resp = self.client.get('/food_rate')
        self.assertEqual(resp.status_code, 302)


class LunchBackendUtilsTestCase(unittest.TestCase):
    """
    Utils tests.
    """
    def setUp(self):
        """
        Before each test, set up a environment.
        """
        pass

    def tearDown(self):
        """
        Get rid of unused objects after each test.
        """
        pass

    def test_get_current_date(self):
        """
        Test current date.
        """
        self.assertEqual(utils.get_current_date(), date.today())

    def test_get_current_datetime(self):
        """
        Test current datetime.
        """
        self.assertAlmostEqual(
            utils.get_current_datetime(),
            datetime.now(),
            delta=timedelta(microseconds=101),
        )

    def test_make_date(self):
        """
        Test make date.
        """
        self.assertEqual(
            utils.make_date(datetime.now()),
            date.today()
        )

    def test_next_month(self):
        """
        Test next month function
        """
        self.assertEqual(
            utils.next_month(2015, 12),
            (2016, 1),
        )
        self.assertEqual(
            utils.next_month(2015, 6),
            (2015, 7),
        )

    def test_previous_month(self):
        """
        Test previous month function
        """
        self.assertEqual(
            utils.previous_month(2015, 1),
            (2014, 12),
        )
        self.assertEqual(
            utils.previous_month(2015, 6),
            (2015, 5),
        )


class LunchBackendPermissionsTestCase(unittest.TestCase):
    """
    Permissions tests.
    """
    def setUp(self):
        """
        Before each test, set up a environment.
        """
        self.client = main.app.test_client()

    def tearDown(self):
        """
        Get rid of unused objects after each test.
        """
        pass

    def test_permissions(self):
        """
        Tests if permissions decorator works properly
        """
        resp = self.client.get('add_food')
        self.assertEqual(resp.status_code, 401)
        resp_2 = self.client.get('day_summary')
        self.assertEqual(resp_2.status_code, 401)


def suite():
    """
    Default test suite.
    """
    base_suite = unittest.TestSuite()
    base_suite.addTest(unittest.makeSuite(LunchBackendViewsTestCase))
    base_suite.addTest(unittest.makeSuite(LunchBackendUtilsTestCase))
    base_suite.addTest(unittest.makeSuite(LunchBackendPermissionsTestCase))
    return base_suite


if __name__ == '__main__':
    unittest.main()
