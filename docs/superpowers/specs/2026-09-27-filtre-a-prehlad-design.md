# Filtre, zoradenie, hromadná úprava a rozsah Prehľadu

Stav: body 1–11 implementované 2026-09-27 (plány `docs/superpowers/plans/2026-09-27-filtre-1-zoradenie-a-filtre.md` a `2026-09-27-filtre-2-tabulka-hromadna-uprava-a-sekcie.md`). Body 1–11 zo zoznamu vylepšení.
Bod 12 (neúspešný čiarový kód si zapamätať) patrí do specu hromadného
skenovania, lebo ho rieši index kódov.

## Prečo

Po importe alebo hromadnom skenovaní bude v zbierke stovky až tisícky
kusov. Dnešná Zbierka má bohatý panel filtrov, ale:

- **zoradenie má len štyri voľby a v zoskupenom zobrazení nefunguje vôbec**
  (chyba: `GET /items/grouped` ignoruje `sort` a vždy radí podľa zisku);
- chýbajú rozsahy (dátum a cena kúpy, hodnota), hľadanie nepozná
  diakritiku ani poznámku;
- kusy sa dajú meniť len po jednom;
- Chcem, Témy a Figúrky majú filtrov málo alebo žiadne;
- Prehľad ukazuje vždy celú zbierku.

## Zásady

- **Jedno miesto pre filtre, jedno pre zoradenie.** Filtre ostávajú
  v `services/filters.py` (`ItemFilter`, `PREDICATES`, `facets()`).
  Zoradenie dostane vlastný register `services/sorting.py`, ktorý používa
  zoznam kusov, zoskupený zoznam, tabuľka aj export. Router nič neradí sám.
- **Filter Zbierky je jazyk celej appky.** Ten istý `ItemFilter` berú aj
  štatistiky, hromadná úprava aj rozsah Prehľadu, takže „čo vidím
  v Zbierke“ a „čo počíta Prehľad“ sa nerozídu.
- **Panel je riadený dátami.** Nová skupina filtrov je záznam v `facets()`
  a riadok `FilterOption`, nie nový kus šablóny.
- Poradie volieb vo filtri ostáva stabilné (podľa celej zbierky), vybrané
  sú červené.

## 1. Zoradenie

Voľby, každá aj s opačným smerom (tlačidlo ↑↓ vedľa výberu):

| kľúč | podľa čoho | predvolený smer |
|---|---|---|
| `profit` | nerealizovaný zisk v € | zostupne |
| `profit_pct` | zisk v % | zostupne |
| `cagr` | ročný výnos | zostupne |
| `value` | trhová hodnota | zostupne |
| `purchase` | kúpna cena | zostupne |
| `purchased` | dátum kúpy | najnovšie |
| `year` | rok vydania | najnovšie |
| `parts` | počet dielikov | zostupne |
| `name` | názov | A → Z |
| `recent` | naposledy pridané | najnovšie |

- API: `sort` a `dir=asc|desc`; v adrese len mimo predvolených hodnôt.
- **Prázdne hodnoty (bez ceny, bez dátumu) sú vždy na konci**, v oboch
  smeroch. Inak by pri „zisk vzostupne“ boli navrchu kusy bez ceny.
- Zoskupená karta sa radí podľa súčtu svojich kusov (zisk, hodnota,
  kúpna cena), podľa najnovšieho kusu (dátum kúpy, pridané), inak podľa
  setu (rok, dieliky, názov).

## 2. Rozsahy od–do

Nová sekcia panelu **Kúpa a hodnota**:

- dátum kúpy od–do (`bought_from`, `bought_to`), cez `DateField`;
- kúpna cena za kus od–do (`price_min`, `price_max`);
- trhová hodnota za kus od–do (`value_min`, `value_max`); kus bez ceny do
  rozsahu hodnoty nepatrí.

`facets()` vráti hranice (najmenšia a najväčšia hodnota v zbierke) ako
zástupný text polí, rovnako ako dnes pri roku vydania.

## 3. Nové filtre z údajov, ktoré už máme

| skupina | hodnoty | zdroj |
|---|---|---|
| Kde kúpené | už použité obchody | `purchase_place` |
| Kanál predaja | Aukro, Bazoš… (len pri predaných) | `sold_via` |
| Hodnotenie | aspoň 3,5 / 4 / 4,5 | Brickset `bs_rating` |
| Rast hodnoty | rastie / klesá / bez odhadu | BrickEconomy `growth_12m_pct` |
| Pôvod ceny | presná / odvodená (≈) / ručná / bez ceny / staršia ako 30 dní | snímky |
| Stiahnuté | za posledných 12 mesiacov | `retired_date` |

Existujúci filter „cena“ (zisk, strata, bez ceny) ostáva; „pôvod ceny“ je
nová skupina, lebo odpovedá na inú otázku (dá sa tej sume veriť?).

## 4. Hľadanie

- Bez ohľadu na diakritiku a veľkosť písmen („hradna“ nájde „Hradná“).
  Normalizuje sa hľadaný text aj prehľadávané polia (NFKD, bez znamienok).
- Prehľadáva: názov, číslo, tému, podtému, umiestnenie, kde kúpené,
  poznámku kusu a štítky.
- Viac slov = všetky musia sedieť („technic 2024“).

## 5. Filter „z importu“

- Skupina **Import** v paneli: posledné importy (súbor, dátum, počet kusov).
- Parameter `import` (id importu, opakovateľný), predikát cez
  `import_batch_id`.
- Po potvrdení importu vedie tlačidlo „Otvoriť Zbierku“ rovno s týmto
  filtrom. Neskôr ho použije aj hromadné skenovanie (sken je tiež import).

## 6. Hromadná úprava

- V Zbierke tlačidlo **Vybrať**. Karty a riadky dostanú začiarkávatko, lišta
  dole ukáže počet vybraných a akcie. „Vybrať všetko“ vyberie celý výsledok
  filtra, nielen to, čo je na obrazovke.
- Akcie: umiestnenie, zoznam, stav, pridať alebo odobrať príznak, zaradiť
  do kategórie alebo z nej vyradiť.
- Výber sa pošle ako zoznam kusov alebo ako filter:
  `POST /items/bulk-update { item_ids | filter, changes }`. Server zmení
  všetko v jednej transakcii a vráti počet zmenených kusov.
- Vybraná zoskupená karta znamená všetky jej **vlastnené** kusy; predané
  sa hromadne nemenia.
- Pred uložením potvrdenie „Zmeniť umiestnenie 143 kusov na Povala?“.
  Kategória visí na sete, takže sa zaradí set, nie kus.

## 7. Zobrazenie tabuľkou

- Prepínač **Karty | Tabuľka** vedľa zoskupenia, pamätá sa pri účte.
- Stĺpce: fotka, číslo, názov, téma, rok, kusy, stav, umiestnenie, kúpené,
  hodnota, zisk, %, ročne. Klik na hlavičku stĺpca zoradí (register z bodu 1,
  radí server).
- `v-data-table-virtual`: aj 1500 riadkov sa posúva plynulo, stránka sa
  neláme. Pri zoskupení je riadok set alebo séria, pri „každý kus“ kus.
- Bez ceny pomlčka, odvodená cena so znakom ≈, rovnako ako na karte.

## 8. Chcem

- Zoradenie: blízkosť k cieľovej cene (v %), trhová cena, cieľová cena,
  názov, téma, pridané.
- Filtre (čipy): cieľ dosiahnutý, stiahnuté z predaja, bez trhovej ceny,
  hľadanie podľa názvu a čísla.
- Radí a filtruje server (`GET /wishlist?sort=&reached=&retired=&q=`),
  aby to bolo rovnaké ako v Zbierke.

## 9. Rozsah Prehľadu

- Hore na Prehľade výber **Rozsah**: celá zbierka, uložený pohľad,
  kategória, zoznam, téma. Pamätá sa pri účte.
- Štatistiky (`summary`, `timeline`, `breakdown`, `sales`, `movers`,
  `series`) berú ten istý `ItemFilter` ako Zbierka. Uložený pohľad je
  presne uložený filter Zbierky, nič nové.
- Pri zapnutom rozsahu je nad dlaždicami viditeľný štítok „Rozsah:
  Investícia“ s krížikom, nech je jasné, že čísla nie sú za celú zbierku.
- Čísla v ponuke (počty setov, figúrok) ostávajú za celú zbierku.

## 10. Témy

- Zoradenie: počet mojich setov, úplnosť (mám / všetkých v téme), názov.
- Filtre: sledované, s mojimi setmi, nekompletné.

## 11. Figúrky

- Filter **skoro kompletné** (chýbajú najviac 2) a zoradenie **najmenej
  chýba**. Dopĺňa dnešné filtre a zoradenia v `MinifigsView`.

## Volania

Nič z toho nevolá cudzie služby. Všetko sa počíta z databázy.

## Poradie implementácie

1. **Backend filtrov a zoradenia** (body 1–5): `sorting.py`, nové polia
   `ItemFilter`, predikáty, `facets()`, oprava zoradenia zoskupeného
   zoznamu. Testy pre každý predikát a každé zoradenie, vrátane prázdnych
   hodnôt na konci.
2. **Panel a zoradenie vo Zbierke**: nové sekcie, smer zoradenia.
3. **Tabuľka** (bod 7).
4. **Hromadná úprava** (bod 6): endpoint, výber, lišta akcií.
5. **Chcem, Témy, Figúrky** (body 8, 10, 11).
6. **Rozsah Prehľadu** (bod 9): štatistiky s `ItemFilter`, výber rozsahu.

Každý krok sa overí na kópii databázy, commitne a nasadí zvlášť.

## Testy

- Každý nový predikát: zahrnie a vylúči správne kusy; hodnota „nič“.
- Každé zoradenie v oboch smeroch, prázdne hodnoty na konci, zoskupený
  zoznam sa radí rovnako ako zoznam kusov.
- Hľadanie bez diakritiky a viacerými slovami.
- Hromadná úprava: podľa zoznamu aj podľa filtra, predané kusy sa nemenia,
  iný účet sa nedotkne.
- Štatistiky s filtrom: súčty sedia so súčtami výberu v Zbierke.
