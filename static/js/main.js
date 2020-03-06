function showCompany(ticker){
    window.location.href = "/screener/" + ticker;
};

function filterCountry(){
    var e = document.getElementById("country");
    var country = e.options[e.selectedIndex].value;
    window.location.href = "/?country=" + country;
};