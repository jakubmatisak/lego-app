# Fáza 3: skenovanie čítačkou, pamäť formulára, oznámenia a doplnená kúpna cena

Stav: implementované 2026-09-27. Schválené (A áno bez indexu, B áno,
C áno so zvyšovaním počtu pri rovnakom kóde, D áno, E áno). Plán:
`docs/superpowers/plans/2026-09-27-faza-3-skenovanie-a-oznamenia.md`.

## Prečo

Prvé naplnenie zbierky je stovky krabíc za sebou. Doma je ručná čítačka
Honeywell MS5145 v režime klávesnice. Pridávanie má ísť tak, že používateľ
len skenuje. Formulár si pamätá, kam kusy ukladá. Každé uloženie
a každá chyba sa ohlási oznámením. Kúpnu cenu dopĺňať netreba, keď stačí
odporúčaná.

## A. Pamäť neúspešných kódov

Kód, ktorý nikto nepoznal, sa pri každom skene znova pýtal Bricksetu
a UPCitemdb, a oba majú denný limit. Neúspech sa teraz zapamätá.

- Tabuľka `barcode_misses`: `user_id`, `ean`, `outcome` (`not_found` alebo
  `no_set_number`), `product_title`, `checked_at`. Unikátne je
  (`user_id`, `ean`). Neúspech sa pamätá pri účte, lebo Brickset hľadá
  pod kľúčom účtu: čo nenašiel jeden bez kľúča, môže nájsť druhý s kľúčom.
- `find_by_ean` najprv pozrie katalóg (ako dnes). Potom pozrie neúspech
  mladší než **30 dní**: ak je, vráti ho bez volania von a s `cached=true`.
  Až potom ide na Brickset a UPCitemdb.
- Zapisujú sa len `not_found` a `no_set_number`. `limit` a `disabled` sú
  dočasné, tie sa nepamätajú.
- Nájdený kód svoj neúspech zmaže.
- `GET /catalog/by-ean/{code}?retry=true` pamäť obíde („Skúsiť znova“).
- Ručné priradenie kódu (`PUT /catalog/{num}/ean`) zmaže neúspechy toho
  kódu všetkým účtom, lebo kód je odteraz v katalógu.
- `EanLookupOut` dostane `cached: bool` a `checked_at`. Rozhranie pri
  zapamätanom neúspechu povie, kedy sa kód hľadal, a ponúkne tlačidlo
  „Skúsiť znova“.

Index čiarových kódov (hromadné sťahovanie kódov dopredu) sa nerobí.

## B. Pamäť formulára

Nastavenia → nová záložka **Formuláre**, karta s piatimi prepínačmi:
umiestnenie, stav, zoznam (účel), kde kúpené, dátum kúpy. Predvolene sú
všetky vypnuté a formulár sa správa ako doteraz: dnešný dátum, nové
v krabici, prázdne polia.

- Uloženie: `users.preferences` pod kľúčom `form`:
  `{"remember": {"location": true, …}, "last": {"location": "Povala", …}}`.
  Backend kľúč pridá do `PREFERENCE_KEYS`.
- Zapnuté pole sa predvyplní poslednou uloženou hodnotou. Vypnuté pole
  ostane predvolené.
- „Posledná hodnota“ sa zapíše po každom úspešnom uložení vo formulároch
  Pridať set, Kúpil som (`PurchaseDialog`) a Mám všetky
  (`SeriesPurchaseDialog`, ten nemá zoznam) a pri automatickom uložení po
  skene. Zapisujú sa všetky polia, aj vypnuté, aby po zapnutí prepínača
  bolo čo predvyplniť.
- Logika je v `composables/useFormMemory.ts`: čisté funkcie
  `initialForm(pref, today)` a `rememberForm(pref, values)` plus tenký
  obal nad `useProfileStore`.

## C. Skenovanie odkiaľkoľvek

Čítačka v režime klávesnice funguje na každej obrazovke po prihlásení.

- **Web Serial sa odstraňuje celý.** Používateľ ho nepoužíva, čítačka ide
  ako klávesnica. Z appky zmizne sériová časť `stores/scanner.ts`,
  tlačidlo v `ScannerConnect.vue` (ostane len nápoveda „stačí skenovať“),
  `createLineSplitter`, texty `scan.serial*`, balík `@types/w3c-web-serial`
  a odkaz v `env.d.ts`. Zmienky v dokumentácii sa opravia.
- **Globálny odberateľ.** `AppLayout` sa prihlási na skeny natrvalo.
  Skeny dostáva posledný prihlásený (`handlers.at(-1)`), takže kým je
  otvorené Pridať set, dostáva ich ono. Inak layout prejde na
  `add-set?code=…`.
- **Pridať set** pri otvorení s `?code=` kód vyhľadá a parameter z adresy
  odstráni (`router.replace`), aby obnovenie stránky nehľadalo znova.
- **Sken na Pridať set.** Skeny sa spracúvajú po jednom, v poradí
  príchodu. O každom rozhodne čistá funkcia
  `decideScan(current, code)` v `scanner/scanFlow.ts`:
  - **rovnaký kód** ako práve načítaný a ešte neuložený set → **počet + 1**.
    Pri sérii sa formulár prepne na nerozbalený sáčok a zvýši sa počet
    sáčkov;
  - **iný kód**, keď je načítaný neuložený set → **automatické uloženie**
    toho, čo je vo formulári, a načítanie nového kódu. Uloží sa presne to,
    čo formulár ukazuje: pole ceny je obyčajne prázdne, teda „bez ceny“,
    ale vpísaná cena sa nezahodí. Séria bez vybraných figúrok sa uložiť
    nedá. Vtedy príde varovanie, že sa neuložila, a načíta sa nový kód;
  - **inak** (nič nenačítané, alebo set sa nenašiel) → len vyhľadanie.
- Automatické uloženie ohlási oznámenie „Uložené: 42233 Mighty Machines
  ×2“ s tlačidlom **Späť**. Späť zmaže práve vytvorené kusy
  (`DELETE /items/{id}` pre id z odpovede `POST /items` alebo
  `/items/bulk`) a ohlási, že sa vrátili.
- Po automatickom uložení sa vynulujú polia viazané na kus: počet 1,
  cena, poznámka, výber figúrok, sáčok. Stav, umiestnenie, zoznam, kde
  kúpené, dátum a čipy ostanú, lebo ďalšia krabica býva z tej istej kopy.
- Uloženie tlačidlom ostáva ako dnes (a prejde do Zbierky), len navyše
  ohlási „Pridané do zbierky“.
- Uloženie aj automatické uloženie je jedna funkcia `saveCurrent()`, ktorá
  vráti vytvorené kusy. Priradenie neznámeho kódu (`pendingEan`) a kategórie
  robí tiež ona.

## D. Oznámenia v celej appke

- `stores/notify.ts`: fronta správ pre `<v-snackbar-queue>`, ktorá je raz
  v `AppLayout` (a v `LoginView`/verejnej stránke nie je, tam sa nič
  neukladá). API: `success(text, action?)`, `error(text)`, `info(text)`.
  Úspech zmizne po 3 s, chyba po 6 s, správa s tlačidlom po 8 s.
  Akcia je `{ label, run }`. Fronta ukáže naraz najviac tri správy.
- Každá správa má zatváracie tlačidlo. Akciu kreslí slot `actions`
  fronty: správa nesie `data-notice` s id a store k nemu drží akciu.
  Po zatvorení správy (`onDismiss`) akciu zabudne.
- Oznámenie dostane každé pridanie, úprava a zmazanie v appke:
  - pridať set a ručný katalóg;
  - Kúpil som a Mám všetky;
  - Chcem (pridať, odobrať);
  - kus v detaile (uložiť, zmazať, ručná cena);
  - predaj, vrátenie predaja, zmazanie a úprava v store zbierky;
  - kategórie (uložiť, zmazať, členstvo);
  - fotky (nahrať, zmazať);
  - uložené pohľady (uložiť, zmazať);
  - Nastavenia (odkazy, používatelia, registrácia, profil, kľúče);
  - import (potvrdiť, vrátiť, zahodiť).
  Chyby, ktoré sa doteraz zapisovali do `collection.error`
  a `filters.error` a nikde sa neukazovali, idú do oznámení.
- Lokálne snackbary (`SettingsView`, `ExportCsvButton`) nahradí store.
- Chyby, ktoré patria k poľu vo formulári (napríklad zlý kód v dialógu),
  ostávajú pri poli. Oznámenie ich nenahrádza, len výsledok akcie.

## E. Kúpna cena doplnená automaticky

- Karta BrickEconomy dostane prepínač **„Doplniť kúpnu cenu
  z odporúčanej“**, predvolene vypnutý. Uloženie
  `users.fetch_settings.auto_purchase_price` (bool), `FetchPolicy`
  pole `auto_purchase_price`, `PUT /auth/me/sources` ho prijme, zdroj
  BrickEconomy v `GET /auth/me/sources` ho vráti.
- Nový stĺpec `collection_items.purchase_price_auto` (bool, predvolene
  false), v `ItemOut` rovnako.
- **Kedy:** pri obnove cien, keď je prepínač zapnutý. Dopĺňajú sa len
  vlastnené kusy toho účtu, ktoré kúpnu cenu nemajú.
  - Kus, ktorého položka sa v tejto obnove stiahla, dostane odporúčanú
    cenu z odpovede BrickEconomy (`retail_price_eu`). Keď ju odpoveď
    nemá, berie sa `catalog.rrp_eur` (Brickset alebo skorší BrickEconomy).
  - Na konci obnovy sa zvyšné kusy bez ceny doplnia z `catalog.rrp_eur`.
    Nestojí to volanie, takže sa to stane aj pri kusoch s čerstvou cenou,
    ktoré obnova preskočila, a aj keď je kvóta minutá.
  - Pri obnove jedného setu z detailu sa to týka len kusov toho setu.
- Doplnený kus má `purchase_price_auto=true`. Ručná zmena kúpnej ceny
  (`PATCH /items/{id}` s `purchase_price_eur`) príznak zruší.
- **Označenie:** pri kúpnej cene ikona `mdi-auto-fix` s popisom „kúpna
  cena doplnená automaticky z odporúčanej“ na karte setu, v zozname kusov
  v detaile a v dialógu kusu.
- **Filter:** nová skupina **Kúpna cena**: zadaná, doplnená automaticky,
  chýba (`purchase=manual|auto|none`). Je to jeden záznam v `ItemFilter`,
  jeden predikát a jedna skupina vo `facets()`.
- Pravidlá zisku ostávajú. Doplnená cena je cena ako každá iná, len je
  viditeľne označená.

## Testy

- A: zapamätaný neúspech nejde von (nula volaní `respx`); po 30 dňoch áno;
  `retry` pamäť obíde; `limit` sa nepamätá; nájdený kód neúspech zmaže;
  ručné priradenie ho zmaže; iný účet má vlastnú pamäť.
- B: `initialForm` pri vypnutých prepínačoch dá predvolené hodnoty, pri
  zapnutých posledné; `rememberForm` zapíše všetky polia.
- C: `decideScan` pre rovnaký kód, iný kód s neuloženým setom a prázdny
  stav; skenovacie odberanie bez sériovej časti (`codes.spec.ts` bez
  `createLineSplitter`).
- D: store: farby a časy, akcia sa zavolá a po zatvorení zabudne.
- E: obnova so zapnutým prepínačom doplní cenu z odpovede, bez nej
  z katalógu; vypnutý prepínač nedoplní nič; kus s cenou ostane; predaný
  ostane; iný účet ostane; ručná zmena príznak zruší; filter
  `purchase=auto`; nastavenia sa dajú uložiť a prečítať.
