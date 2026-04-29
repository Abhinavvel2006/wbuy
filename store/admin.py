from django.contrib import admin
from django.utils.html import format_html

from .models import Order, OrderItem, Payment, Product


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("name", "price", "quantity", "subtotal")

    def subtotal(self, obj):
        return f"Rs.{obj.subtotal}"


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("amount", "payment_id", "payment_method", "status", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "name", "category", "price", "stock", "is_active")
    list_display_links = ("thumbnail", "name")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    list_editable = ("price", "stock", "is_active")
    list_per_page = 20

    @admin.display(description="Image")
    def thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:45px;width:55px;object-fit:cover;border-radius:4px;">',
                obj.image.url,
            )
        return "-"

    actions = ["make_active", "make_inactive"]

    @admin.action(description="Mark selected as Active")
    def make_active(self, request, qs):
        qs.update(is_active=True)

    @admin.action(description="Mark selected as Inactive")
    def make_inactive(self, request, qs):
        qs.update(is_active=False)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "email", "status", "total", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "email")
    list_editable = ("status",)
    inlines = [OrderItemInline, PaymentInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "amount", "payment_method", "status", "payment_id", "created_at")
    list_filter = ("payment_method", "status", "created_at")
    search_fields = ("order__id", "order__user__username", "payment_id", "payment_method")
    readonly_fields = ("created_at",)
