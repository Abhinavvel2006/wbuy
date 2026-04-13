from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/',          admin.site.urls),
    path('',                views.index,        name='index'),
    path('products/',       views.product_list, name='product_list'),
    path('cart/',           views.cart,         name='cart'),
    path('place-order/',    views.place_order,  name='place_order'),
    path('orders/',         views.orders,       name='orders'),
    path('login/',          views.login,        name='login'),
    path('logout/',         views.logout,       name='logout'),
    path('register/',       views.register,     name='register'),
    path('about/',          views.about,        name='about'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
