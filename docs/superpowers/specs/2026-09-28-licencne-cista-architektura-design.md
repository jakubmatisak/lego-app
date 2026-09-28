# Licenčne čistá architektúra dát a komprimované fotky (plán)

## Kontext

Appka má byť „hlúpa“ bez kľúčov: údaje z cudzích služieb vidí len účet,
ktorý si k službe vložil vlastný kľúč. Dnes sú katalóg aj cenové snímky
spoločné pre celú inštanciu. Účet bez kľúča preto vidí ceny BrickEconomy
stiahnuté cudzím kľúčom a verejné odkazy ich ukazujú anonymom. To je
v rozpore s osobnou licenciou BrickEconomy. Pri Brickset sú podmienky
zdieľania nejasné, preto sa správa rovnako prísne.

Rozhodnutia používateľa (2026-09-28):
- **Kým účet nezadá kľúč (alebo nezapne službu), nevidí z nej nič.**
  - **Brickset a BrickEconomy:** prísne, len to, čo stiahol jeho vlastný
    kľúč (záznam prístupu na set).
  - **Rebrickable:** stačí mať vlastný kľúč Rebrickable. Potom účet vidí
    celý spoločný katalóg, lebo podmienky Rebrickable zdieľanie dovoľujú.
  - **Eurostat a UPCitemdb** kľúč nemajú. Majú prepínač, pre nové účty
    predvolene vypnutý. Kým ho účet nezapne, nič z nich nevidí ani nevolá.
- Údaj sa ukladá **raz**. Viditeľnosť určuje tabuľka prístupov podľa
  odtlačku kľúča, nie kópia dát pre každý kľúč. Dôvod: robustnosť pri
  ~100 používateľoch.
- Vlastné fotky kusov sa komprimujú, **najviac 1 MB** na fotku.
- Licencia kódu MIT (hotové). Licenčné úpravy mimo architektúry sú
  poslednou fázou tohto plánu.

Pracovný postup ako doteraz: TDD, overenie na kópii DB (:8001), commit
po fázach, nasadenie na :8000, na konci nezávislý audit.

## Pravidlo viditeľnosti (jadro návrhu)

- **Vždy viditeľné:** číslo setu a vlastné údaje účtu (kusy, kúpne ceny,
  umiestnenie, poznámky, fotky, ručné ceny). Ručne založené sety a ručne
  priradené čiarové kódy tiež, lebo nepochádzajú zo žiadnej služby.
- **S vlastným kľúčom Rebrickable:** celý spoločný katalóg z Rebrickable
  (názov, rok, séria, dieliky, fotka, členovia sérií, sekcia Figúrky).
  - Bez kľúča ukáže set len „Set {číslo}“ bez fotky a série.
  - Filter Séria ukáže „Bez série“, Figúrky sa skryjú.
- **So zapnutým UPCitemdb:** čiarové kódy, ktoré našlo UPCitemdb.
  - Nový stĺpec `catalog_items.ean_source` (`manual`/`upcitemdb`).
  - Existujúce kódy bez zdroja sa berú ako `upcitemdb`.
- **So zapnutým Eurostatom:** prepočet „V dnešných peniazoch“. Vypnutý
  Eurostat sa správa ako chýbajúci index: sumy ostanú nominálne a reálne
  riadky sa neukážu.
- **Podľa kľúča, prísne na set:** všetko z Brickset (popis, štítky, hodnotenie,
  obľúbenosť, RRP, čiarový kód, retired, galéria, vlny sérií) a z
  BrickEconomy (ceny a história, odhady, rast, retired dátum, podséria,
  číslo figúrky, RRP, čiarový kód).
- Účet vidí údaj zo služby, len keď odtlačok jeho **aktuálneho** kľúča má
  záznam prístupu k tomu setu (alebo vlne). Zmaže kľúč: údaje zmiznú.
  Vloží ho znova: vrátia sa. Nový kľúč začína bez prístupov.
- **Ceny BrickEconomy:** vidí len snímky s `captured_at ≤` časom posledného
  volania svojho kľúča pre ten set. Novšiu cenu stiahnutú cudzím kľúčom
  uvidí až po vlastnom volaní.
- **Ručné ceny** patria len účtu, ktorý ich zadal.
- **Verejné odkazy** nikdy neobsahujú údaje z Brickset ani BrickEconomy.
  So zapnutými sumami len vlastné čísla majiteľa (kúpna cena, ručná cena).

## Fáza 1 – Komprimované fotky (samostatné, nezávislé)

- Pridať závislosť `pillow` (licencia HPND/MIT-CMU, voľná) do
  `backend/pyproject.toml`.
- Nový `services/photo_processing.py::normalize(raw: bytes) -> bytes`:
  - Otvorí obrázok cez Pillow (nahrádza kontrolu magických bajtov
    `MAGIC` v `routers/photos.py`). Pri chybe hodí výnimku a router vráti 415.
  - Nastaví strop `Image.MAX_IMAGE_PIXELS` na 60 MP (ochrana pred
    „dekompresnou bombou“).
  - `ImageOps.exif_transpose` (otočí podľa fotoaparátu), potom RGB.
    Priehľadné PNG dostane biele pozadie.
  - Zmenší na najviac 1600 px na dlhšej strane.
  - Uloží ako JPEG bez EXIF (zmizne GPS), progresívne.
  - Kvalita od 85 po 55. Keď ani potom nie je ≤ 1 MB, rozmery × 0,8
    a znova.
- `config.py`: `photo_max_bytes` = 20 MB (vstup), nové
  `photo_stored_max_bytes` = 1 MB (výstup).
- `routers/photos.py::upload`: načíta najviac 20 MB (inak 413), potom
  `normalize`, uloží `.jpg`, `content_type="image/jpeg"`, skutočné
  `size_bytes`.
- Jednorazová úprava existujúcich fotiek: príkaz v `cli.py`
  (`recompress-photos`), idempotentný. Súbor prepíše na `.jpg`, upraví
  `filename`, `content_type` a `size_bytes`.
- Frontend: `components/PhotosDialog.vue` len text „fotka sa zmenší na
  najviac 1 MB“. `accept` ostáva jpeg/png/webp, pribudne heic, ak ho
  Pillow prečíta. Kód sa inak nemení.
- Testy (`tests/test_api_insights.py` pri fotkách + nový
  `tests/test_photo_processing.py`):
  - 6 MB JPEG → ≤ 1 MB;
  - EXIF s GPS je preč;
  - otočenie podľa EXIF;
  - PNG s priehľadnosťou;
  - súbor nad 20 MB → 413;
  - text namiesto obrázka → 415;
  - `recompress-photos` na existujúcom súbore.

## Fáza 2 – Dátový model a zápis

Nové tabuľky (modely v `models/`, migrácia autogenerate na pracovnej DB):
- `brickset_facts` (PK `catalog_num`): name, year, theme, num_parts,
  num_minifigs, image_url, rrp_eur, is_retired, retired_at, ean,
  description, tags, bs_rating, bs_rating_count, bs_owned_by,
  bs_wanted_by, brickset_id, image_count, images (JSON), fetched_at.
- `brickeconomy_facts` (PK `catalog_num`): name, theme, year, num_parts,
  num_minifigs, rrp_eur, is_retired, retired_at, retired_date, subtheme,
  minifig_no, ean, forecast_2y_eur, forecast_5y_eur, growth_12m_pct,
  growth_last_year_pct, fetched_at.
- `source_access`: provider, fingerprint (16 znakov z
  `services/keys.py::fingerprint`), subject (`catalog_num` alebo
  `wave:{téma}:{rok}`), last_fetched_at, found (bool).
  - Unique (provider, fingerprint, subject), index (fingerprint, provider).
  - Riadok s `found=false` = „pýtali sme sa, služba nič nemá“. Nahrádza
    globálny `brickset_checked_at`.
- `price_snapshots.user_id` (nullable, FK users CASCADE). Vyplnené len pri
  `source="manual"`.

Z `catalog_items` sa odstránia stĺpce len z Brickset alebo BE: description,
tags, bs_*, brickset_checked_at, brickset_id, bs_image_count, bs_images,
forecast_*, growth_*, retired_date, subtheme, minifig_no. Zmiešané stĺpce
(rrp_eur, ean, is_retired, retired_at) ostanú, ale len pre Rebrickable
a ručné údaje.

Zápis, jedno miesto na službu:
- `services/pricing.py`:
  - `store_market(session, data, fingerprint)` ukladá snímky ako doteraz,
    jedenkrát; duplicitu histórie stráži už existujúce `_known_moments`.
  - Potom zapíše alebo posunie `source_access`.
  - `apply_catalog_extras` píše do `brickeconomy_facts`, nie do katalógu.
  - `store_manual(..., user_id)`.
- `services/catalog.py`:
  - `_merge` a `_upsert` rozdelia výsledok: časť z Rebrickable do
    `catalog_items`, časť z Brickset do `brickset_facts` s prístupom.
  - `apply_brickset(session, item, meta, fingerprint)`.
- `services/brickset_extras.py::fill_one`, galéria v
  `routers/catalog.py::get_set_images`, vlny v `services/themes.py::wave`
  a hľadanie kódu v `services/barcode.py`: všetko cez tie isté funkcie
  a všetko zapisuje prístup.
- Riadky katalógu, ktoré vytvoril len Brickset (vlny) alebo BE
  (`routers/prices.py::lookup_price`), dostanú v katalógu len číslo
  a meno „Set {číslo}“. Skutočné údaje sú vo facts, takže účet bez
  kľúča vidí len číslo.
- Prepínače predvolene vypnuté:
  - `capabilities.py::CapSpec` dostane `default_enabled` (False pre
    `upcitemdb.barcode` a `eurostat.inflation`).
  - `services/fetch_policy.py`: `FetchPolicy` pozná aj zoznam `enabled`
    (výslovne zapnuté). `enabled(cap)` = required, alebo (default zapnutá
    a nie je v `disabled`), alebo (default vypnutá a je v `enabled`).
    `parse_settings` a `PUT /auth/me/sources` ho prijmú.
  - Existujúce účty dostanú v migrácii oba prepínače zapnuté, aby sa
    u teba nič nezmenilo; predvolene vypnuté sú len pre nové účty.
- Odtlačok kľúča sa dostane k zápisu cez nové
  `UserKeys.fingerprint(provider)` a `Provider.fingerprint` (verejná
  vlastnosť namiesto `provider._key`).

## Fáza 3 – Čítanie cez jedno miesto

- Nový `services/visibility.py`:
  - `Visibility.load(session, keys, user_id, nums)`: tromi dotazmi načíta
    prístupy a facts pre dané čísla.
  - `vis.view(item) -> CatalogView`: dátová trieda s rovnakými menami
    atribútov ako `CatalogItem`. Základ je Rebrickable, ak má účet kľúč
    Rebrickable alebo ide o ručný set; inak len číslo a „Set {číslo}“.
    Brickset a BE dopĺňajú podľa prístupu, s rovnakými prednosťami ako
    dnes `_merge`.
  - Bez kľúča Rebrickable aj `members_of` a série (`cmf_series`,
    `blind_series`, `filters.py::series_of`) vrátia prázdno: Figúrky sa
    skryjú a kusy sérií sú obyčajné položky s číslom.
  - `vis.ean_visible(item)`: ručný kód vždy, `upcitemdb` len so zapnutým
    prepínačom, kódy z Brickset a BE podľa prístupu.
  - `vis.inflation`: False pri vypnutom Eurostate. `services/inflation.py`
    potom vráti „index chýba“ a nič nestiahne.
  - `vis.snapshot_clause()`: SQL podmienka pre `PriceSnapshot`: BE riadky
    cez join na `source_access` s `captured_at ≤ last_fetched_at`, ručné
    len `user_id = účet`.
  - `vis.price_age_hours(num)`: vek podľa posledného volania vlastného
    kľúča.
  - `Visibility.public(owner)`: bez prístupov, len ručné ceny majiteľa.
- Závislosť `CurrentVisibility` v `auth/deps.py`. Nič mimo tohto modulu
  sa priamo nepýta na facts ani na `price_snapshots`.
- Prepojenie (vzor rovnaký všade: čísla → `Visibility.load` →
  `view`/`snapshot_clause`):
  - `services/portfolio.py::load_snapshots`, `SnapshotIndex`,
    `value_items`, `_apply_forecast`, `average_discount`, breakdown podľa
    podsérie;
  - `services/pricing.py::latest_snapshot` / `snapshot_age_hours`;
  - `routers/prices.py` (get_prices, list_checks, lookup_price,
    refresh_one);
  - `routers/items.py`, `routers/stats.py`, `routers/misc.py`
    (wishlist, export), `routers/categories.py`;
  - `services/filters.py` (tagy, podséria, retired, hodnotenie, rast
    a facets) dostane `CatalogView`;
  - `services/categories.py` (pravidlo na podsériu);
  - `services/wishlist.py`, `services/purchase_fill.py` (RRP len
    viditeľné);
  - `routers/themes.py` / `services/themes.py` (vlny len s prístupom
    `wave:`, inak odhad z názvu ako dnes bez kľúča);
  - `services/barcode.py::find_by_ean` (lokálne hľadanie: `catalog.ean`
    + facts s prístupom);
  - `routers/share.py` cez `Visibility.public`. Z verejných DTO zmizne
    `is_retired`, trhové sumy len z ručných cien.
- Schémy: `CatalogOut` sa skladá z `CatalogView` jednou funkciou
  (`catalog_out(view)`), pole `brickset_checked_at` nahradí
  `brickset_checked` (bool z prístupu). Po zmene `openapi_export`
  a `gen:api`.
- Frontend: API už maskuje, zmeny sú malé.
  - `SetDetailView.vue`: `brickset_checked`.
  - Pri BrickEconomy v `SourceCard.vue` poznámka „Licencia je osobná; kľúč
    v dvoch účtoch = zdieľaná licencia“.
  - Pomlčky pri chýbajúcich údajoch už existujú.

## Fáza 4 – Obnova cien podľa kľúča

- `services/refresh.py::collect_targets` berie vek z
  `vis.price_age_hours`, nie z globálnej snímky. Zmizne tým skryté
  „stiahne sa raz pre dvoch“.
- `_inflight` sa kľúčuje aj odtlačkom: dva kľúče môžu ťahať ten istý set,
  ten istý kľúč nie dvakrát.
- `services/price_misses.py` ostáva spoločný (neúspech nič neprezrádza).
- CLAUDE.md: pravidlo „Jedno volanie na položku“ doplniť o „na kľúč“.

## Fáza 5 – Presun existujúcich dát

- Alembic migrácia (bez kľúčov):
  - skopíruje stĺpce z Brickset a BE z `catalog_items` do facts
    (Brickset podľa `brickset_checked_at`/source, BE podľa prítomnosti
    odhadov alebo BE snímok);
  - zmiešané RRP, EAN a retired dá do facts podľa rovnakého pravidla,
    inak ich nechá v katalógu;
  - ručné snímky priradí majiteľovi setu, pri viacerých majiteľoch ich
    skopíruje každému.
- Prístupy potrebujú odtlačky kľúčov, a tie vedia len pri rozšifrovaní
  (`JWT_SECRET`). Preto nie v migrácii, ale jednorazová úloha pri štarte
  (`services/access_backfill.py`, príznak v `app_settings`):
  - každý účet s kľúčom Brickset alebo BE dostane prístup k setom zo
    svojej Zbierky, Chcem a Overiť cenu;
  - `last_fetched_at` = najnovšia BE snímka setu alebo čas doplnenia
    z Brickset;
  - vlny dostanú všetci držitelia kľúča Brickset.
- Overenie na kópii DB: pred migráciou a po nej musí mať tvoj účet rovnaké
  súčty na Prehľade (investované, hodnota, zisk), rovnaký počet cien
  a popisov. Nový účet bez kľúča nevidí ceny, popisy ani galériu.

## Fáza 6 – Licenčné upratanie

- `backend/tests/fixtures/brickeconomy.py`: skutočné ceny a história
  nahradiť vymyslenými. Upraviť 7 testov v `tests/test_providers.py`,
  ktoré čísla porovnávajú (riadky ~179–354).
- Zmazanie účtu:
  - `DELETE /auth/me` s heslom a admin `DELETE /admin/users/{id}`.
  - Deti sa mažú výslovne, lebo SQLite nemá zapnuté `foreign_keys`:
    kusy, fotky aj súbory, Chcem, odkazy, kategórie, pohľady, importy,
    overenia, ručné snímky, prístupy, api_calls, barcode_misses.
  - Tlačidlo v Nastaveniach → Účet s potvrdením.
### GDPR

- **Prevádzkovateľ:** v Nastaveniach → Aplikácia správca vyplní meno
  (alebo názov) a kontaktný e-mail (`app_settings`). Bez nich stránka
  o súkromí ukáže upozornenie „prevádzkovateľ nevyplnil kontakt“.
- **Zásady ochrany súkromia:** verejná stránka `/sukromie` (SK aj EN),
  odkaz z prihlásenia, registrácie, pätičky a Nastavení.
  - Aké údaje: e-mail, meno, hash hesla, zbierka a ceny, fotky,
    zašifrované kľúče, nastavenia, log volaní služieb (30 dní),
    prihlasovacie tokeny (30 dní).
  - Účel a právny základ: poskytnutie služby, čl. 6 ods. 1 písm. b; log
    volaní a bezpečnosť, oprávnený záujem, písm. f.
  - Doba uchovávania: do zmazania účtu, logy a tokeny 30 dní.
  - Príjemcovia: hosting. Služby, ktoré účet sám pripojí, dostanú len
    čísla setov a čiarové kódy pod jeho vlastným kľúčom, nie osobné
    údaje. Eurostat nedostane nič osobné.
  - Práva: prístup a export, oprava, zmazanie, prenosnosť, námietka,
    sťažnosť na Úrad na ochranu osobných údajov SR.
  - Verzia a dátum textu.
- **Registrácia:** povinné zaškrtnutie „Prečítal(a) som si zásady
  ochrany súkromia“. Nie je to súhlas ako právny základ, len potvrdenie,
  že bol používateľ informovaný.
  - Uloží sa `users.privacy_accepted_at` a `privacy_version`.
  - Pri novej verzii zásad sa po prihlásení ukáže jednorazové oznámenie.
- **Export mojich údajov** (prenosnosť, čl. 20): `GET /auth/me/export`
  vráti ZIP s JSON (profil, kusy, Chcem, kategórie, pohľady, odkazy,
  overenia, ručné ceny, nastavenia bez kľúčov) a s fotkami. Tlačidlo
  v Nastaveniach → Účet, sťahuje sa cez klienta a blob ako CSV.
- **Zmazanie účtu:** viď vyššie. Tlačidlo je vedľa exportu a vopred
  ponúkne export.
- **Fotky bez polohy:** EXIF sa odstraňuje už vo Fáze 1.

### Cookies a úložisko v prehliadači

Appka nepoužíva analytiku, reklamu ani sledovanie.
- **Cookie:** jedine prihlasovacia `refresh` (httpOnly,
  `auth/router.py:55`). Je nevyhnutná.
- **localStorage:** nastavenia, ktoré si používateľ sám zvolil:
  - `lego-theme` (tmavý alebo svetlý režim),
  - `lego-hide-prices` (skryté ceny),
  - `moje-kocky.camera` (zvolená kamera),
  - `moje-kocky.portfolio-range` (rozsah grafu).

Podľa § 109 ods. 8 zákona 452/2021 Z. z. na nevyhnutné úložisko
a úložisko, o ktoré používateľ požiadal, **súhlas netreba**. Namiesto
lišty so súhlasom:
- sekcia „Cookies a úložisko“ na `/sukromie` s tabuľkou (názov, účel,
  doba);
- nenápadný jednorazový riadok na prihlasovacej stránke „Používame len
  nevyhnutné cookies“ s odkazom na zásady (zavretie sa zapamätá
  v localStorage);
- pravidlo do CLAUDE.md: nové cookie alebo úložisko = riadok v tabuľke,
  analytika alebo sledovanie = najprv lišta so súhlasom.

**Obrázky cez vlastný server:** fotky setov sa dnes načítavajú priamo
z Rebrickable a Brickset, takže tie služby vidia IP adresu každého
návštevníka, aj na verejných odkazoch. Riešenie:
- `GET /img?u=…` na serveri stiahne obrázok len zo zoznamu povolených
  hostiteľov (cdn.rebrickable.com, images.brickset.com), bez ukladania
  na disk, s kešom v prehliadači na deň;
- frontend (`SetImage.vue`, `SetGallery.vue`, verejná stránka) ide cez
  neho;
- IP návštevníka potom tretím stranám neodchádza a v zásadách netreba
  prenos IP rozoberať.
- README: sekcia Právne podľa nového stavu; poznámka, že repozitár
  nemá mať „lego“ v názve (premenovanie na GitHube urobí používateľ).
- Mimo kódu (povie sa používateľovi): požiadať Brickset o súhlas pri
  otvorenej verejnej inštancii, prípadne BrickEconomy o súhlas s
  vyrovnávacou pamäťou.

## Overenie

- Backend `uv run pytest`, `ruff check` a `ruff format`. Frontend
  `type-check`, `lint`, `test`, `build-only`.
- Nové testy viditeľnosti (`tests/test_visibility.py`):
  - účet bez kľúča nevidí cenu, popis ani galériu;
  - s kľúčom vidí až po vlastnom volaní;
  - po zmazaní kľúča nie;
  - iný kľúč nie, kým sám nezavolá;
  - snímka novšia než moje volanie je skrytá;
  - ručná cena je súkromná;
  - verejný odkaz nemá BE ani Brickset údaje ani so sumami;
  - obnova: druhý kľúč volá, aj keď prvý dnes volal;
  - riadok vytvorený BE ukáže bez kľúča len číslo;
  - kód z Brickset nenájde účet bez kľúča;
  - bez kľúča Rebrickable len „Set {číslo}“ a žiadne série;
  - kód z UPCitemdb a inflácia až po zapnutí prepínača;
  - nový účet má UPCitemdb a Eurostat vypnuté, existujúci zapnuté.
- GDPR testy:
  - registrácia bez potvrdenia zásad → 422;
  - export obsahuje údaje účtu, ale nie kľúče ani cudzie dáta;
  - zmazanie účtu odstráni všetky jeho riadky aj súbory fotiek;
  - `/img` odmietne hostiteľa mimo zoznamu.
- Na kópii DB (:8001) prejsť dva účty: tvoj s kľúčmi a nový bez kľúčov
  (Prehľad, Zbierka, detail, Overiť cenu, Série, verejný odkaz).
- Porovnať súčty Prehľadu pred a po presune.
- Commit po každej fáze, nasadenie na :8000 a health po poslednej.
- Aktualizovať CLAUDE.md a úplný spec (nový odsek o viditeľnosti).
- Nezávislý audit (opus) celej zmeny, opraviť Critical/Important.
