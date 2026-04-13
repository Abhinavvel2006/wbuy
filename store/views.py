import json
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Product, Order, OrderItem


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
    total   = sum(float(i.get('price', 0)) * int(i.get('quantity', 1)) for i in cart_data)

    order = Order.objects.create(user=request.user, total=total, address=address)

    for item in cart_data:
        product = None
        try:
            product = Product.objects.get(name=item['name'])
        except Product.DoesNotExist:
            pass

        OrderItem.objects.create(
            order=order,
            product=product,
            name=item.get('name', ''),
            price=float(item.get('price', 0)),
            quantity=int(item.get('quantity', 1)),
        )

    messages.success(request, f'Order #{order.id} placed successfully!')
    return render(request, 'order_success.html', {'order': order})



@login_required
def orders(request):
    user_orders = Order.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'orders.html', {'orders': user_orders})


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
