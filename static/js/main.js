function showCompany(ticker){
    window.location.href = "/screener/" + ticker;
};

function filterCountry(){
    var e = document.getElementById("country");
    var country = e.options[e.selectedIndex].value;
    window.location.href = "/?country=" + country;
};

function computeTotal(currency){
    var total = document.getElementById("total_add");
    var total_text = document.getElementById("total_add_text");
    var shares = document.getElementById("shares").value;
    var price = document.getElementById("price").value;
    total.value = shares * price;
    if (currency.length > 3){
        currency = "USD";
    }
    total_text.textContent = new Intl.NumberFormat('de-DE', { style: 'currency', currency: currency }).format(shares * price);
};

function disconnect(){
    window.location.href = "/logout";
};

Date.prototype.toDateInputValue = (function() {
    var local = new Date(this);
    local.setMinutes(this.getMinutes() - this.getTimezoneOffset());
    return local.toJSON().slice(0,10);
});
