function showCompany(ticker) {
    window.location.href = "/screener/" + ticker;
}

function show_portfolio(portfolio_name){
    window.location.href = "/portfolio?name=" + portfolio_name;
}

function got_to_portfolio_manager(){
    window.location.href = "/portfolios-manager";
}

function got_to_screener(){
    window.location.href = "/";
}


function filterCountry() {
    var e = document.getElementById("country");
    var country = e.options[e.selectedIndex].value;
    window.location.href = "/?country=" + country;
}

function computeTotal(currency) {
    var total = document.getElementById("total_add");
    var total_text = document.getElementById("total_add_text");
    var shares = document.getElementById("shares").value;
    var price = document.getElementById("price").value;
    total.value = shares * price;
    if (currency.length > 3) {
        currency = "USD";
    }
    total_text.textContent = new Intl.NumberFormat('de-DE', {
        style: 'currency',
        currency: currency
    }).format(shares * price);
}

function disconnect() {
    window.location.href = "/logout";
}

function add_transaction(tickers) {
    if(document.getElementById('add_transaction').reportValidity()){    
        ticker = document.getElementById('ticker_input').value;
        name = document.getElementById('name_input').value;
        if(ticker in tickers && tickers[ticker] == name){
            document.getElementById('submit_transaction').disabled = true;
            document.getElementById('submit_transaction').style.backgroundColor = "grey";
            document.getElementById('add_transaction').submit();
        }
        else{
            error_div = document.getElementById("error_add_transaction");
            error_div.style.display = "block";
            error_div.innerHTML = "Error: Ticker and Name do not match.";
        }
    }
}

function add_portfolio(currencies){
    if(document.getElementById('add_portfolio_form').reportValidity()){
        currency = document.getElementById('portfolio_currency').value;
        alert(currency in currencies);
        if(currencies.includes(currency)){
            document.getElementById('submit_portfolio').disabled = true;
            document.getElementById('submit_portfolio').style.backgroundColor = "grey";
            document.getElementById('add_portfolio_form').submit();
        }
        else{
            error_div = document.getElementById("error_add_transaction");
            error_div.style.display = "block";
            error_div.innerHTML = "Error: Currency " + currency + " does not exists.";
        }
    }
}

function fill_name(tickers) {
    ticker = document.getElementById('ticker_input').value;
    document.getElementById('name_input').value = tickers[ticker];
}

function fill_ticker(tickers) {
    name = document.getElementById('name_input').value;
    document.getElementById('ticker_input').value = getKeyByValue(tickers, name);
}

function go_to_portfolio_form(){
    var elmnt = document.getElementById("add_portfolio_form");
    elmnt.style.display = "block";
    elmnt.scrollIntoView();
}

function getKeyByValue(object, value) {
    return Object.keys(object).find(key => object[key] === value);
}

function openTab(evt, tabName) {
    // Declare all variables
    var i, tabcontent, tablinks;

    // Get all elements with class="tabcontent" and hide them
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }

    // Get all elements with class="tablinks" and remove the class "active"
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }

    // Show the current tab, and add an "active" class to the button that opened the tab
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
}

Date.prototype.toDateInputValue = (function () {
    var local = new Date(this);
    local.setMinutes(this.getMinutes() - this.getTimezoneOffset());
    return local.toJSON().slice(0, 10);
});
