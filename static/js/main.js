function showCompany(ticker) {
    window.location.href = "/screener/" + ticker;
}

function import_portfolio() {
    window.location.href = "/import_portfolio";
}

function show_portfolio(portfolio_name) {
    window.location.href = "/portfolio?name=" + portfolio_name;
}

function got_to_portfolio_manager() {
    window.location.href = "/portfolios-manager";
}

function got_to_screener() {
    window.location.href = "/";
}

function go_to_login() {
    window.location.href = "/login";
}

function go_to_register() {
    window.location.href = "/register";
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

function fillTransactionFormWithTickers(tickers) {
    let ticker_options = document.getElementById("tickers");
    let names_options = document.getElementById("names");
    for (const key in tickers) {
        ticker_options.appendChild(createOption(key));
        names_options.appendChild(createOption(tickers[key]));
    }
}

function fillDividendsHistory(dividends, page, sorted_column = "Date", ascending = true) {
    let table = document.getElementById("dividend_table");
    while (table.children.length > 1) {
        table.removeChild(table.lastChild);
    }
    if (!(sorted_column in dividends)) {
        throw Error(sorted_column + " not in dividend dictionary.");
    }
    let length = Object.keys(dividends[sorted_column]).length
    let indices = new Array(length);
    for (let i = 0; i < length; ++i) indices[i] = i;
    if(ascending){
        indices.sort(function (a, b) {
            return dividends[sorted_column][a] < dividends[sorted_column][b] ? -1 : dividends[sorted_column][a] > dividends[sorted_column][b] ? 1 : 0;
        })
    }
    else{
        indices.sort(function (a, b) {
            return dividends[sorted_column][a] > dividends[sorted_column][b] ? -1 : dividends[sorted_column][a] < dividends[sorted_column][b] ? 1 : 0;
        })
    }

    for(let key of Object.keys(dividends)){
        let temp = new Array(length);
        for(let i = 0; i < length; ++i){
            temp[i] = dividends[key][indices[i]];
        }
        dividends[key] = temp;
    }

    let countRow = 0;
    const maxRows = 10;
    let current_page = 1;
    for (const index in dividends["Date"]) {
        if (countRow > maxRows) {
            current_page += 1;
            countRow = 0;
        }
        if (current_page === page) {
            let row = document.createElement('tr');
            row.appendChild(createColumn(dividends["Tickers"][index]));
            row.appendChild(createColumn(dividends["Name"][index]));
            row.appendChild(createColumn(Math.round(dividends["Dividends"][index] * 100) / 100));
            row.appendChild(createColumn(dividends["Date"][index]));
            table.appendChild(row);
        }
        countRow += 1;
    }
    let maxPages = Math.ceil(Object.keys(dividends["Date"]).length / maxRows)
    document.getElementById("pagination_dividend").innerHTML = "";
    let ul = document.createElement('ul');
    ul.classList.add("pagination");
    ul.classList.add("justify-content-center");
    for (let i = 1; i < maxPages; i++) {
        if (i < 5 || maxPages - i < 5) {
            let li = document.createElement('li');
            if (i === page) {
                li.classList.add("active");
            }
            li.classList.add("page-item");
            let link = document.createElement("a");
            link.innerText = i.toString();
            link.classList.add("page-link");
            link.href = "#dividend_table";
            link.onclick = function () {
                fillDividendsHistory(dividends, i, sorted_column, ascending)
            };
            li.appendChild(link)
            ul.appendChild(li)
        } else if (i === 5) {
            let li = document.createElement('li');
            li.classList.add("page-item");
            li.classList.add("disabled");
            let link = document.createElement("a");
            link.innerText = "...";
            link.classList.add("page-link");
            link.href = "#";
            li.appendChild(link)
            ul.appendChild(li)
        }
    }
    document.getElementById("pagination_dividend").appendChild(ul);
    return !ascending;
}

function createColumn(value) {
    let column = document.createElement('td');
    column.innerText = value;
    return column
}

function createOption(value) {
    var opt = document.createElement('option');
    opt.appendChild(document.createTextNode(value));
    opt.value = value;
    return opt;
}

function add_transaction(tickers) {
    if (document.getElementById('add_transaction').reportValidity()) {
        ticker = document.getElementById('ticker_input').value;
        name = document.getElementById('name_input').value;
        if (ticker in tickers && tickers[ticker] == name) {
            document.getElementById('submit_transaction').disabled = true;
            document.getElementById('submit_transaction').style.backgroundColor = "grey";
            document.getElementById('add_transaction').submit();
        } else {
            error_div = document.getElementById("error_add_transaction");
            error_div.style.display = "block";
            error_div.innerHTML = "Error: Ticker and Name do not match.";
        }
    }
}

function add_portfolio(currencies) {
    if (document.getElementById('add_portfolio_form').reportValidity()) {
        currency = document.getElementById('portfolio_currency').value;
        if (currencies.includes(currency)) {
            document.getElementById('submit_portfolio').disabled = true;
            document.getElementById('submit_portfolio').style.backgroundColor = "grey";
            document.getElementById('add_portfolio_form').submit();
        } else {
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

function go_to_portfolio_form() {
    var elmnt = document.getElementById("add_portfolio_form");
    elmnt.style.display = "block";
    elmnt.scrollIntoView();
}

function getKeyByValue(object, value) {
    return Object.keys(object).find(key => object[key] === value);
}

function openTab(buttonName, tabName) {
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
    document.getElementById(buttonName).className += " active";
}

function sortTableFromData(data, tableID) {
    let table = document.getElementById(tableID);
    let childCount = 0;
    while (table.firstChild && length(table.children)) {
        table.removeChild(table.lastChild);
        childCount += 1;
    }
}


function sortTable(n, element, ignore = 1) {
    var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
    table = document.getElementById(element);
    switching = true;
    // Set the sorting direction to ascending:
    dir = "asc";
    /* Make a loop that will continue until
    no switching has been done: */
    while (switching) {
        // Start by saying: no switching is done:
        switching = false;
        rows = table.rows;
        /* Loop through all table rows (except the
        first, which contains table headers): */
        for (i = ignore; i < (rows.length - 1); i++) {
            // Start by saying there should be no switching:
            shouldSwitch = false;
            /* Get the two elements you want to compare,
            one from current row and one from the next: */
            x = rows[i].getElementsByTagName("TD")[n].innerHTML.toLowerCase();
            x_float = parseFloat(x.replace(/[^\d.-]/g, ''));
            if (!Number.isNaN(x_float)) {
                x = x_float;
            }
            y = rows[i + 1].getElementsByTagName("TD")[n].innerHTML.toLowerCase();
            y_float = parseFloat(y.replace(/[^\d.-]/g, ''));
            if (!Number.isNaN(x_float)) {
                y = y_float;
            }
            /* Check if the two rows should switch place,
            based on the direction, asc or desc: */
            if (dir == "asc") {
                if (x > y) {
                    // If so, mark as a switch and break the loop:
                    shouldSwitch = true;
                    break;
                }
            } else if (dir == "desc") {
                if (x < y) {
                    // If so, mark as a switch and break the loop:
                    shouldSwitch = true;
                    break;
                }
            }
        }
        if (shouldSwitch) {
            /* If a switch has been marked, make the switch
            and mark that a switch has been done: */
            rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
            switching = true;
            // Each time a switch is done, increase this count by 1:
            switchcount++;
        } else {
            /* If no switching has been done AND the direction is "asc",
            set the direction to "desc" and run the while loop again. */
            if (switchcount == 0 && dir == "asc") {
                dir = "desc";
                switching = true;
            }
        }
    }
}

Date.prototype.toDateInputValue = (function () {
    var local = new Date(this);
    local.setMinutes(this.getMinutes() - this.getTimezoneOffset());
    return local.toJSON().slice(0, 10);
});
