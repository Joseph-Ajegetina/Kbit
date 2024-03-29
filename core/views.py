from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Item, Order, OrderItem, Address, Payment, Coupon, Refund, UserProfile
from django.views.generic import ListView, DetailView, View
from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm
from django.contrib import messages
from django.utils import timezone
from django.http import Http404

import random
import string
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class CheckOutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            print(form.fields)
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }
            shipping_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True)

            if shipping_address_qs.exists():
                context.update({'default_shipping_address': shipping_address_qs[0]})
                print(context)

            billing_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='B',
                default=True)

            if billing_address_qs.exists():
                context.update({'default_billing_address': billing_address_qs[0]})
            return render(self.request, "checkout.html", context=context)

        except ObjectDoesNotExist:
            messages.info(self.request, "you do not have an active order")
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        try:
            form = CheckoutForm(self.request.POST or None)
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                use_default_shipping = form.cleaned_data.get('use_default_shipping')
                if use_default_shipping:
                    print("Using the default shipping address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='S',
                        default=True)
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.warning(self.request, "No default shipping address")
                        return redirect('core:checkout')
                else:
                    print('user entering a new shipping address')
                    shipping_address1 = form.cleaned_data.get('shipping_address1')
                    shipping_address2 = form.cleaned_data.get('shipping_address2')
                    shipping_country = form.cleaned_data.get('shipping_country')
                    shipping_zipcode = form.cleaned_data.get('shipping_zipcode')
                    payment_options = form.cleaned_data.get('payment_options')
                    if is_valid_form([shipping_address1, shipping_address2, shipping_country]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zipcode=shipping_zipcode,
                            address_type='S'
                        )
                        shipping_address.save()
                        order.shipping_address = shipping_address
                        order.save()
                        set_default_shipping = form.cleaned_data.get('set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()
                    else:
                        messages.info(self.request, "Please fill in the required shipping address fields")

                use_default_billing = form.cleaned_data.get('use_default_billing')
                same_billing_address = form.cleaned_data.get('same_billing_address')
                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.address_type = "B"
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    print("Using the default billing address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='B',
                        default=True)
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.warning(self.request, "No default billing address")
                        return redirect('core:checkout')
                else:
                    print('user entering a new billing address')
                    billing_address1 = form.cleaned_data.get('billing_address1')
                    billing_address2 = form.cleaned_data.get('billing_address2')
                    billing_country = form.cleaned_data.get('billing_country')
                    billing_zipcode = form.cleaned_data.get('billing_zipcode')
                    print(f"Billing_address1: {billing_address1} \nBilling_address2:{billing_address2}")
                    if is_valid_form([billing_address1, billing_address2, billing_country]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zipcode=billing_zipcode,
                            address_type='B'
                        )
                        billing_address.save()
                        order.billing_address = billing_address
                        order.save()
                        set_default_billing = form.cleaned_data.get('set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()
                    else:
                        messages.info(self.request, "Please fill in the required billing address fields")

                payment_option = form.cleaned_data.get('payment_option')
                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                return redirect('core:checkout')
            else:
                messages.warning(self.request, "Failed checkout")
                return redirect('core:checkout')

            return render(self.request, "order_summary.html")
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have active order")
            return redirect('/')


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False
            }
            try:
                userprofile = self.request.user.userprofile
                if userprofile.one_click_purchasing:
                    # fetech user card list
                    cards = stripe.Customer.list_sources(
                        userprofile.stripe_customer_id,
                        limit=3,
                        object='card'
                    )
                    card_list = cards['data']
                    if len(card_list) > 0:
                        # Update the context with the default card
                        context.update({'card': card_list[0]})

                return render(self.request, "payment.html", context=context)
            except ObjectDoesNotExist:
                return render(self.request, "payment.html", context=context)
        else:
            messages.warning(self.request, 'You have not added a billing address')
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST or None)
        userprofile = UserProfile.objects.get(user=self.request.user)
        if form.is_valid():
            token = self.request.POST.get("stripeToken")
            save = form.cleaned_data.get('save_card')
            use_default = form.cleaned_data.get('use_default')

            if save:
                # allow to fetch the cards
                if not userprofile.stripe_customer_id:
                    customer = stripe.Customer.create(
                        email=self.request.user.email,
                        source=token
                    )
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                    userprofile.save()
                else:
                    stripe.Customer.create_source(
                        userprofile.stripe_customer_id,
                        source=token
                    )
            amount = int(order.get_total() * 100)

            try:
                if use_default:
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency='usd',
                        customer=userprofile.stripe_customer_id

                    )
                else:
                    # Use Stripe's library to make requests...
                    charge = stripe.Charge.create(
                        amount=amount,
                        currency="usd",
                        source=token,
                        description="My First Test Charge (created for API docs)",
                    )
                # create payment
                payment = Payment()
                payment.stripe_charge_id = charge
                payment.user = self.request.user
                payment.amount = order.get_total()
                payment.save()

                # assign the payment to the order
                order_items = order.items.all()
                order_items.update(ordered=True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.payment = payment
                order.ref_code = create_ref_code()
                order.save()

                messages.success(self.request, "Your order was successful")
                return redirect('/')

            except stripe.error.CardError as e:
                # Since it's a decline, stripe.error.CardError will be caught
                body = e.json_body
                err = body.get('error', {})
                messages.error(self.request, f"{ err.get('message') }")
                return redirect('/')

            except stripe.error.RateLimitError as e:
                messages.warning(self.request, "Rate limit error")
                return redirect('/')

            except stripe.error.InvalidRequestError as e:
                messages.warning(self.request, "Invalid parameters")
                return redirect('/')

            except stripe.error.AuthenticationError as e:
                messages.warning(self.request, "Not authenticated")
                return redirect('/')

            except stripe.error.APIConnectionError as e:
                messages.warning(self.request, "Network error")
                return redirect('/')

            except stripe.error.StripeError as e:
                messages.warning(self.request, "You were not charged, please try again")
                return redirect('/')

            except Exception as e:
                messages.warning(self.request, "A serious error occured, we have been notified")
                return redirect('/')


class ItemView(DetailView):
    model = Item
    template_name = 'product.html'


class HomeView(ListView):
    model = Item
    template_name = "home.html"
    paginate_by = 10


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {'object': order}
            return render(self.request, "order_summary.html", context=context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have active order")
            return redirect('/')


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    print(order_qs)
    if order_qs.exists():
        print("exists")
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item was added to order items")
            return redirect("core:product", slug=slug)
        else:
            order.items.add(order_item)
            messages.info(request, "This item was added to your orders")
            return redirect("core:product", slug=item.slug)
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=request.user, start_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "This item was added to your orders")
        return redirect("core:product", slug=slug)


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            # order.items.remove(order_item)
            order_item.delete()
            messages.info(request, "This item was removed from your cart.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart")
            return redirect("core:order-summary")
    else:
        messages.info(request, "You do not have an active order")
        return redirect("core:order-summary")


@login_required
def add_single_item_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated")
            return redirect("core:order-summary")
        else:
            order.items.add(order_item)
            messages.info(request, "This item was added to your orders")
            return redirect("core   order-summary")


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order_item.delete()
            messages.info(request, "This item quantity was updated.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart")
            return redirect("core:order-summary")
    else:
        messages.info(request, "You do not have an active order")
        return redirect("core:order-summary")


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon

    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect('core:checkout')


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, 'You have successfully added coupon')
                return redirect('core:checkout')
            except ObjectDoesNotExist:
                messages.info(self.request, "you do not have an active order")
                return redirect('core:checkout')


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context=context)

    def post(self, *args, **swargs):
        form = RefundForm(self.request.POST or None)
        print(form.is_valid())
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()
                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request, 'Your request was received')

            except ObjectDoesNotExist:
                messages.info(self.request, "This order does not exit")
                return redirect('core:request-refund')
