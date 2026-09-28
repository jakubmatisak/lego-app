# Pravidlá sťahovania a karty služieb (fáza 2)

Stav: implementované 2026-09-27 podľa plánu
`docs/superpowers/plans/2026-09-27-pravidla-stahovania.md`. Časť 3 (index
čiarových kódov a hromadné skenovanie) bude mať vlastný spec.

## Prečo

Cudzie služby majú denné limity (Brickset 100 `getSets`, BrickEconomy
90 z 100, UPCitemdb ~100 na IP). Používateľ chce vidieť a vypnúť každé
volanie, ktoré mu netreba, a pri hromadnej práci (import, skenovanie)
nemíňať limit na detaily, ktoré sa dajú doplniť neskôr. Appka má fungovať
aj bez platených kľúčov a nezobrazovať, čo bez nich nejde.

## Časť 1: brána a schopnosti

**Schopnosť** je pomenované *prečo* jedného druhu volania. Register je
`backend/src/lego_api/capabilities.py` (`Cap` a `CAPABILITIES`):

| schopnosť | služba | do limitu | trieda | dá sa vypnúť |
|---|---|---|---|---|
| `rebrickable.set` | Rebrickable | nie | na požiadanie | nie (bez nej set nevznikne) |
| `rebrickable.series_sync` | Rebrickable | nie | na pozadí | áno |
| `brickset.on_add` | Brickset `getSets` | áno | na požiadanie | áno |
| `brickset.backfill` | Brickset `getSets` | áno | na pozadí | áno |
| `brickset.on_detail` | Brickset `getSets` | áno | na požiadanie | áno |
| `brickset.barcode` | Brickset `getSets` | áno | na požiadanie | áno |
| `brickset.waves` | Brickset `getSets` | áno | na požiadanie | áno |
| `brickset.themes` | Brickset `getThemes`, `getYears` | nie | na požiadanie | áno |
| `brickset.usage` | Brickset `getKeyUsageStats` | nie | interná | nie, nezobrazuje sa |
| `brickeconomy.prices` | BrickEconomy | áno | na pozadí (dávka), na požiadanie (jeden set) | áno |
| `upcitemdb.barcode` | UPCitemdb | áno | na požiadanie | áno |
| `eurostat.inflation` | Eurostat | nie | na požiadanie | áno |

Predvolene je všetko zapnuté, teda appka sa správa ako dnes.

**Brána** (`services/fetch_policy.py`) rozhoduje pred každou požiadavkou:

1. je schopnosť zapnutá v nastaveniach účtu (povinné sú zapnuté vždy);
2. služba s limitom: na požiadanie smie až po limit, **na pozadí** len kým
   ostáva viac než **rezerva** (predvolene Brickset 20, BrickEconomy 0).

Zablokované volanie neodíde. Zdroj sa správa, ako keby nemal kľúč (vráti
nič), appka nespadne. Kde to používateľ potrebuje vedieť (čiarový kód),
povie rozhranie prečo.

**Zdroj bez schopnosti nezavolá nič.** Verejné metódy zdrojov berú
schopnosť ako povinný parameter (`cap=`); vo vnútri ju odovzdajú
jedinému miestu, ktoré volá von (`_get`, `_get_sets`, `_plain`,
`get_market`, `lookup`, `fetch`). Tam je brána.

**Pravidlá cestujú s kľúčmi.** `UserKeys` dostane pole `policy`
(`FetchPolicy`); `keys_of(user)` ho naplní z účtu. Kľúče už dnes idú do
všetkých zdrojov aj úloh na pozadí, pravidlá teda idú s nimi. Zdroje sa
vytvárajú cez `…Provider.for_user(settings, keys)`.

**História volaní nesie schopnosť.** `api_log.record(..., cap=)` zapíše
účel ako kľúč schopnosti. Mapa `ENDPOINT_PURPOSES` podľa mien trás zanikne;
závislosť prihláseného používateľa a úlohy na pozadí nastavujú už len
používateľa (`api_log.set_user`). Staré záznamy si svoje účely nechajú.

**Uloženie:** `users.fetch_settings` (JSON, `server_default '{}'`):
`{"disabled": [...], "reserve": {"brickset": 20}, "price_batch": 40}`.
Neznáme kľúče sa pri uložení odmietnu. Strop dávky cien je
`min(price_batch, PRICE_REFRESH_BUDGET)`.

## Časť 2: Nastavenia → Dáta, karty služieb

Záložka **Dáta** v Nastaveniach ostáva; jej obsah nahradia karty služieb
v poradí úrovní: Rebrickable, Brickset, BrickEconomy, UPCitemdb, Eurostat.

Karta:

1. **Hlavička:** názov, štítok zadarmo / platené, stav kľúča (zadaný,
   chýba), dnešné volania a limit.
2. **Kľúč:** pole ako dnes a odkaz, kde ho získať (Rebrickable, Brickset,
   BrickEconomy). UPCitemdb a Eurostat kľúč nemajú.
3. **Čo odomkne:** zoznam funkcií. Bez kľúča je karta sivá a zoznam
   hovorí, čo by si získal.
4. **Prepínače** (len keď služba funguje): jeden na schopnosť, vysvetlivka
   (koľko stojí volaní, do ktorého limitu sa ráta, čo stratíš) a riadok
   „prinesie: …“ s údajmi, ktoré to isté volanie donesie.
5. **Rezerva** pri Brickset a BrickEconomy, **dávka** pri BrickEconomy.

API: `GET /auth/me/sources`, `PUT /auth/me/sources`. `ApiKeysOut` pridá
`capabilities`: zoznam schopností, ktoré účet práve smie používať (služba
má kľúč alebo ho netreba, a schopnosť je zapnutá). Frontend z neho má
`auth.can(cap)`.

**Mimo Nastavení sa skryje, čo nejde:**

- tlačidlo obnovy cien bez `brickeconomy.prices`;
- Témy v ponuke bez `brickset.themes`;
- Prehľad: dlaždice a graf trhovej hodnoty bez `brickeconomy.prices`,
  pokiaľ nie sú ručné ceny (trhová hodnota > 0);
- Zbierka: skupina Odhad rastu bez `brickeconomy.prices`; Hodnotenie sa
  skrýva už dnes, keď nemá dáta;
- dopĺňanie Brickset pri otvorení Zbierky bez `brickset.backfill`,
  v detaile setu bez `brickset.on_detail`.

## Testy

- Brána: vypnutá schopnosť, povinná sa vypnúť nedá, rezerva pri pozadí,
  na požiadanie až po limit.
- Každý zdroj: pri vypnutej schopnosti nejde žiadna požiadavka (`respx`,
  `assert_all_called=False`, nula volaní).
- História: záznam nesie kľúč schopnosti.
- API zdrojov: čítanie, uloženie, odmietnutie neznámeho kľúča a vypnutia
  povinnej schopnosti; `capabilities` v `ApiKeysOut`.
- Frontend: `auth.can`, karty sa kreslia zo zoznamu služieb.
