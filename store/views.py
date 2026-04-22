import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Order, OrderItem, Product


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
    """Receive cart JSON from frontend, create Order in DB."""
    try:
        cart_data = json.loads(request.POST.get('cart_json', '[]'))
    except (json.JSONDecodeError, ValueError):
        messages.error(request, 'Invalid cart data.')
        return redirect('cart')

    if not cart_data:
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    address = request.POST.get('address', '').strip()
    email = request.POST.get('email', '').strip()

    if not address:
        messages.error(request, 'Delivery address is required.')
        return redirect('cart')

    if not email:
        messages.error(request, 'Email is required.')
        return redirect('cart')

    total = Decimal('0.00')
    normalized_items = []
    for item in cart_data:
        try:
            quantity = int(item.get('quantity', 1))
            price = Decimal(str(item.get('price', 0)))
        except (TypeError, ValueError, InvalidOperation):
            messages.error(request, 'Invalid cart item data.')
            return redirect('cart')

        name = item.get('name', '').strip()
        if not name or quantity < 1 or price < 0:
            messages.error(request, 'Invalid cart item data.')
            return redirect('cart')

        total += price * quantity
        normalized_items.append({
            'name': name,
            'price': price,
            'quantity': quantity,
        })

    order = Order.objects.create(
        user=request.user,
        email=email,
        total=total,
        address=address,
    )

    item_lines = []
    for item in normalized_items:
        product = Product.objects.filter(name=item['name']).first()
        quantity = item['quantity']
        price = item['price']
        name = item['name']

        OrderItem.objects.create(
            order=order,
            product=product,
            name=name,
            price=price,
            quantity=quantity,
        )
        item_lines.append(f"- {name} x{quantity} @ Rs.{price:.2f} = Rs.{price * quantity:.2f}")

    subject = f"Order Confirmed - WBuy Order #{order.id}"
    body = (
        f"Hi {request.user.username},\n\n"
        f"Thank you for shopping with WBuy! Your order has been placed.\n\n"
        f"Order ID: #{order.id}\n"
        f"Delivery: {address}\n\n"
        f"Items Ordered:\n"
        + "\n".join(item_lines)
        + f"\n\nOrder Total: Rs.{total:.2f}\n\n"
        f"We will notify you once your order is shipped.\n\n"
        f"Thanks,\nThe WBuy Team"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.email],
            fail_silently=False,
        )
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
