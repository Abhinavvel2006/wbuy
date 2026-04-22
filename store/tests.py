import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Order, OrderItem, Product


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class PlaceOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            email='buyer-account@example.com',
            password='testpass123',
        )
        self.product = Product.objects.create(
            name='Headphones',
            description='Wireless headphones',
            price='1999.00',
            category='Electronics',
            stock=5,
            is_active=True,
        )
        self.client.login(username='buyer', password='testpass123')
        self.url = reverse('place_order')

    def test_place_order_saves_email_and_sends_confirmation(self):
        response = self.client.post(self.url, {
            'address': '123 Main Street',
            'email': 'customer@example.com',
            'cart_json': json.dumps([
                {'name': 'Headphones', 'price': 1999, 'quantity': 2},
            ]),
        })

        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.email, 'customer@example.com')
        self.assertEqual(order.address, '123 Main Street')
        self.assertEqual(order.total, Decimal('3998.00'))
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 1)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ['customer@example.com'])
        self.assertEqual(sent_email.from_email, 'shop@example.com')
        self.assertIn(f'#{order.id}', sent_email.subject)
        self.assertIn('123 Main Street', sent_email.body)
        self.assertIn('Headphones', sent_email.body)
        self.assertIn('Rs.3998.00', sent_email.body)

    def test_place_order_rejects_empty_cart(self):
        response = self.client.post(self.url, {
            'address': '123 Main Street',
            'email': 'customer@example.com',
            'cart_json': '[]',
        })

        self.assertRedirects(response, reverse('cart'))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    @patch('store.views.send_mail', side_effect=Exception('SMTP down'))
    def test_place_order_keeps_order_when_email_fails(self, mocked_send_mail):
        response = self.client.post(self.url, {
            'address': '123 Main Street',
            'email': 'customer@example.com',
            'cart_json': json.dumps([
                {'name': 'Headphones', 'price': 1999, 'quantity': 1},
            ]),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        mocked_send_mail.assert_called_once()

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn('Order #1 placed successfully!', messages)
        self.assertTrue(
            any('confirmation email failed: SMTP down' in message for message in messages)
        )

    def test_user_can_delete_own_order(self):
        order = Order.objects.create(
            user=self.user,
            email='customer@example.com',
            total='1999.00',
            address='123 Main Street',
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            name='Headphones',
            price='1999.00',
            quantity=1,
        )

        response = self.client.post(reverse('delete_order', args=[order.id]))

        self.assertRedirects(response, reverse('orders'))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_user_cannot_delete_another_users_order(self):
        other_user = User.objects.create_user(
            username='otherbuyer',
            email='other@example.com',
            password='testpass123',
        )
        order = Order.objects.create(
            user=other_user,
            email='customer@example.com',
            total='1999.00',
            address='123 Main Street',
        )

        response = self.client.post(reverse('delete_order', args=[order.id]))

        self.assertRedirects(response, reverse('orders'))
        self.assertEqual(Order.objects.count(), 1)
