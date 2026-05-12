(() => {
  // ../quickfix/quickfix/public/js/quickfix.bundle.js
  frappe.provide("quickfix");
  quickfix.add_shop_name = function() {
    console.log("Adding shop name to navbar...");
    var shop_name = frappe.boot.quickfix_shop_name;
    console.log("Shop name from boot:", shop_name);
    if (shop_name && !$(".quickfix-shop-name").length) {
      $(".navbar-brand img").after(
        `<span 
                class="quickfix-shop-name"
                style="
                    color: #555;
                    font-size: 20px;
                    font-weight:700;
                    margin-left: 10px;
                    vertical-align: middle;
                    display: inline-block;">
                        ${shop_name}
            </span>`
      );
    }
  };
  $(document).ready(function() {
    quickfix.add_shop_name();
  });
})();
//# sourceMappingURL=quickfix.bundle.FONZ3WHC.js.map
