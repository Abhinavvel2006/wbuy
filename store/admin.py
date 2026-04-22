from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model   = OrderItem
    extra   = 0
    readonly_fields = ('name', 'price', 'quantity', 'subtotal')

    def subtotal(self, obj):
        return f'₹{obj.subtotal}'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display        = ('thumbnail', 'name', 'category', 'price', 'stock', 'is_active')
    list_display_links  = ('thumbnail', 'name')
    list_filter         = ('category', 'is_active')
    search_fields       = ('name', 'description')
    list_editable       = ('price', 'stock', 'is_active')
    list_per_page       = 20

    @admin.display(description='Image')
    def thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:45px;width:55px;object-fit:cover;border-radius:4px;">',
                obj.image.url
            )
        return '—'

    actions = ['make_active', 'make_inactive']

    @admin.action(description='Mark selected as Active')
    def make_active(self, request, qs):
        qs.update(is_active=True)

    @admin.action(description='Mark selected as Inactive')
    def make_inactive(self, request, qs):
        qs.update(is_active=False)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display   = ('id', 'user', 'email', 'status', 'total', 'created_at')
    list_filter    = ('status',)
    search_fields  = ('user__username', 'email')
    list_editable  = ('status',)
    inlines        = [OrderItemInline]
    readonly_fields = ('created_at', 'updated_at')
