function showCompany(ticker){
    window.location.href = "/screener/" + ticker;
}

function filterCountry(){
    var e = document.getElementById("country");
    var country = e.options[e.selectedIndex].value;
    window.location.href = "/?country=" + country;
}

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
}

function disconnect(){
    window.location.href = "/logout";
}

function add_transaction(){
    document.getElementById('submit_transaction').disabled = true; 
    document.getElementById('add_transaction').submit();
}

function fill_name(tickers){
    ticker = document.getElementById('ticker_input').value;
    document.getElementById('name_input').value = tickers[ticker];
}

function fill_ticker(tickers){
    name = document.getElementById('name_input').value;
    document.getElementById('ticker_input').value = getKeyByValue(tickers,name);
}

function getKeyByValue(object, value) {
  return Object.keys(object).find(key => object[key] === value);
}

Date.prototype.toDateInputValue = (function() {
    var local = new Date(this);
    local.setMinutes(this.getMinutes() - this.getTimezoneOffset());
    return local.toJSON().slice(0,10);
});