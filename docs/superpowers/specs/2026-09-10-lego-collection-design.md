# Moje kocky: úplný spec aplikácie

Stav k 2026-09-27. Spísané spätne z pôvodného plánu (2026-09-10), jeho
doplnku o BrickEconomy (2026-09-15), z kódu a z rozhodnutí počas vývoja.
Popisuje, čo appka robí, ako a prečo. Pri každej väčšej zmene sa má
upraviť aj tento súbor.

Tento dokument a CLAUDE.md si rozdeľujú úlohy takto:

- **CLAUDE.md** je pracovný ťahák: príkazy a pravidlá, ktoré sa ľahko
  porušia.
- **Tento spec** opisuje celok: funkcie, dáta, rozhrania, rozhodnutia
  a to, čo sme zamietli.
- **Nové väčšie funkcie** majú vlastný spec vedľa, v tvare
  `RRRR-MM-DD-tema-design.md`. Po dokončení sa ich podstata prenesie sem.

Obsah:

1. Účel a publikum
2. Architektúra a nasadenie
3. Účty, prihlásenie a kľúče
4. Zdroje dát a ich limity
5. Dátový model
6. Výpočty (hodnota, zisk, výnos, inflácia, odhad)
7. Ceny: odkiaľ, kedy a za koľko volaní
8. Katalóg, série a čiarové kódy
9. Obrazovky
10. API
11. Pravidlá rozhrania
12. Zamietnuté a odložené
13. Testovanie a prevádzka

---

## 1. Účel a publikum

Moje kocky evidujú LEGO zbierku: čo mám, koľko som za to dal, koľko to má
dnes hodnotu, čo som predal a za koľko, a čo mi chýba. Používa ju
používateľ a jeho otec (zberateľ), prípadne pár známych. Každý účet má
vlastnú zbierku, katalóg setov je spoločný.

Nie je to verejný produkt ani obchod. Z toho vyplývajú štyri veci:

- **Registrácia je zatvorená.** Otvára ju správca v appke.
- **Limity cudzích služieb sú skutočné obmedzenie.** Kvóty sa neriešia
  platením, ale šetrením. Každá funkcia, ktorá siaha na ceny, musí vedieť,
  koľko stojí volaní.
- **Škálovanie netreba.** SQLite a jeden proces uvicornu stačia, zámky
  a medzipamäte sú v pamäti procesu.
- **Súkromie je prvoradé.** Fotky, ceny a kľúče sú osobné. Zdieľanie je
  len cez výslovný odkaz a sumy v ňom sú voliteľné.

---

## 2. Architektúra a nasadenie

### Zásobník

| vrstva | technológia |
|---|---|
| backend | Python 3.13, FastAPI, SQLAlchemy 2 (async, aiosqlite), Alembic, Pydantic 2, httpx, argon2-cffi, PyJWT |
| frontend | Vue 3, Vuetify 4, TypeScript, Pinia, vue-router, vue-i18n, Chart.js (s pluginom na zoom), ZXing wasm |
| typy API | `openapi-typescript` a `openapi-fetch`, generované z OpenAPI backendu |
| správa balíkov | uv (Python), npm (Node) |
| testy | pytest, respx, ruff; vue-tsc, ESLint, Vitest |

### Štruktúra repozitára

```
backend/src/lego_api/
  main.py            aplikácia, routre, servovanie SPA (index.html bez keša)
  config.py          Settings z prostredia (.env)
  db.py              engine a session
  api_log.py         zápis volaní cudzích služieb
  ean.py             normalizácia čiarového kódu
  auth/              heslá, JWT, závislosti, router /auth
  models/            tabuľky SQLAlchemy
  schemas/           DTO (Pydantic), typ Money
  routers/           trasy API
  services/          logika (portfólio, ceny, katalóg, filtre, série, …)
  providers/         klienti cudzích služieb
backend/alembic/     migrácie
backend/tests/       pytest a fixtúry s reálnymi odpoveďami
frontend/src/
  api/               generovaná schéma, klient, aliasy typov
  views/             obrazovky
  components/        vlastné komponenty (treba ich importovať)
  stores/            Pinia (auth, collection, filters, prices, preferences)
  layouts/           rám appky s ponukou a hornou lištou
  locales/           sk.json, en.json
  plugins/           Vuetify, i18n (slovenské množné čísla)
  utils/format.ts    formát súm, percent a dátumov
docs/superpowers/specs/  tieto dokumenty
```

### Nasadenie

- **Obraz:** jeden Docker obraz s viacstupňovým zostavením. Node zostaví
  frontend a výsledný Python obraz ho servuje spolu s API.
- **Kontajner:** `docker compose up -d --build`, port 8000,
  `restart: unless-stopped`. Po reštarte počítača nabehne sám, ak Docker
  Desktop štartuje so systémom.
- **Dáta:** zväzok `./data:/app/data` drží `lego.db` aj `photos/`.
  Obraz dáta nenesie, takže nové nasadenie ich nezmaže.
- **Migrácie:** Alembic ich spustí pri štarte kontajnera. Keď migrácia
  niečo zmení (revízia v `alembic_version` nie je head), alebo nad
  databázou naposledy bežala iná verzia appky (aktualizácia aj návrat na
  staršiu, aj bez zmeny schémy), databáza sa najprv skopíruje zálohovacím
  API SQLite do `data/backups/` (`lego-RRRRMMDD-HHMMSS-v<verzia>-<revízia>.db`,
  verzia a revízia pred štartom, posledných 5). Verzia appky je verzia
  balíka `lego-api` z `pyproject.toml` (`lego_api.__version__`); po úspešnej
  migrácii sa zapíše do `app_settings` → `app_version` a pred ďalšou sa
  číta surovým SQL, keďže schéma môže byť stará. Databáza bez zapísanej
  verzie (inštalácie spred tejto evidencie) sa zálohuje ako prvý štart novej
  verzie, v mene je len revízia; nová prázdna databáza sa nezálohuje. Bez
  zálohy sa migrácia nespustí; pri páde migrácie log povie, kde záloha je
  a že pred návratom treba zmazať `lego.db-journal` (`-wal`, `-shm`)
  (`services/db_backup.py`). Staré zálohy sa mažú až po úspešnej migrácii
  a po zlyhanej si značka `backups/lego-failed-migration.json` pamätá
  zálohu spred aktualizácie: slučka reštartov (`restart: unless-stopped`)
  ju tak nevytlačí kópiami napoly zmigrovanej databázy, kým sa databáza
  nezmení. Každý úspešný štart značku zmaže, aj keď nič nezálohoval.
  Verzia sa pri páde nezapíše, takže to platí aj pre novú verziu bez
  migrácie. Aby sa chyba do logu dostala, appka nastaví Alembicu
  `keep_logging` a `env.py` nevolá `fileConfig`. Zálohy nesú aj údaje
  neskôr zmazaných účtov, spomínajú ich zásady `/sukromie`.
- **Tajomstvá:** v `.env` (nie je v gite) je len `JWT_SECRET`
  a prevádzkové nastavenia. Kľúče k službám tam nie sú.
- **Prístup:** appka beží doma a von je dostupná pod doménou.
  `COOKIE_SECURE=true` patrí na https.
- **Záloha:** skopírovať `data/lego.db` a `data/photos/`.

### Nastavenia (`config.py`)

| premenná | predvolená hodnota | význam |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/lego.db` | databáza |
| `JWT_SECRET` | – | podpis tokenov a šifrovanie kľúčov |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | 15 / 30 | platnosť tokenov (30 dní so zapamätaním prihlásenia) |
| `REFRESH_SESSION_HOURS` | 12 | obnovovací token bez zapamätania |
| `COOKIE_SECURE`, `COOKIE_DOMAIN` | false / – | cookie obnovovacieho tokenu |
| `ALLOW_REGISTRATION` | true | východisko, kým ho správca v appke nezmení |
| `BRICKECONOMY_DAILY_LIMIT` | 90 | vlastný strop pod oficiálnych 100 |
| `PRICE_MAX_AGE_HOURS` | 168 | vek snímky, po ktorom sa cena obnoví |
| `PRICE_REFRESH_BUDGET` | 40 | strop položiek na jednu dávku |
| `PRICE_REFRESH_DELAY_SECONDS` | 1.0 | pauza medzi volaniami |
| `CMF_PARENT_THEME` | Collectible Minifigures | nadradená téma sérií na Rebrickable |
| `PHOTOS_DIR`, `PHOTO_MAX_BYTES`, `PHOTOS_PER_ITEM` | ./data/photos, 10 MB, 12 | fotky |
| `HTTP_TIMEOUT_SECONDS` | 10 | bežný limit volaní (pomalé zoznamy majú 45 s) |
| `INFLATION_ENABLED`, `EUROSTAT_HICP_URL` | true | index inflácie |

---

## 3. Účty, prihlásenie a kľúče

**Registrácia.** Email, heslo (argon2id) a zobrazované meno.

- Prvý účet sa dá zaregistrovať vždy a stane sa správcom. Inak by nová
  inštalácia nemala správcu.
- Ďalšie registrácie otvára správca prepínačom v Nastaveniach → Aplikácia
  (tabuľka `app_settings`). `ALLOW_REGISTRATION` platí len dovtedy, kým ho
  správca nezmení.
- Prihlasovacia stránka si stav zisťuje cez verejné `/providers/status`
  a pri zatvorenej registrácii skryje „Nový účet“.
- Nový účet začína bez kategórií, zakladá si ich sám.

**Tokeny.**

- Prístupový JWT platí 15 minút a drží sa len v pamäti prehliadača.
- Obnovovací token je v httpOnly cookie, v databáze je jeho sha256. Pri
  každom použití sa vymení a starý sa odvolá; odhlásenie ho zmaže.
- **Zapamätať si prihlásenie na tomto počítači** (políčko pri prihlásení
  aj registrácii, predvolene nie, `remember` v tele): trvalé cookie na
  30 dní. Bez neho session cookie bez Max-Age, ktoré zanikne so zatvorením
  prehliadača, a token na serveri platí 12 hodín, lebo prehliadač s obnovou
  kariet vráti aj session cookie. Režim je v `refresh_tokens.remember`,
  obnova ho zdedí a platnosť posunie (kĺzavé: aktívne používanie
  neodhlási). Tokeny spred zavedenia sú bez zapamätania. Vypršané tokeny
  všetkých účtov sa mažú pri vydaní nového.
- Zmena hesla zmaže všetky tokeny účtu, teda aj zapamätané prihlásenia
  na iných počítačoch. Prehliadač, v ktorom sa heslo zmenilo, dostane nový
  token bez zapamätania (session cookie) a ostane prihlásený do zatvorenia.
  Zmazanie účtu zmaže tokeny s ostatnými údajmi.
- Trvalé cookie vznikne len na výslovnú voľbu: zaškrtnutie políčka je
  súhlas s ním, lištu netreba. Zásady ho opisujú v tabuľke cookies
  a v Ako dlho.
- Klient pri 401 raz skúsi obnovenie a potom pošle na prihlásenie.
- Súbory na stiahnutie (CSV, fotky) preto idú cez klienta ako blob, nie
  obyčajným odkazom: odkaz by odišiel bez tokenu.

**Roly.** `user` a `admin`. Správca vidí zoznam používateľov (môže ich
deaktivovať a meniť rolu) a nastavenia appky.

**Kľúče k cudzím službám** (Rebrickable, Brickset, BrickEconomy):

- Patria používateľovi a zadáva ich v Nastaveniach → Dáta.
- Pri uložení sa overia jedným volaním. V `users` sú zašifrované
  (`services/keys.py`, kľúč odvodený z `JWT_SECRET`).
- Z API sa nikdy nevracajú, von ide len koncovka (`mask()`).
- Do zdrojov sa dostanú cez závislosť `CurrentKeys`. Zdroj bez kľúča je
  jednoducho vypnutý a appka funguje ďalej bez neho.
- Denná kvóta BrickEconomy sa počíta podľa odtlačku kľúča, nie podľa účtu.
  Otec s vlastným kľúčom má vlastnú kvótu.
- Kópia databázy s iným `JWT_SECRET` kľúče nerozšifruje. Na testovacej
  kópii sú tlačidlá obnovy cien skryté a to je v poriadku.

**Preferencie** (`users.preferences`, JSON):

- Povolené kľúče sú `collection` (filter Zbierky), `themes` (sledované
  témy) a `display` (prepínač dnešných peňazí).
- Ukladajú sa s oneskorením 800 ms. Prázdny objekt stav zmaže.
- Platia na počítači aj na telefóne.

---

## 4. Zdroje dát a ich limity

| zdroj | na čo | limit | kľúč |
|---|---|---|---|
| **Rebrickable** | metadáta setu, fotka, téma, dieliky, figúrky, zberateľské série | ~1 volanie/s, 429 pri prekročení | používateľa |
| **BrickEconomy** | trhová cena novej aj použitej položky, história cien, RRP v eurách, retired, číslo figúrky, EAN, odhad o 2 a 5 rokov, rast za 12 mesiacov | 100/deň na kľúč, appka si dáva strop 90 | používateľa (členstvo Premium) |
| **Brickset** | EAN, popis, štítky, hodnotenie, obľúbenosť, témy, roky, vlny | `getSets` 100/deň; `getThemes`, `getYears` a štatistika sa nerátajú | používateľa, len na súkromné použitie |
| **UPCitemdb** | posledná možnosť pri čiarovom kóde | ~100/deň na IP adresu servera | bez kľúča |
| **Eurostat** | HICP Slovenska, mesačný index | bez limitu | bez kľúča |

**Konkrétne volania:**

- **Rebrickable:**
  - `GET /api/v3/lego/sets/{num}/` a `/themes/{id}/` (témy sa cachujú
    v pamäti procesu);
  - `/sets/?theme_id=` (členovia série jedným volaním);
  - `/themes/?page_size=1000` (zoznam sérií);
  - hľadanie podľa balenia (blind-box série).
- **BrickEconomy:** `GET /api/v1/set/{num}?currency=EUR`
  a `/api/v1/minifig/{num}`. Hlavičky `x-apikey`, `accept` a `user-agent`
  sú povinné.
- **Brickset:**
  - `getSets` s `setNumber`, `query` (EAN) alebo `theme` a `year`,
    s `extendedData: 1` pre popis;
  - `getThemes`, `getYears`, `getKeyUsageStats`.
- **Eurostat:** `prc_hicp_minr?geo=SK&coicop18=TOTAL&unit=I15`
  (ECOICOP v2). Starý `prc_hicp_midx` končí 2025-12.

**Evidencia volaní.** Každé volanie cudzej služby zapíše `api_log.record`
do `api_calls`: kedy, kto, služba, akcia, predmet, účel, výsledok, stav
HTTP a či sa ráta do limitu. Záznamy sa držia 30 dní.

- Účel je schopnosť volania (`capabilities.py`), zdroj ju zapíše sám.
  Čie je volanie, nastaví závislosť prihláseného používateľa alebo úloha
  na pozadí cez `api_log.set_user`.

**Brána a pravidlá sťahovania.** Každé volanie má schopnosť (napríklad
`brickset.on_add`, `brickset.backfill`, `brickeconomy.prices`) a pred
odoslaním prejde bránou (`services/fetch_policy.py`). Brána pustí volanie,
len keď je schopnosť v nastaveniach účtu zapnutá a pri službách s limitom
zostáva dosť volaní; volania na pozadí nechajú rezervu. Podrobnosti sú
v specu `2026-09-27-pravidla-stahovania-design.md`.
- Ikona v hornej lište (`GET /usage`) ukazuje dnešné limity podľa UTC dňa
  a históriu volaní s filtrom podľa služby.
- Brickset navyše dáva vlastnú štatistiku, tá ráta aj volania mimo appky.

---

## 5. Dátový model

Katalóg je spoločný pre všetkých používateľov, zbierka, Chcem, kategórie,
fotky a odkazy patria účtu. Sumy sú `Numeric`: kúpne ceny na dve desatinné
miesta, snímky na štyri. Z API chodia ako reťazec zaokrúhlený na centy
(typ `Money`).

### Katalóg

**`catalog_items`**, kľúčom je `catalog_num` (`10294-1`, `71046-3`, `71046`).

| skupina | polia |
|---|---|
| druh | `kind` (set / minifig), `parent_num` → séria, `series_size` |
| základ (Rebrickable, ručné) | `name`, `year`, `theme`, `num_parts`, `num_minifigs`, `image_url`, `rrp_eur`, `is_retired`, `retired_at`, `ean` + `ean_source` |
| pôvod | `source`, `fetched_at` |

Údaje z Brickset sú v **`brickset_facts`** (popis, štítky, hodnotenie,
obľúbenosť, RRP, kód, retired, `brickset_id`, galéria, `found`) a z
BrickEconomy v **`brickeconomy_facts`** (podséria, retired dátum, číslo
figúrky, RRP, kód, odhady a rast). Kto ich vidí, určuje **`source_access`**
(služba, odtlačok kľúča, subjekt = číslo setu, `wave:{téma}:{rok}` alebo
`ean:{kód}`, `last_fetched_at`). Pravidlá viditeľnosti sú v specu
`2026-09-28-licencne-cista-architektura-design.md`.

`CatalogItem` zámerne nemá ORM vzťah na členov série. Členov vracia
`CatalogService.members_of` výslovným dotazom.

**Ostatné katalógové tabuľky:**

- **`cmf_series`**: zberateľské série minifigúrok z Rebrickable
  (`theme_id`, `name`, `series_num`, `synced_at`).
- **`blind_series`**: blind-box série iných radov (`base_num`, `name`,
  `category`, `year`, `is_series`, `synced_at`).
- **`theme_waves`** a **`theme_wave_sets`**: téma a rok z Brickset
  a ktoré sety do nich patria.
- **`inflation_index`**: mesiac (`2026-08`), hodnota (2015 = 100)
  a `fetched_at`.

### Zbierka

**`collection_items`**: jeden kus je jeden riadok a množstvo sa dopočítava.
Dva kusy toho istého setu sa môžu líšiť stavom, cenou aj umiestnením.

| skupina | polia |
|---|---|
| vlastníctvo | `status` (owned / sold / reserved), `user_id`, `catalog_num` |
| stav | `condition` (new_sealed / opened_unbuilt / built / parted_out), `flags` (has_box, has_manual, has_stand, damaged_box, missing_parts, complete) |
| figúrka | `price_variant` (sealed / complete / figure_only), `unidentified` (nerozbalený sáčok série) |
| kúpa | `purchase_price_eur`, `purchase_date`, `purchase_place` |
| predaj | `sold_price_eur`, `sold_date`, `sold_via`, `sold_fees_eur`, `sold_shipping_eur` |
| zaradenie | `purpose` (investment / for_sale / display / build), `location` |
| iné | `manual_market_price_eur`, `note`, `created_at`, `updated_at` |

**Ďalšie tabuľky účtu:**

- **`item_photos`**: popis fotky (`filename`, `content_type`,
  `size_bytes`). Súbor leží v `PHOTOS_DIR`, meno vymýšľa server a typ sa
  overuje podľa obsahu. So zmazaným kusom sa mažú aj súbory.
- **`price_snapshots`**: `catalog_num`, `source` (brickeconomy / manual),
  `price_kind` (SET / MINIFIG), `condition` (N / U), `avg_price`,
  `min_price`, `max_price`, `qty`, `currency`, `captured_at`.
- **`wishlist_items`**: Chcem, jeden set najviac raz na účet, s
  `target_price_eur`, `note` a `created_at`. Kúpený set z neho vyradí
  server pri každom pridaní kusu (`services/wishlist.py::drop_bought`).
- **`categories`**: vlastné kategórie (`name`, `color`, `rules` JSON,
  `sort_order`).
- **`category_items`**: ručné zaradenie alebo vylúčenie setu (`mode`
  include / exclude).
- **`saved_views`**: uložené pohľady Zbierky (`name`, `query`).
- **`share_links`**: odkazy na pozretie (`token`, `show_values`, `label`,
  `revoked_at`, `last_viewed_at`).
- **`price_checks`**: naposledy overené sety z Overiť cenu (`user_id`,
  `catalog_num`, `checked_at`), jeden riadok na set, posledných 200.

### Systém

- **`users`**, **`refresh_tokens`**, **`app_settings`** (kľúč a hodnota),
  **`api_calls`**.
- **`import_batches`**: hromadné importy (koncept s riadkami, stav,
  priebeh, vyradené položky Chcem). Kusy a položky Chcem z importu majú
  `import_batch_id`, podľa neho sa import vracia. Pozri spec importu.

---

## 6. Výpočty

Všetko je v `services/portfolio.py` a počíta sa v Pythone nad načítanými
riadkami, nie v SQL.

**Trhová hodnota kusu.** Ktorá položka a aký stav sa cení, určuje
`resolve_price_target` (kapitola 7). Hodnota je posledná snímka pre
správny stav, pri nájdení v poradí:

1. **Cena pre správny stav** (`market`).
2. **Cena pre druhý stav** (`market_approx`), v rozhraní so znakom ≈.
   Zdroj vracia cenu použitého kusu len pri stiahnutých setoch a bez tejto
   náhradnej ceny by postavený kus setu v predaji nemal hodnotu vôbec.
3. **Ručne zadaná cena** (`manual`).
4. **Žiadna cena** (`missing`). Kus prispieva nulou, ale rozhranie ukáže
   pomlčku, nikdy `0 €` ani `−100 %`.

**Súčet bez jedinej ceny nie je nula.** Keď v skupine nemá trhovú cenu ani
jeden vlastnený kus, hodnota aj nerealizovaný zisk sú `null` a rozhranie
ukáže pomlčku. Platí to pre rozpad výkonnosti (taká skupina ide na koniec),
dlaždice Prehľadu (celá zbierka aj rozsah) a súčty výberu v Zbierke. Keď
cenu má len časť kusov, hodnota je súčet ocenených a počet bez ceny ide
vedľa (`price_missing`). Bez vlastnených kusov je hodnota naozaj nula.
Top podľa zisku kusy bez ceny vynechá; bez jediného oceneného karta povie,
že zisk ukáže po stiahnutí cien. To isté platí na verejnom odkaze (set bez
ceny „cena neznáma“, hodnota zbierky pomlčka a „bez ceny: N“), v súčte
Súpisu, v exporte CSV (prázdna hodnota aj nerealizovaný zisk) a v dialógu
predaja (bez ceny prázdne pole, nie nula so stratou celej kúpnej ceny).

**Nerealizovaný a realizovaný zisk sa nikdy nesčítavajú.**

- **Nerealizovaný** = trhová hodnota − kúpna cena, cez vlastnené kusy.
- **Realizovaný** je čistý: predajná − poplatky − poštovné − kúpna, cez
  predané kusy.

Do trhovej hodnoty portfólia vstupujú len vlastnené kusy. Keby sa oba
zisky sčítali, predaj kusu by na grafe vyzeral ako strata hodnoty.

**Časový rad** má tri krivky:

- **viazaný kapitál**: kúpne ceny kusov, ktoré ku dňu vlastním;
- **trhová hodnota**: posledná známa cena ku dňu, kus bez ceny sa ráta
  za kúpnu;
- **kumulatívny čistý výnos z predajov.**

Predaný kus ku dňu predaja vypadne z prvých dvoch kriviek a objaví sa
v tretej. Krok je týždeň, pre krátke obdobie deň.

**Ročný výnos (CAGR).**

- Pod rok držania sa nepočíta. Z +10 % za mesiac by vyšlo +214 % ročne.
- Skupina (téma, zoznam, celá zbierka) je jeden celok s dobou držania
  váženou vkladom (`collection_cagr`), nie priemer percent jednotlivých
  kusov.

**Priemerná zľava pri nákupe** = 1 − priemer (kúpna / RRP). Ráta sa len
z kusov, ktoré majú obe čísla, a rozhranie uvedie, z koľkých kusov.

**Odhad hodnoty** o 2 a 5 rokov (z BrickEconomy) platí len pre kusy
v krabici. Porovnáva sa s dnešnou hodnotou tých istých kusov, nie celej
zbierky.

**Pohyby cien** za 30, 90 a 365 dní porovnávajú dnešnú snímku so snímkou
najbližšou k začiatku okna. Položka bez staršej snímky sa vynechá, nič sa
nedopočítava.

**Rozpad výkonnosti** podľa témy, podtémy alebo zoznamu: vklad, hodnota,
zisk a výnos. Pri čiastočnej cene ukáže pri hodnote „bez ceny: N“ a zisk
ako pomlčku. **Predaje podľa kanála:** tržba, náklady, kúpna cena, čistý
zisk a výnos.

**V dnešných peniazoch (inflácia).**

- Kúpna cena sa násobí `index(posledný mesiac) / index(mesiac kúpy)`,
  predajná podľa mesiaca predaja. Trhová hodnota je dnešná a nemení sa.
- Index je skutočný mesačný HICP Slovenska, nie priemerná miera. Roky 2022
  a 2023 tak vážia toľko, koľko naozaj vážili.
- `deflate` nastaví `buy_factor` a `sell_factor` na `ValuedItem`, takže
  súhrn, zisk, CAGR, rozpad aj graf idú samy. Trasy berú `real=true`.
- Mesiac, ktorý Eurostat ešte nezverejnil, a kúpa bez dátumu sa
  neprepočítavajú.
- Priemerná zľava voči RRP ostáva nominálna.
- Index sa sťahuje raz za týždeň a len na požiadanie. Po chybe je hodinu
  pokoj a starý rad ostáva.

**Súčty výberu v Zbierke** (`FacetsOut.totals`): kúpené, hodnota, zisk
a reálny zisk po inflácii, nezávisle od prepínača. Kus bez ceny do zisku
nevstupuje, len sa spočíta.

---

## 7. Ceny: odkiaľ, kedy a za koľko volaní

**Voľba položky na cenenie** je len v `services/pricing.py::resolve_price_target`.

| kus | cení sa ako | číslo |
|---|---|---|
| set | set | `catalog_num` |
| figúrka – zatvorený sáčok | set | `catalog_num` |
| figúrka – komplet so stojanom | set | `catalog_num` |
| figúrka – len figúrka | minifig | `minifig_no`; keď ho nepoznáme, set |
| nerozbalený sáčok série | set | číslo série |

Holá figúrka bez `minifig_no` spadne na set. Volanie s katalógovým číslom
by skončilo chybou a zbytočne ukrojilo z kvóty.

Figúrka z Rebrickable mimo série (`fig-…`, `pricing.is_bare_figure`) set
nie je a zdroj ju pod týmto číslom nepozná. O volaní von rozhoduje
`pricing.source_prices`: cieľ „set pod fig-…“ sa nevolá nikdy, Overiť cenu
vráti `unsupported` a dávka ho do plánu nedá (ani z Chcem). Pod vlastným
`minifig_no` sa cení ako figúrka. Ručná cena pod katalógovým číslom platí
ďalej, snímky číta `resolve_price_target`.

**Jedno volanie na položku.** Odpoveď nesie cenu novej aj použitej
položky a históriu. Dávka sa preto delí podľa `PriceTarget.call_key()`
(číslo a druh), nie podľa stavu. Tri kusy toho istého setu v rôznom stave
stoja jedno volanie. Predané kusy sa neobnovujú.

**Čo sa z odpovede uloží:**

- **`store_market`:**
  - aktuálna hodnota novej aj použitej položky sa zapíše vždy, aj keď sa
    nezmenila, lebo je to stopa, že sme sa dnes pýtali;
  - udalosti z `price_events_*` sa zapíšu pod vlastným dátumom (poludnie
    UTC) a tie, ktoré už v databáze sú, sa preskočia.
- **`apply_catalog_extras`** doplní RRP v eurách, retired, číslo figúrky
  a EAN a prepíše odhad o 2 a 5 rokov a rast. Rast môže byť záporný.

**Kedy sa obnovuje.** Ceny obnovuje len tlačidlo v hornej lište
(`POST /prices/refresh-all`), ďalej to beží cez `BackgroundTasks`. Nemá to
plánovač a nespúšťa to ani prihlásenie. Poistky v `services/refresh.py`:

- **vek posledného volania:** obnoví sa, len čo je staršie ako 168 h;
- **strop dávky:** 40 položiek;
- **zvyšok dennej kvóty:** počítadlo je v `providers/brickeconomy.py`,
  pri 429 sa dávka zastaví;
- **jedno volanie na (číslo, druh);**
- **zámok proti súbehu** a množina položiek, ktoré sa práve obnovujú.

**Vek** je čas od posledného volania vlastného kľúča, či cena prišla, alebo
nie (`source_access` čísla, pri neúspechu `miss:{číslo}`, a neúspech
z Overiť cenu v pamäti procesu), prípadne od novšej ručnej ceny. Keď zdroj
odpovie, že set nepozná alebo preň cenu nemá, `pricing.store_miss` to
zapíše pod `miss:{číslo}`; prístup pod samotným číslom by účtu odomkol
ceny iného kľúča. Overiť cenu zapisuje neúspech tou istou funkciou.
Výpadok siete či chyba servera (`provider.last_answered` je False) sa
nezapíše nikde, ani v Overiť cenu, a skúsi sa pri ďalšej obnove.

**Poradie dávky.** Najprv neznáme ceny: kľúč sa na položku ešte nepýtal
a niektorý jej stav nemá snímku. Medzi nimi Zbierka pred Chcem (hodnota
zbierky ráta len vlastnené kusy) a naposledy pridané prvé (čerstvo pridaný
set je ten, na ktorého cenu používateľ čaká). Potom ostatné od najstaršieho
volania, takže pri veľkej zbierke vzniká rotácia. Pri ~1500 rôznych setoch
a 90 volaniach denne trvá jedno kolo zhruba 17 dní. História tým netrpí,
lebo každá odpoveď nesie ceny za posledné mesiace.

Kým sa neúspech nezapisoval, položka bez ceny bola pri každej obnove
neznáma, prvá na rade a stála volanie pri každom kliknutí. To isté
postavený kus setu v predaji: zdroj mu použitú cenu nepošle, kým sa set
nestiahne z predaja. Teraz stojí každá taká položka jedno volanie za
168 h, ako položka s cenou.

**Ručná obnova z detailu** (`refresh-all?num=`) vek snímky nepozerá, strop
dávky a zvyšok kvóty platia aj pre ňu. **Ručná cena**
(`PUT /prices/{num}/manual`) je plnohodnotná snímka, graf aj portfólio
ju vidia.

**Spätná väzba.** `GET /prices/refresh-status` hlási, či obnova beží,
koľko ostáva a koľko zostáva z kvóty. Horná lišta ukazuje indikátor a po
dobehnutí prenačíta Prehľad aj Zbierku. Tlačidlo je vypnuté bez kľúča
alebo pri minutej kvóte a nápoveda hovorí, koľko volaní dnes zostáva.

---

**Kúpna cena doplnená z odporúčanej** (prepínač na karte BrickEconomy,
`fetch_settings.auto_purchase_price`, predvolene vypnutý,
`services/purchase_fill.py`). Pri obnove cien dostane vlastnený kus bez
kúpnej ceny odporúčanú: z odpovede BrickEconomy, inak z katalógu
(Brickset). Na konci obnovy sa zvyšné kusy doplnia z katalógu zadarmo,
aj s čerstvou cenou; rovnako hneď pri zapnutí prepínača a pri obnove
s minutou kvótou. Kus má `purchase_price_auto`,
rozhranie ho označí ikonou a filter Kúpna cena (zadaná, doplnená, chýba)
ho nájde. Ručná zmena ceny príznak zruší; dialóg kusu preto posiela cenu,
len keď sa zmenila.

## 8. Katalóg, série a čiarové kódy

**Dohľadanie setu** (`CatalogService.resolve`):

1. Najprv sa hľadá v databáze (`get_local`). Holé číslo `10294` skúsi
   `10294-1` a potom `10294`.
2. Ak tam nie je, stiahne sa z Rebrickable a doplní z Brickset.
3. Set nevracia názov témy, len `theme_id`, preto sa dotiahne cez
   `/themes/{id}/`.

Set, ktorý nie je v žiadnom katalógu, sa dá zadať ručne (`POST /catalog`).

**Zberateľské série minifigúrok.**

- Na Rebrickable je každá figúrka samostatný set (`71046-1` až
  `71046-12`) v téme, ktorej nadradená téma je „Collectible Minifigures“.
- Appka nad nimi vytvorí zastrešujúcu položku s holým číslom (`71046`,
  `series_size`).
- Členovia sa ťahajú jedným volaním cez tému.
- Balenia (sáčok, kompletná sada, multipack) medzi členov nepatria.
  Spoznajú sa podľa nula dielikov alebo podľa názvu.
- **Pri holom čísle má séria prednosť pred svojím prvým členom.**
  `get_local` to stráži, inak by `71046` vrátilo jednu figúrku namiesto
  výberu z dvanástich.
- **Sekcia Figúrky pozná všetky série, aj nezačaté.** `services/cmf.py`
  ich sťahuje na pozadí, sekundu od seba. Otvorenie sekcie raz za týždeň
  skontroluje zoznam; série z tohto a minulého roka sa raz za dva týždne
  stiahnu znova. Nové série teda pribúdajú samy. Po chybe sa to hodinu
  neskúša znova. Cenovú kvótu to nemíňa.
- **Blind-box série iných radov** (Mighty Machines, Super Mario Character
  Pack, VIDIYO, Unikitty!, Duplo vrecúška) nemajú vlastnú tému. Hľadajú sa
  podľa balenia (`find_blind_series`) a figúrky sú varianty čísla
  (`42233-1` až `-8`). Ukladajú sa do `blind_series` s kategóriou, členovia
  sú `kind=set` a cenia sa ako sety.

**Nerozbalený sáčok** je kus ukazujúci na sériu s `unidentified=true`.
Po rozbalení ho `PATCH /items/{id}/identify` prepne na konkrétnu figúrku.

**Čiarový kód** (`services/barcode.py`) sa hľadá v poradí:

1. **Katalóg doma** podľa `ean`.
2. **Brickset:** `getSets` s `query`; výsledok sa overí proti `barcode`
   v odpovedi, lebo dotaz môže trafiť aj názov.
3. **UPCitemdb:** z názvu produktu sa vyčíta číslo setu a overí sa cez
   Rebrickable.

Podrobnosti:

- Kontrolná číslica sa overuje pred dotazom.
- Nájdený kód sa uloží a ďalší sken toho istého setu už von nejde. Kód sa
  ukladá aj z každej odpovede BrickEconomy a Brickset.
- Neznámy kód si pridávanie zapamätá a po uložení ho priradí setu
  zadanému číslom (`PUT /catalog/{num}/ean`).
- Kód, ktorý nenašiel nikto, sa pri účte pamätá 30 dní (`barcode_misses`),
  takže ďalší sken tej istej krabice nemíňa limity Brickset ani UPCitemdb.
  Rozhranie povie, kedy sa kód hľadal, a ponúkne „Skúsiť znova“
  (`?retry=true`). Limit a vypnuté sa nepamätajú, ani neúspech, pri ktorom
  brána dnes nepustila Brickset. Nájdený alebo ručne priradený kód
  neúspech zmaže.
- Čítačka (`BarcodeScanner.vue`) použije natívny `BarcodeDetector`, ak ho
  prehliadač má, inak ZXing wasm zo súborov appky, nie z CDN.
- Čítačka ponúka výber kamery a fotku zo súboru. Popri celom zábere skúša
  zväčšený stred a „vyrovnaný tieň“ (obraz delený svojou rozmazanou
  kópiou); bez toho sa skutočná fotka krabice s tieňom neprečítala.
- Kamera ide len na https alebo localhost.
- **Ručná čítačka** (`stores/scanner.ts`) ide v režime klávesnice (HID):
  rozpozná sa podľa rýchleho písania ukončeného Enterom a nepotrebuje nič
  pripájať. Web Serial appka nepodporuje (používateľ ho nepotreboval).
  Skeny dostane posledný odberateľ `useScanCodes`. Layout sa prihlási ako
  záloha (`fallback`) a sken z ktorejkoľvek obrazovky pošle na
  `/pridat?code=…`. Pridať set sa prihlási nad neho a ďalšie skeny
  spracuje samo (`scanner/scanFlow.ts`):
  - rovnaký kód ako neuložený set: počet + 1 (pri sérii nerozbalené sáčky);
  - iný kód: rozpracovaný set sa uloží tak, ako je vo formulári (bez ceny,
    ak ju nikto nevpísal), oznámenie s tlačidlom Späť zmaže práve tie
    kusy, a načíta sa nový kód;
  - skeny aj uloženie tlačidlom idú cez jednu frontu, nič sa neuloží
    dvakrát.

**Brickset navyše** (`services/brickset_extras.py`):

- Popis, štítky, hodnotenie a obľúbenosť prídu z `getSets` s
  `extendedData: 1`, raz na set a kľúč, stráži to `source_access`.
- Nové sety ich dostanú pri vyhľadaní. Staršie dopĺňa beh na pozadí pri
  otvorení Zbierky, najviac 40 za beh, a detail setu pri otvorení (jedno
  volanie).
- Existujúcim údajom Brickset nič neprepisuje, len dopĺňa chýbajúce.
  Štítky sú aj filter.

**Témy a vlny** (`services/themes.py`):

- Zoznam tém a rokov je z Brickset zadarmo. Vlna (téma + rok) je jedno
  `getSets` a uloží sa; čerstvé roky sa po 30 dňoch stiahnu znova.
- Do úplnosti patria len kategórie Normal a Extended, nie kolekcie.
- Brickset tému pomenúva inak než Rebrickable a sety zaraďuje inak
  (staršie Botanicals sú v Brickset pod Icons, figúrky série Shrek sú
  v Rebrickable pod témou Shrek). Set sa ráta v jedinej téme (`assign`):
  stiahnutá vlna, ktorú účet vidí; potom téma a rok z údajov Brickset
  o sete (`bs_theme`, `bs_year`, len s prístupom kľúča); až keď Brickset
  set nepozná, téma a rok z katalógu. Nie-set je, čo Brickset vedie
  v inej kategórii než Normal či Extended (`brickset_facts.category`).
  Staršie údaje kategóriu nemajú: set vtedy vyradí len vlna jeho témy
  a roka stiahnutá neskôr, než o ňom Brickset odpovedal. Vlna staršia než
  údaj setu je stará (Brickset set pridal potom): set sa ráta, rok je
  odhad a otvorenie roka vlnu stiahne znova. Set bez údajov Brickset sa
  podľa roka z Rebrickable nezahadzuje.
- Rátajú sa len sety (`counts_as_set`): figúrky zo sérií (minifigúrky aj
  blind-box), zatvorený sáčok pod číslom série ani holá figúrka nie.
  Platí to pre témy, roky, vlnu aj počet pri Sériách v ponuke
  (`theme_names`). Ten ráta len témy zo zoznamu Brickset, rovnako ako
  zoznam Sérií; kým zoznam nie je v pamäti, len témy od Brickset.
- „V zbierke“ nikdy neprekročí počet setov témy ani roka. Téma je
  kompletná (`complete`, zelený pruh), len keď sa počty naozaj zhodujú a vo
  stiahnutých vlnách nič nechýba; orezaný počet je plný pruh, ale žltý.
- Kým vlna nie je stiahnutá, počet pri roku je odhad, potom je presný
  (odhad ostane, keď v nej chýba môj set).

**Vlastné kategórie** (`services/categories.py`):

- Set patrí do kategórie podľa pravidiel na názov, tému alebo podtému
  (celé slovo, obsahuje, presne) alebo ručne.
- Prednosť: ručná voľba na sete, potom ručná voľba na jeho sérii, potom
  pravidlá.
- Ručný záznam sa uloží, len keď mení výsledok, takže vylúčenie proti
  pravidlu je riadok s `mode=exclude`.
- Nový účet nemá žiadnu predvolenú kategóriu (Formula 1 majú len staršie účty z migrácie).
- Zaradiť set sa dá na troch miestach: v detaile setu (zapíše sa hneď),
  pri pridaní setu a v úprave kusu. Pridanie aj úprava kusu majú ten istý
  výber (`CategoryPicker.vue`, `useCategoryPicker.ts`) so správcom
  kategórií; zmeny sa zapíšu až pri uložení formulára a len tie, ktoré sa
  líšia od stavu servera. V úprave kusu sa zaraďuje set kusu, nie kus.

---

## 9. Obrazovky

**Rám appky** (`AppLayout.vue`).

- Na širokej obrazovke je bočná ponuka s číslami, na telefóne spodná
  navigácia (tá čísla nemá).
- Horná lišta obsahuje:
  - názov stránky;
  - indikátor obnovy cien;
  - prepínač „V dnešných peniazoch“, ktorý pri zapnutí ukazuje štítok
    s mesiacom indexu;
  - limity API;
  - tlačidlo obnovy cien;
  - svetlý a tmavý režim;
  - jazyk;
  - menu účtu.
- Čísla v ponuke:
  - **Zbierka:** počet setov;
  - **Figúrky:** figúrky zo sérií;
  - **Témy:** moje a sledované témy;
  - **Chcem:** položky.

**Prehľad** (`/`):

- **Rozsah** nad dlaždicami: celá zbierka, uložený pohľad, kategória,
  zoznam alebo téma (`components/ScopePicker.vue`, pamätá sa v
  `preferences.dashboard`). Všetky `/stats/*` berú ten istý filter ako
  `/items`, predané kusy v rozsahu ostávajú. Štítok „Rozsah: …“ s krížikom;
  ponuka a Zbierka ostávajú za celú zbierku.
- **Dlaždice:**
  - investované, s priemernou zľavou;
  - trhová hodnota, s počtom kusov bez ceny;
  - nerealizovaný zisk, s percentom a CAGR;
  - realizovaný zisk;
  - zbierka: hlavné číslo sú sety sekcie Zbierka, podnadpis „41 figúrok ·
    3 sáčky · 189 kusov · 39 188 dielikov“ (nulové počty vynechá). Čísla sú
    tie isté ako pre ponuku, len s rozsahom Prehľadu: `collection_set_count`,
    `series_figures` (rôzne figúrky zo sérií, aj blind-box) a
    `sealed_bag_count` (každý nerozbalený sáčok, ako vo Figúrkach; figúrkou
    je až po rozbalení). Bez rozsahu dlaždica sedí s ponukou aj s Figúrkami.
- **Graf portfólia:**
  - tri krivky;
  - rýchle voľby (mesiac až všetko), vlastné od–do, ťahanie a zoom;
  - pre krátke obdobie denné body.
- **Karty:**
  - koláč tém (počet setov);
  - výkonnosť podľa témy, podtémy alebo zoznamu;
  - predaje podľa kanála;
  - odhad hodnoty;
  - top 10 podľa zisku;
  - pohyby cien za 30, 90 a 365 dní, 10 záznamov;
  - kompletnosť sérií, nekompletné prvé; „Ukázať chýbajúce“ otvorí sériu
    vo Figúrkach rovno na chýbajúcich (`?show=missing`).
- Karty sú v upratanej mriežke a obrazovka nie je vyššia než monitor.

**Zbierka** (`/zbierka`):

- **Len sety.** Figúrky zo sérií (zberateľské minifigúrky aj blind-box série
  ako Mighty Machines) sú vo Figúrkach. Zbierka posiela `sets_only=true`
  do zoznamu, počtov panela aj hromadnej úpravy; figúrky tak nie sú ani vo
  voľbách panela a súčtoch. Prehľad, export CSV, súpis a detail setu ho
  neposielajú a počítajú všetko. Počty v ponuke a hlavičke Zbierky sú
  `collection_set_count`, `collection_item_count`, `collection_sold_count`.
- Hľadanie bez diakritiky v názve, čísle, téme, podtéme, umiestnení,
  obchode, poznámke a štítkoch (všetky slová musia sedieť).
- Zoradenie desiatimi spôsobmi so smerom (register `services/sorting.py`),
  prázdne hodnoty vždy na konci; tlačidlo Filtre s počtom aktívnych filtrov.
- Prepínač vlastnené / predané / všetko a zoskupenie podľa setu alebo
  kusu.
- **Panel filtrov** je vpravo a dá sa skryť:
  - kategórie, téma, podtéma, stav, zoznam, umiestnenie, príznaky,
    štítky, roky, retired a cena (zisk, strata, bez ceny);
  - kúpa a hodnota: dátum kúpy od–do, kúpna cena a trhová hodnota za kus
    od–do, kde kúpené; kanál predaja; hodnotenie Brickset (aspoň 3,5 / 4 /
    4,5); odhad rastu; pôvod ceny (trhová, odvodená, ručná, bez ceny,
    neobnovená 30+ dní); import; stiahnuté za posledný rok;
  - len duplicity (pri stave kusu).
  - Typ, séria, podoba figúrky, nekompletné série a chýbajúce figúrky tu
    nie sú; stará adresa či uložený stav s nimi sa pri otvorení vyčistí.
- Čipy aktívnych filtrov, uložené pohľady a „Resetovať filtre“.
- Riadok súčtov výberu, Export CSV a Pridať set.
- Filter je v adrese pod rovnakými menami, aké berie API. Posledný stav
  si pamätá účet: príchod z ponuky ho vráti, odkaz s filtrom má prednosť.
- Na širokej obrazovke sa posúvajú len karty a panel, nie celá stránka.
  Do výšky rastú len výsledky, riadky nad nimi majú vlastnú výšku.
- **Karty alebo tabuľka** (pamätá sa pri účte). Tabuľka
  (`CollectionTable.vue`, `v-data-table-virtual`) má stĺpce číslo, názov,
  téma, rok, kusy, stav, umiestnenie, kúpené, hodnota, zisk, %, ročne;
  klik na hlavičku radí cez server (`utils/tableColumns.ts`).
- **Hromadná úprava:** „Vybrať na úpravu“, začiarkávatká na kartách,
  riadkoch aj v tabuľke, „Vybrať všetko“ = celý výsledok filtra. Akcie:
  umiestnenie, zoznam, stav, príznak pridať či odobrať, kategória zaradiť
  či vyradiť (na set). `POST /items/bulk-update` s filtrom v adrese,
  zoznamom kusov alebo číslami setov; najprv `dry_run` na potvrdenie
  „Kde uložené → Povala: 143 kusov“. Menia sa len vlastnené kusy účtu.
  Figúrky zo sérií sa hromadne upravujú v detaile série (rozsah `series`).
- **Figúrky inde:** keď hľadanie trafí figúrky zo sérií, pod riadkom
  súčtov je nenápadný riadok „N figúrok zo sérií je vo Figúrkach“
  s odkazom Otvoriť Figúrky (`FacetsOut.hidden_figures`); keď Zbierka
  nenašla nič a filter by trafil figúrky, ten istý riadok je v prázdnom
  stave. Bežný filter (stav, umiestnenie…), ktorý niečo ukazuje, figúrky
  nehlási. Kým sa hľadanie spresňuje a nové počty ešte neprišli, riadok
  drží miesto bez starého počtu, aby výsledky neposkakovali. Písmo 14 px
  (`text-body-medium`). Starý odkaz s filtrom série vedie do
  Figúrok, uložený pohľad s filtrom figúrok je označený a po kliknutí to
  oznámi.
- **Karta setu:** fotka, názov, číslo, téma, dieliky, čipy stavu
  a umiestnenia, štítok Stiahnutý, kúpené → hodnota a percento. Bez ceny
  je tam pomlčka, pri odvodenej cene ≈. Predaná karta ukazuje predajnú
  cenu.

**Pridať set** (`/pridat`):

- Jedno pole na číslo alebo EAN a jedno tlačidlo hľadania; čítačka
  čiarového kódu kamerou alebo z fotky.
- Výrazný pás „už ho máš“ s počtom kusov a umiestnením.
- **Z Chcem** set pri uložení vyradí server; odpoveď `POST /items`
  (`/items/bulk`) nesie pôvodnú položku v `removed_from_wishlist` na prvom
  kuse setu. Po uložení tlačidlom je vedľa „Pridané do zbierky“ oznámenie
  „Odstránené z Chcem“ so Späť, ktoré ju vráti s cieľovou cenou, poznámkou
  aj dátumom pridania; kusy ostanú. Automatické uloženie po skene má jedno
  oznámenie a jedno Späť: zmaže kusy a vráti Chcem (druhé Späť by pri
  rýchlom skenovaní zapratalo obrazovku). Chcem vracia až po zmazaní kusov
  a s `?unless_owned=true`: set, ktorý ešte mám, lebo pri skenoch X, Y, X
  druhý kus X uložil ďalší sken, server do Chcem nevráti (204) a oznámenie
  to povie. Kúpený set v Chcem nie je.
- Pri sérii mriežka figúrok so stepperom, „všetky“ a „nerozbalený sáčok“.
- Formulár: počet, stav, príznaky, cena, dátum, kde kúpené, kde uložené,
  zoznam a kategórie.
- **Bez kľúča Rebrickable** Pridať set ukáže upozornenie s odkazom do
  Nastavení → Dáta a pri nenájdenom čísle rovno otvorí ručné zadanie.
  Stačí číslo, názov je nepovinný (bez neho „Set 10294“). Holé číslo
  dostane variant `-1` ako v Rebrickable, aby po pripojení kľúča nevznikol
  ten istý set druhý raz. Fotka, téma ani dieliky sa nedoplnia.
- **Pamäť formulára** (Nastavenia → Formuláre, `preferences.form`,
  `composables/useFormMemory.ts`): pre umiestnenie, stav, zoznam, kde
  kúpené a dátum kúpy prepínač. Zapnuté pole sa predvyplní poslednou
  uloženou hodnotou, vypnuté ostane predvolené. Platí aj pre Kúpil som,
  Mám všetky a automatické uloženie po skene.

**Detail setu** (`/set/:num`):

- Metadáta a blok z Brickset (popis, štítky, hodnotenie, obľúbenosť,
  odkaz).
- Kategórie setu.
- Karty cien: nový a použitý kus, zmena, posledná aktualizácia, obnova
  len tohto setu a ručná cena.
- Graf ceny s kúpnou cenou.
- Tabuľka kusov: úprava, fotky, predaj, vrátenie predaja, zmazanie,
  identifikácia sáčku, návrh inzerátu (cena a text pre Aukro a Bazoš).
- Kusy aj súčty (vlastnené, predané) sú jedna mriežka: Kúpené, Hodnota
  a Zisk stoja v každom riadku aj v súčte pod sebou, nech má kus
  koľkokoľvek štítkov. Na užšej karte sú štítky nad sumami, na telefóne
  sumy v troch rovnakých stĺpcoch a akcie pod nimi.
- Kusy sa načítavajú so `status=all`, aby predaný kus nezmizol aj
  s históriou.
- „Ďalší kus“ pridá kus bez hľadania; na stránke série (podľa
  `series_size`, aj nezačatej) vedie do Figúrok. Kus pod holým číslom
  série server vždy uloží ako nerozbalený sáčok.
- Na stránke série hromadná úprava jej vlastnených kusov (krabica, zoznam,
  stav, príznaky, kategória).
- Úprava kusu sa počas ukladania nedá zavrieť a uloží sa na kus, pre ktorý
  sa začala; výber kategórií hlási načítanie aj chybu so „Skúsiť znova“.

**Figúrky** (`/figurky`):

- Kategórie v záložkách (minifigúrky a blind-box série), filter (aj
  „skoro kompletné“: chýbajú najviac 2), zoradenie podľa abecedy, roku
  a „najmenej chýba“, úplnosť každej série (`utils/seriesList.ts`).
- **Séria** (`/figurky/:num`): mám a nemám. Chýbajúca figúrka je
  prerušovaná karta s „Chcem“ a „Mám ju“. „Mám všetky“ zadá celú sériu
  jednou sumou, rozpočítanou na centy. „Kusy série“ vedie do detailu série
  (`/set/:num`): nerozbalené sáčky, predané figúrky, hromadná úprava
  a obnova cien série. Pridať set po uložení série alebo figúrky vedie sem,
  nie do Zbierky. Odkazy odtiaľ na detail nesú `?from=minifigs`, ponuka
  potom ostane na Figúrkach.

**Série** (`/temy`, v rozhraní „Série“, v dátach téma): moje série a hľadanie vo všetkých. Tému bez setu sa dá
uložiť hviezdičkou. Moje témy sa radia podľa počtu mojich setov, úplnosti
alebo názvu a filtrujú na sledované, s mojimi setmi a nekompletné
(`utils/themeList.ts`, v prehliadači; nekompletná je téma bez `complete`,
pri rovnakej úplnosti idú kompletné prvé). **Téma** (`/temy/:theme`) ukazuje roky „mám X z Y“
a sety zvoleného roku.

**Chcem** (`/chcem`): cieľová cena a poznámka sa dajú upraviť
(`PATCH /wishlist/{id}`, ceruzka na karte, „Zadať“ pri chýbajúcom cieli);
cieľová a trhová cena a vzdialenosť od cieľa
(`distance_pct`). Radí a filtruje server (`GET /wishlist?sort=distance|
market|target|name|theme|added&dir=&q=&reached=&retired=&no_price=`),
predvolene najbližšie k cieľu navrch, prázdne hodnoty na konci. „Kúpil som“ presunie položku do zbierky, bez hľadania.
Z Chcem ju vyradí server, rovnako ako každé iné pridanie kusu (Pridať set
číslom aj skenom, Mám ju, Mám všetky, Ďalší kus, import): porovnáva sa
katalógové číslo, vyraďuje vlastnený aj rezervovaný kus, predaný nie
(dodatočne zapísaný predaj neznamená, že set už nechcem). `POST /wishlist`
berie `created_at`, aby Späť vrátil položku na jej pôvodné miesto;
rovnako ju s pôvodným dátumom obnoví vrátenie importu.

**Nastavenia** (`/nastavenia`):

- **Účet:** meno, heslo.
- **Zdieľanie:** odkazy na pozretie zbierky alebo zoznamu Chcem
  (`share_links.kind`), celého alebo len vybraných setov
  (`catalog_nums`). Dajú sa vytvoriť, skopírovať a zrušiť, majú
  prepínač súm a čas posledného otvorenia. Odkaz na Chcem nezdieľa
  zbierku ani poznámky.
- **Jazyk a mena.**
- **Dáta:** karty služieb (Rebrickable, Brickset, BrickEconomy, UPCitemdb,
  Eurostat): kľúč, čo odomkne, prepínače volaní s vysvetlivkou a riadkom
  „prinesie“, rezerva a dávka cien. Bez kľúča je karta sivá a hovorí, čo
  by kľúč priniesol; mimo Nastavení sa skryje, čo bez neho nejde.
- **Import a export:** hromadný import z .xlsx alebo .csv:
  - šablóna s výberovými zoznamami a hárkom Návod;
  - náhľad so stavom a dôvodom pri každom riadku;
  - dohľadanie neznámych setov, zaškrtnutie duplicít;
  - potvrdenie, vrátenie a história importov.

  Pod tým je export CSV a súpis pre poistku.
- **Používatelia** a **Aplikácia** (registrácia, prevádzkovateľ): len
  správca. Na konci Aplikácie je nenápadne verzia appky z `GET /health`
  (`components/AppVersion.vue`).

**Overiť cenu** (`/overit-cenu`): napíšem číslo alebo naskenujem kód
(čítačka ide cez `useScanCodes`, sken ostane na stránke) a hneď vidím set,
či ho mám, cenu nového aj použitého kusu a graf histórie. Hore je veľké
upozornenie, že overenie míňa volanie BrickEconomy; bez pripojeného
BrickEconomy je namiesto neho odkaz do Nastavení → Dáta a ukážu sa len
uložené ceny. Všetko robí `POST /prices/lookup/{num}`: set hľadá
v katalógu, cez Rebrickable, a neznámy set spozná aj z odpovede BrickEconomy
o cene (názov, séria, rok, dieliky, bez fotky), v tom istom volaní. Cena
mladšia než 24 hodín sa neťahá znova. Hore je stav služieb (kto spozná
set, kto čiarový kód, kto cenu) a keď neznámy set nemá kto dohľadať,
povie to rovno aj s odkazom do Nastavení.
Pod tým je tabuľka Naposledy overené (`price_checks`); klik na riadok
ukáže uložené ceny bez volania a poradie nemení. Séria sama cenu nemá,
ponúkne výber figúrky.

**Galéria v detaile setu:** ďalšie oficiálne fotky z Brickset
(`getAdditionalImages`, do limitu sa nepočíta), stiahnuté raz na set do
`catalog_items.bs_images` cez `GET /catalog/{num}/images`. Potrebuje
`brickset_id` z getSets; starší set sa naň raz opýta. Prepínač
`brickset.images` na karte Brickset galériu vypne. Náhľady v páse, klik
otvorí karusel; pod galériou „Image(s) courtesy of Brickset.com“. Na
verejnom odkaze galéria nie je.

**Súpis pre poistku** (`/supis`): stránka bez ponuky na tlač alebo PDF
z prehliadača. Obsahuje kusy, ceny a fotky; PDF zámerne nerobí server.

**Verejná zbierka** (`/z/:token`): bez prihlásenia a bez navigácie.
Pri vypnutých sumách server ceny do odpovede vôbec nevloží.

---

## 10. API

Predpona `/api/v1`, všetko okrem `/auth/register`, `/auth/login`,
`/auth/refresh`, `/public/*`, `/providers/status` a `/health` vyžaduje
prihlásenie. Úplná schéma je v OpenAPI (`openapi_export`).

| oblasť | trasy |
|---|---|
| auth | `POST register, login, refresh, logout`; `GET/PATCH me`; `GET/PUT me/keys` (aj `capabilities`), `GET/PUT me/sources`; `GET me/preferences`, `PUT me/preferences/{key}` |
| katalóg | `GET catalog/{num}`, `children`, `ownership`, `categories`; `POST catalog` (ručne), `{num}/refresh`, `{num}/brickset`, `brickset/backfill`; `GET catalog/by-ean/{code}`; `PUT catalog/{num}/ean` |
| kusy | `GET items` (filtre, `sort`, `real`), `items/grouped` (`by`), `items/facets` (počty + súčty, `hidden_figures`), `locations`, `suggestions`; `POST items`, `items/bulk`; `GET/PATCH/DELETE items/{id}`; `PATCH {id}/identify`; `POST {id}/sell`, `{id}/unsell` |
| fotky | `GET/POST items/{id}/photos`; `GET photos`; `GET/DELETE photos/{id}` |
| kategórie | `GET/POST categories`; `PATCH/DELETE categories/{id}`; `PUT categories/{id}/members/{num}`; `GET/POST views`, `DELETE views/{id}` |
| ceny | `GET prices/refresh-status`; `POST prices/refresh-all?num=`; `GET prices/{num}`; `POST prices/{num}/refresh?max_age_hours=`; `PUT prices/{num}/manual`; `POST prices/lookup/{num}`; `GET/POST/DELETE prices/checks` |
| štatistiky | `GET stats/summary`, `breakdown`, `sales`, `timeline` (všetky s `real`), `movers?window=30/90/365`, `series` |
| figúrky | `GET minifigs/series`, `minifigs/series/{num}`; `GET/POST minifigs/sync` |
| témy | `GET themes`, `themes/years?theme=`, `themes/wave?theme=&year=&force=` |
| Chcem | `GET/POST wishlist` (`?unless_owned=true` pri Späť po skene); `PATCH/DELETE wishlist/{id}` |
| zdieľanie | `GET/POST share`; `PATCH/DELETE share/{id}`; `GET public/{token}` |
| import | `GET imports/template.xlsx`, `imports/template.csv`; `GET/POST imports`; `GET/DELETE imports/{id}`; `POST imports/{id}/commit`, `imports/{id}/undo` |
| iné | `GET export/items.csv`; `GET usage`; `GET providers/status`; `GET health` (stav a verzia appky) |
| správa | `GET admin/users`, `PATCH admin/users/{id}`; `GET/PATCH admin/settings` |

Pravidlá API:

- **Sumy** chodia ako reťazec s dvomi desatinnými miestami (`Money`).
- **Filtre** zoznamu, zoskupeného zoznamu aj počtov sú jeden `ItemFilter`
  (`services/filters.py`):
  - v skupine platí ALEBO, medzi skupinami A;
  - skupina sa zadáva opakovaním parametra (`?theme=a&theme=b`);
  - hodnota „nič“ je `__none__`;
  - `sets_only` je rozsah sekcie Zbierka, nie filter: vyradí figúrky zo
    sérií (`kind_of`) aj z ponuky volieb (`in_section`);
  - počet pri voľbe ráta s ostatnými skupinami, nie s vlastnou. Voľba,
    po ktorej by nič neostalo, zošedne, ale ostane.
- **`Literal` na číselnom query parametri nefunguje**, lebo hodnota príde
  ako reťazec. Rozsah sa kontroluje v tele funkcie.
- **CSV export** je s bodkočiarkou, desatinnou čiarkou a BOM, kvôli
  slovenskému Excelu. Stĺpce sú rovnaké ako pri importe, takže export sa dá
  upraviť a nahrať späť.

---

## 11. Pravidlá rozhrania

- **Jazyk.** Slovenčina, druhý jazyk je angličtina. Všetky texty idú cez
  `t()`. Slovenské množné čísla majú tri tvary (1 set, 2–4 sety, 5 setov):
  kľúče končia na `Plural` a pravidlo je v `plugins/i18n.ts`.
- **Čísla** (`utils/format.ts`): desatinná čiarka, znak eura za číslom
  a tisíce oddelené nezlomiteľnou medzerou, aby sa suma nezlomila do dvoch
  riadkov.
- **Ceny.** Chýbajúca cena je pomlčka, odvodená cena má pred sebou ≈
  a kladný alebo záporný zisk má farbu.
- **Fotky setov sa neorezávajú.** Sety sú široké, figúrky vysoké.
  Chýbajúca fotka je nakreslená krabica.
- **Dátumy** sa zadávajú výhradne cez `DateField.vue` (obal nad
  `v-date-input`). Model je text `RRRR-MM-DD` a prevod ide cez miestny čas,
  nie `toISOString`, ktoré by dátum posunulo o deň. Vuetify má jazyk
  prepojený s appkou (`App.vue`), takže kalendár je po slovensky,
  s pondelkom ako prvým dňom a formátom dd.mm.rrrr. Natívne
  `type="date"` sa nepoužíva.
- **Našepkávače.** Kde uložené, Kde kúpené a kanál predaja ponúkajú už
  použité hodnoty zo servera (`GET /suggestions`), rovnaké na počítači
  aj na telefóne. Hodnoty líšiace sa len veľkosťou písmen sú jedna.
- **Nastavenia** majú jednu šírku pre všetky záložky, aby menu neposkakovalo.
  Formuláre sú v nej užšie, širokú tabuľku má len náhľad importu.
- **Mriežka kariet** sa riadi dostupnou šírkou (`CardGrid`), nie
  breakpointmi.
- **Vlastné komponenty treba importovať.** Chýbajúci import sa prejaví
  prázdnym miestom bez chyby.
- **Svetlý aj tmavý režim.** Primárna farba je LEGO červená `#D01012`,
  sekundárna žltá `#F5C518`.
- **Telefón.** Spodná navigácia, panel filtrov cez celú obrazovku, stránka
  sa posúva normálne.
- **Skryť ceny** (oko v hornej lište): každá suma v appke je „••• €“,
  percentá a počty ostávajú; pamätá sa pri účte. Na ukazovanie portfólia.
- **Bočné menu** sa dá zúžiť na ikony a znova rozbaliť; stav, tmavý režim
  aj inflácia sú pri účte (`preferences.display`), jazyk v profile.
- **Umiestnenie** je miestnosť a krabica (`PlaceFields.vue`), všade
  zobrazené ako „Povala · krabica 3“.
- **Oznámenia.** Každé pridanie, úprava a zmazanie ohlási výsledok cez
  `stores/notify.ts` (`success`, `error`, `info`, voliteľne jedno tlačidlo
  ako Späť). Fronta `v-snackbar-queue` je raz v `AppLayout`. Chyba, ktorá
  patrí k poľu formulára, ostáva pri poli; komponenty nemajú vlastné
  snackbary.
- **index.html sa nekešuje** (`cache-control: no-cache`). Súbory s
  otlačkom v názve sa kešujú na rok. Inak by si prehliadač držal starú
  appku.

---

## 12. Zamietnuté a odložené

| čo | prečo |
|---|---|
| BrickLink ako zdroj cien | vyžaduje účet predajcu a kľúče viazané na IP, domáci server pevnú adresu nemá |
| BrickOwl | ceny až po schválení prístupu ku katalógu |
| eBay | produkčný prístup cez schvaľovanie |
| sťahovanie stránok (BrickLink, BrickEconomy, obchody) | porušuje podmienky a je krehké |
| ponuky a akcie z obchodov | chýba zdroj bez sťahovania stránok; zvážené 2026-09-26 a odložené |
| obnova cien pri prihlásení alebo plánovačom | tíško by míňala kvótu; používateľ chce kontrolu tlačidlom |
| verejná registrácia | appka je pre rodinu, registráciu otvára správca |
| PDF na serveri | prehliadač zvláda diakritiku aj fotky sám |
| vlastné voľné tagy | nahradili ich kategórie s pravidlami a štítky z Brickset |
| reset hesla emailom | zatiaľ netreba, účty zakladá správca |

**Zvážené, zatiaľ nerobené:**

- **Poradie obnovy cien podľa dôležitosti:** drahé sety a sety s pohybom
  ceny častejšie, lacné mesačne.
- **Nočné automatické dočerpanie** zvyšku kvóty.

---

## 13. Testovanie a prevádzka

- **Backend:**
  - pytest s databázou v pamäti;
  - zdroje proti uloženým odpovediam cez `respx`, bez siete; fixtúry sú
    odpísané z reálnych odpovedí vrátane setu, ktorý je ešte v predaji;
  - `conftest.py` nastavuje len tajomstvo, databázu a vypnutú infláciu
    a nuluje stav modulov (obnova, série, Brickset, témy, inflácia).
- **Frontend:** `npm run type-check`, `npm run lint`, `npm test`.
- **Ručné overenie:**
  - vždy na kópii databázy (`data/lego.db` skopírovaná do dočasného
    priečinka), server na porte 8001 s vlastným `DATABASE_URL`,
    `PHOTOS_DIR` a `JWT_SECRET`;
  - na kópii sa zmení email a heslo prvého účtu;
  - kópia sa po skončení zmaže;
  - živá databáza sa na testy nepoužíva nikdy.
- **Po zmene API:** `uv run python -m lego_api.openapi_export`
  a `npm run gen:api`. **Po zmene modelu:** migrácia cez
  `alembic revision --autogenerate`; nový stĺpec NOT NULL potrebuje
  `server_default`.
- **Nasadenie:** `docker compose up -d --build` a kontrola
  `GET /api/v1/health` (vráti aj verziu, napríklad `1.0.0`).
- **Verzia appky:** jediný zdroj je `version` v `backend/pyproject.toml`
  (`lego_api.__version__` cez metadáta balíka; hlási ju `/health`,
  OpenAPI aj Nastavenia → Aplikácia). Pri vydaní sa zvýši spolu
  s `uv lock` a verziou vo `frontend/package.json` (aj `package-lock.json`),
  zhodu stráži `tests/test_version.py`. Zmena verzie spustí pri štarte
  zálohu databázy. Prvé vydanie je 1.0.0.
