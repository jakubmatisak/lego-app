"""Odpovede BrickEconomy so štruktúrou reálneho API, aby testy nešli po sieti.

Polia a tvar sú ako v skutočnej odpovedi, ceny, história, odhady a rast sú
vymyslené: údaje BrickEconomy sa podľa ich podmienok nesmú šíriť.

Podstatné je, že jedna odpoveď nesie cenu novej aj použitej položky a k tomu
históriu, takže netreba volať štyrikrát. Set, ktorý je stále v predaji, nemá
ani použitú cenu, ani históriu, ani dátum stiahnutia z predaja.
"""

# GET /api/v1/set/10236-1?currency=EUR
SET_EWOK_VILLAGE = {
    "data": {
        "retired": True,
        "set_number": "10236-1",
        "name": "Ewok Village",
        "url": "https://www.brickeconomy.com/set/10236-1/lego-star-wars-ewok-village",
        "theme": "Star Wars",
        "subtheme": "Ultimate Collector Series",
        "year": 2013,
        "pieces_count": 1990,
        "minifigs_count": 17,
        "minifigs": ["sw0011a", "sw0236", "sw0338"],
        "availability": "exclusive",
        "retail_price_us": 249.99,
        "retail_price_uk": 199.99,
        "retail_price_eu": 249.99,
        "ean": "0612085845430",
        "released_date": "2013-09-01",
        "retired_date": "2016-11-29",
        "current_value_new": 700.00,
        "current_value_used": 500.00,
        "current_value_used_low": 450.00,
        "current_value_used_high": 600.00,
        "forecast_value_new_2_years": 800.00,
        "forecast_value_new_5_years": 1000.00,
        "rolling_growth_lastyear": 5.00,
        "rolling_growth_12months": 4.00,
        "price_events_new": [
            {"date": "2026-09-03", "value": 700.00},
            {"date": "2026-08-15", "value": 690.00},
            {"date": "2026-08-03", "value": 695.00},
            {"date": "2026-07-23", "value": 710.00},
        ],
        "price_events_used": [
            {"date": "2026-08-17", "value": 500.00},
            {"date": "2026-07-25", "value": 495.00},
            {"date": "2026-06-18", "value": 500.00},
        ],
        "currency": "EUR",
    }
}

# GET /api/v1/set/10294-1?currency=EUR
# Set v predaji: žiadna použitá cena, žiadna história, žiadne stiahnutie.
SET_TITANIC = {
    "data": {
        "set_number": "10294-1",
        "name": "Titanic",
        "theme": "Icons",
        "year": 2021,
        "pieces_count": 9090,
        "availability": "exclusive",
        "retail_price_us": 679.99,
        "retail_price_eu": 679.99,
        "released_date": "2021-11-08",
        "current_value_new": 650.00,
        "forecast_value_new_2_years": 720.00,
        "forecast_value_new_5_years": 820.00,
        "currency": "EUR",
    }
}

# GET /api/v1/set/71046-1?currency=EUR
# Člen zberateľskej série. V ``minifigs`` je číslo samotnej figúrky.
SET_CMF_MEMBER = {
    "data": {
        "retired": True,
        "set_number": "71046-1",
        "name": "Spacewalking Astronaut",
        "theme": "Minifigure Series",
        "subtheme": "Series 26 Space",
        "year": 2024,
        "pieces_count": 16,
        "minifigs_count": 1,
        "minifigs": ["col436"],
        "availability": "retail",
        "retail_price_eu": 3.99,
        "released_date": "2024-05-01",
        "retired_date": "2024-11-01",
        "current_value_new": 10.00,
        "current_value_used": 8.00,
        "current_value_used_low": 7.00,
        "current_value_used_high": 9.00,
        "price_events_new": [
            {"date": "2026-09-14", "value": 10.00},
            {"date": "2026-09-01", "value": 9.00},
        ],
        "currency": "EUR",
    }
}

# Neznáme číslo. Endpoint ``minifig`` odpovedá na nepoznané číslo aj 400.
NOT_FOUND = {"error": {"code": "NotFoundError", "message": "not found"}}

QUOTA_EXCEEDED = {"error": {"code": "QuotaExceededError", "message": "daily quota exceeded"}}
