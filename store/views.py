import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Order, OrderItem, Product

import os
import traceback

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


STRIPE_CHECKOUT_SESSION_PLACEHOLDER = '{CHECKOUT_SESSION_ID}'


def _parse_cart_items(cart_json):
    try:
        cart_data = json.loads(cart_json or '[]')
    except (json.JSONDecodeError, ValueError):
        raise ValueError('Invalid cart data.')

    if not cart_data:
        raise ValueError('Your cart is empty.')

    total = Decimal('0.00')
    normalized_items = []
    for item in cart_data:
        try:
            quantity = int(item.get('quantity', 1))
            price = Decimal(str(item.get('price', 0)))
        except (TypeError, ValueError, InvalidOperation):
            raise ValueError('Invalid cart item data.')

        name = item.get('name', '').strip()
        if not name or quantity < 1 or price < 0:
            raise ValueError('Invalid cart item data.')

        total += price * quantity
        normalized_items.append({
            'name': name,
            'price': price,
            'quantity': quantity,
        })

    return normalized_items, total


def _send_order_confirmation_email(order):
    item_lines = [
        f"- {item.name} x{item.quantity} @ Rs.{item.price:.2f} = Rs.{item.subtotal:.2f}"
        for item in order.items.all()
    ]
    subject = f"Order Confirmed - WBuy Order #{order.id}"
    body = (
        f"Hi {order.user.username},\n\n"
        f"Thank you for shopping with WBuy! Your payment was received successfully.\n\n"
        f"Order ID: #{order.id}\n"
        f"Delivery: {order.address}\n\n"
        f"Items Ordered:\n"
        + "\n".join(item_lines)
        + f"\n\nOrder Total: Rs.{order.total:.2f}\n\n"
        f"We will notify you once your order is shipped.\n\n"
        f"Thanks,\nThe WBuy Team"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        fail_silently=False,
    )


def _resolve_checkout_session_id(request, order):
    session_id = (request.GET.get('session_id') or '').strip()
    if session_id and session_id != STRIPE_CHECKOUT_SESSION_PLACEHOLDER:
        return session_id

    pending_order_id = request.session.get('pending_order_id')
    pending_session_id = request.session.get('pending_checkout_session_id')
    if str(pending_order_id) == str(order.id) and pending_session_id:
        return pending_session_id

    return ''


def _get_checkout_order_id(session):
    metadata = getattr(session, 'metadata', {}) or {}

    if hasattr(metadata, 'to_dict'):
        metadata = metadata.to_dict()
    elif not isinstance(metadata, dict):
        try:
            metadata = dict(metadata)
        except (TypeError, ValueError):
            metadata = {}

    return str(metadata.get('order_id', '')).strip()

def index(request):
    featured = Product.objects.filter(is_active=True)[:8]
    categories = (
        Product.objects.filter(is_active=True)
        .values_list('category', flat=True)
        .distinct()
    )
    return render(request, 'index.html', {
        'featured': featured,
        'categories': categories,
    })


def product_list(request):
    products = Product.objects.filter(is_active=True)

    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(name__icontains=q) | products.filter(description__icontains=q)

    cat = request.GET.get('category', '').strip()
    if cat:
        products = products.filter(category=cat)

    sort = request.GET.get('sort', 'newest')
    products = products.order_by(
        {'price_asc': 'price', 'price_desc': '-price'}.get(sort, '-created_at')
    )

    categories = (
        Product.objects.filter(is_active=True)
        .values_list('category', flat=True)
        .distinct()
        .order_by('category')
    )

    return render(request, 'product.html', {
        'products': products,
        'categories': categories,
        'q': q,
        'cat': cat,
        'sort': sort,
    })


def cart(request):
    return render(request, 'cart.html')


@login_required
@require_POST
def place_order(request):
    try:
        normalized_items, total = _parse_cart_items(request.POST.get('cart_json', '[]'))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('cart')

    address = request.POST.get('address', '').strip()
    email = request.POST.get('email', '').strip()

    if not address:
        messages.error(request, 'Delivery address is required.')
        return redirect('cart')

    if not email:
        messages.error(request, 'Email is required.')
        return redirect('cart')

    order = Order.objects.create(
        user=request.user,
        email=email,
        total=total,
        address=address,
    )

    for item in normalized_items:
        product = Product.objects.filter(name=item['name']).first()
        OrderItem.objects.create(
            order=order,
            product=product,
            name=item['name'],
            price=item['price'],
            quantity=item['quantity'],
        )

    try:
        _send_order_confirmation_email(order)
    except Exception as exc:
        messages.warning(request, f'Order placed, but confirmation email failed: {exc}')

    messages.success(request, f'Order #{order.id} placed successfully!')
    return render(request, 'order_success.html', {'order': order})


@login_required
def orders(request):
    user_orders = Order.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'orders.html', {'orders': user_orders})


@login_required
@require_POST
def delete_order(request, order_id):
    order = Order.objects.filter(id=order_id, user=request.user).first()
    if not order:
        messages.error(request, 'Order not found.')
        return redirect('orders')

    order.delete()
    messages.success(request, f'Order #{order_id} deleted successfully.')
    return redirect('orders')


def register(request):
    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        email     = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not username or not password1:
            return render(request, 'register.html', {'error': 'Username and password are required.'})
        if password1 != password2:
            return render(request, 'register.html', {'error': 'Passwords do not match.'})
        if User.objects.filter(username=username).exists():
            return render(request, 'register.html', {'error': 'Username already taken.'})

        User.objects.create_user(username=username, email=email, password=password1)
        messages.success(request, 'Account created! Please log in.')
        return redirect('login')

    return render(request, 'register.html')


def login(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)
            return redirect(request.GET.get('next', 'index'))
        return render(request, 'login.html', {'error': 'Invalid username or password.'})

    return render(request, 'login.html')


def logout(request):
    auth_logout(request)
    return redirect('index')


def about(request):
    return render(request, 'about.html')

def email(request):
    return render(request, 'email.html')

@login_required
@require_POST
def pay(request):
    address = request.POST.get('address', '').strip()
    email = request.POST.get('email', '').strip()

    if not address:
        messages.error(request, 'Delivery address is required.')
        return redirect('cart')

    if not email:
        messages.error(request, 'Email is required.')
        return redirect('cart')

    try:
        normalized_items, total = _parse_cart_items(request.POST.get('cart_json', '[]'))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('cart')

    # Create order with 'pending' status - will be updated after payment
    order = Order.objects.create(
        user=request.user,
        email=email,
        total=total,
        address=address,
        status='pending',
    )


    for item in normalized_items:
        product = Product.objects.filter(name=item['name']).first()
        OrderItem.objects.create(
            order=order,
            product=product,
            name=item['name'],
            price=item['price'],
            quantity=item['quantity'],
        )

    # Store order_id in session for verification after payment
    request.session['pending_order_id'] = order.id

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        customer_email=email,
        line_items=[
            {
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': item['name'],
                    },
                    'unit_amount': int(item['price'] * 100),
                },
                'quantity': item['quantity'],
            }
            for item in normalized_items
        ],
        mode='payment',
        metadata={'order_id': str(order.id)},
        success_url=(
            request.build_absolute_uri(reverse('order_success'))
            + f'?order_id={order.id}&session_id={STRIPE_CHECKOUT_SESSION_PLACEHOLDER}'
        ),
        cancel_url=request.build_absolute_uri(reverse('cart')),
    )
    request.session['pending_checkout_session_id'] = session.id
    return redirect(session.url, code=303)
    

@login_required

def order_success(request):
    order_id = request.GET.get('order_id')
    order = None
    
    if order_id:
        order = Order.objects.filter(id=order_id, user=request.user).prefetch_related('items').first()

    if not order:
        messages.error(request, 'Order not found.')
        return redirect('index')

    session_id = _resolve_checkout_session_id(request, order)

    # Only verify and update if we have a session_id (came from Stripe redirect)
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as exc:
            messages.warning(request, f'Unable to verify payment status: {exc.user_message or str(exc)}')
        else:
            if session.payment_status == 'paid' and _get_checkout_order_id(session) == str(order.id):
                # Payment verified - update order status and send email
                if order.status == 'pending':
                    order.status = 'processing'
                    order.save(update_fields=['status', 'updated_at'])
                    print(f"ORDER UPDATED: ID={order.id}, STATUS={order.status}")
                    
                    # Send confirmation email only after successful payment
                    try:
                        _send_order_confirmation_email(order)
                    except Exception:
                        traceback.print_exc()   # Prints the full error to Render logs
                        raise
                request.session.pop('pending_order_id', None)
                request.session.pop('pending_checkout_session_id', None)
                messages.success(request, f'Payment successful! Order #{order.id} confirmed.')
            else:
                # Payment not completed - delete the pending order
                order.delete()
                request.session.pop('pending_order_id', None)
                request.session.pop('pending_checkout_session_id', None)
                messages.error(request, 'Payment was not completed. Please try again.')
                return redirect('cart')
    
    return render(request, 'order_success.html', {'order': order})
