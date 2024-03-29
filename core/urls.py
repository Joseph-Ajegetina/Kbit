from django.urls import path
from .views import (
    HomeView,
    ItemView,
    CheckOutView,
    add_to_cart, 
    remove_from_cart,
    OrderSummaryView,
    remove_single_item_from_cart,
    add_single_item_to_cart,
    PaymentView,
    AddCouponView,
    RequestRefundView
)

app_name = 'core'


urlpatterns = [
    path('', HomeView.as_view(), name="home"),
    path('checkout/', CheckOutView.as_view(), name="checkout"),
    path('order-summary/', OrderSummaryView.as_view(), name="order-summary"),
    path('product/<slug>', ItemView.as_view(), name="product"),
    path('add-to-cart/<slug>', add_to_cart, name='add-to-cart'),
    path('add-coupon/', AddCouponView.as_view(), name='add-coupon'),
    path('remove-from-cart/<slug>', remove_from_cart, name='remove-from-cart'),
    path('remove-single-item_from-cart/<slug>', remove_single_item_from_cart, name='remove-single-from-cart'),
    path('add-single-item-to-cart/<slug>', add_single_item_to_cart, name='add-single-to-cart'),
    path('payment/<payment_option>', PaymentView.as_view(), name="payment"),
    path('request-refund',RequestRefundView.as_view(), name='request-refund')
]