var CART_KEY = 'wbuy_cart';


function getCart() {
    try {
        return JSON.parse(localStorage.getItem(CART_KEY)) || [];
    } catch (e) {
        return [];
    }
}

function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function addToCart(name, price, image) {
    var cart  = getCart();
    var found = false;

    for (var i = 0; i < cart.length; i++) {
        if (cart[i].name === name) {
            cart[i].quantity += 1;
            found = true;
            break;
        }
    }

    if (!found) {
        cart.push({ name: name, price: parseFloat(price), image: image, quantity: 1 });
    }

    saveCart(cart);
    updateCartBadge();
    showToast(name + ' added to cart!', 'success');
}

function updateCartBadge() {
    var cart  = getCart();
    var count = 0;
    for (var i = 0; i < cart.length; i++) {
        count += cart[i].quantity;
    }
    var $badge = $('.cart-count');
    $badge.text(count);
    if (count > 0) {
        $badge.show();
    } else {
        $badge.hide();
    }
}


function showToast(message, type) {
    type = type || 'primary';
    var id  = 'toast-' + Date.now();
    var html = '<div id="' + id + '" class="toast align-items-center text-bg-' + type + ' border-0 mb-2" role="alert">' +
               '<div class="d-flex">' +
               '<div class="toast-body">' + message + '</div>' +
               '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
               '</div></div>';

    if ($('#toast-area').length === 0) {
        $('body').append('<div id="toast-area"></div>');
    }

    $('#toast-area').append(html);
    var toastEl = document.getElementById(id);
    var toast   = new bootstrap.Toast(toastEl, { delay: 2500 });
    toast.show();
    $(toastEl).on('hidden.bs.toast', function () { $(this).remove(); });
}


$(function () {
    updateCartBadge();

    $(document).on('click', '.add-to-cart-btn', function () {
        var $btn  = $(this);
        var name  = $btn.data('name');
        var price = $btn.data('price');
        var image = $btn.data('image') || '';
        addToCart(name, price, image);
    });
});
