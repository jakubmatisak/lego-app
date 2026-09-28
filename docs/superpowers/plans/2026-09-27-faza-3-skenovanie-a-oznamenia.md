# Fáza 3: skenovanie, pamäť formulára, oznámenia, doplnená kúpna cena — plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pridávanie len skenovaním čítačkou odkiaľkoľvek, formulár si pamätá
zvolené polia, každá akcia sa ohlási oznámením, neúspešné kódy sa nepýtajú
znova a kúpna cena sa dá doplniť z odporúčanej.

**Architecture:** Backend: tabuľka neúspechov kódov v `services/barcode.py`,
príznak `purchase_price_auto` a doplnenie v `services/refresh.py` cez nový
`services/purchase_fill.py`, nový filter v `services/filters.py`. Frontend:
store `notify` s jednou `v-snackbar-queue` v layoute, čisté funkcie
`useFormMemory` a `scanFlow`, globálny odberateľ skenov v `AppLayout`,
bez Web Serial.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest+respx; Vue 3, Vuetify 4.2, Pinia, vitest.

**Spec:** `docs/superpowers/specs/2026-09-27-faza-3-skenovanie-a-oznamenia-design.md`

## Global Constraints

- Rozhranie aj komentáre po slovensky; množné číslo cez kľúče `…Plural`.
- Sumy z API ako `Money` (reťazec, dve desatinné miesta).
- Každé volanie von ide cez bránu schopností; nič nové nesmie minúť kvótu.
- Po zmene API: `uv run python -m lego_api.openapi_export`, potom `npm run gen:api`.
- Vlastné komponenty sa v šablóne importujú ručne.
- Testovať len na kópii DB na :8001; po úlohe `docker compose up -d --build` na :8000.
- Commit končí `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Sken počas prebiehajúceho ukladania alebo hľadania: skeny sa musia spracovať v poradí, žiadny sa nestratí, nič sa neuloží dvakrát.
2. Späť po automatickom uložení, keď medzitým prišiel ďalší sken: zmaže len kusy toho uloženia.
3. Doplnenie ceny sa nesmie dotknúť predaného kusu, kusu s cenou ani kusu iného účtu, a nesmie stáť volanie navyše.
4. Zapamätaný neúspech kódu sa nesmie vrátiť, keď kód medzitým pribudol do katalógu (katalóg má prednosť).
5. Globálny odberateľ skenov nesmie brať písanie do polí (rýchlosť rozhoduje detektor) a nesmie bežať mimo prihlásenej časti.

---

### Task 1: Kúpna cena doplnená automaticky — backend

**Files:**
- Create: `backend/src/lego_api/services/purchase_fill.py`, migrácia `backend/alembic/versions/*_doplnena_kupna_cena_a_neuspesne_kody.py` (spoločná s Task 2)
- Modify: `models/collection.py`, `services/fetch_policy.py`, `services/sources.py`, `schemas/__init__.py` (`SourcesUpdate`, `ItemOut`, zdroj), `auth/router.py`, `services/refresh.py`, `routers/items.py` (PATCH), `services/filters.py`, `routers/items.py` (query `purchase`)
- Test: `backend/tests/test_purchase_fill.py`, doplnky v `test_fetch_policy.py`, `test_sources_api.py`, `test_filters_extra.py`

**Interfaces:**
- Produces: `FetchPolicy.auto_purchase_price: bool`; `fill_purchase_prices(session, user_id, *, rrp_by_num: dict[str, Decimal] | None = None, only: str | None = None) -> int`; `CollectionItem.purchase_price_auto: bool`; `ItemOut.purchase_price_auto`; zdroj brickeconomy má `auto_purchase_price: bool | None`; filter `purchase=manual|auto|none`.

- [ ] **Step 1: testy (RED)** v `tests/test_purchase_fill.py`:

```python
async def test_refresh_fills_missing_purchase_price_from_brickeconomy(session, sessionmaker_, fast_settings):
    # kus bez ceny, odpoveď s rrp 99.99 → cena 99.99, auto=True
async def test_fill_falls_back_to_catalog_rrp(session, sessionmaker_, fast_settings):
    # odpoveď bez rrp, katalóg rrp 80 → 80
async def test_fresh_items_are_filled_from_catalog_without_a_call(...):
    # čerstvá snímka, katalóg rrp 50 → 0 volaní, cena 50
async def test_switched_off_fills_nothing(...)
async def test_priced_sold_and_foreign_items_stay(...)
async def test_manual_price_change_clears_the_auto_flag(auth_client, ...)
async def test_filter_by_purchase_origin(...)
```
a v `test_fetch_policy.py` `parse_settings({"auto_purchase_price": True})` → `{"auto_purchase_price": True}`, `"áno"` → ValueError; `test_sources_api.py` PUT/GET prepínača.

- [ ] **Step 2:** `uv run pytest tests/test_purchase_fill.py -q` → FAIL (modul chýba).
- [ ] **Step 3:** model + migrácia (`purchase_price_auto` Boolean `server_default=sa.false()`), policy a `parse_settings` (bool), `policy_of`, `SourcesUpdate.auto_purchase_price: bool | None`, `sources_of` pre brickeconomy, `purchase_fill.py`, v `refresh_prices` zbierať `rrp_by_num` z `_refresh_one` (vracia `MarketData | None`) a v `finally` zavolať `fill_purchase_prices` pri zapnutom prepínači; PATCH: ak `purchase_price_eur` v dátach → `purchase_price_auto=False`; filter.
- [ ] **Step 4:** `uv run pytest -q` → všetko zelené; `ruff check`.
- [ ] **Step 5:** commit „Kúpna cena doplnená z odporúčanej: backend“.

### Task 2: Pamäť neúspešných kódov — backend

**Files:**
- Create: `backend/src/lego_api/models/barcode_miss.py`
- Modify: `models/__init__.py`, migrácia z Task 1, `services/barcode.py`, `routers/catalog.py`, `schemas/__init__.py` (`EanLookupOut.cached`, `checked_at`)
- Test: `backend/tests/test_barcode.py`

**Interfaces:**
- Produces: `find_by_ean(..., retry: bool = False)`; `EanResult.cached: bool`, `EanResult.checked_at: datetime | None`; `MISS_TTL = timedelta(days=30)`; `GET /catalog/by-ean/{code}?retry=`.

- [ ] **Step 1: testy (RED)**: zapamätaný neúspech bez volania; po 31 dňoch volanie; `retry=True` volá; limit sa nepamätá; nájdený kód zmaže neúspech; `PUT /catalog/{num}/ean` zmaže neúspech; iný účet volá.
- [ ] **Step 2:** `uv run pytest tests/test_barcode.py -q` → FAIL.
- [ ] **Step 3:** implementácia (používateľ = `keys.policy.user_id`; bez neho sa nepamätá nič).
- [ ] **Step 4:** celý backend zelený, ruff.
- [ ] **Step 5:** export schémy + `npm run gen:api`; commit „Neúspešné kódy sa 30 dní nepýtajú znova“.

### Task 3: Oznámenia — store a layout

**Files:**
- Create: `frontend/src/stores/notify.ts`, `frontend/src/stores/notify.spec.ts`
- Modify: `layouts/AppLayout.vue`

**Interfaces:**
- Produces: `useNotifyStore()` s `queue`, `success(text, action?)`, `error(text)`, `info(text)`, `actionFor(id)`, `run(id)`; `NoticeAction = { label: string, run: () => void | Promise<void> }`.

- [ ] **Step 1: test (RED)**: `success` pridá `{text, color:'positive', timeout:3000}`; `error` `color:'negative'`, 6000; s akciou 8000 a `data-notice`; `run(id)` zavolá akciu; `onDismiss` akciu zabudne.
- [ ] **Step 2:** `npx vitest run src/stores/notify.spec.ts` → FAIL.
- [ ] **Step 3:** store + `<v-snackbar-queue v-model="notify.queue" closable total-visible="3">` so slotom `actions`.
- [ ] **Step 4:** vitest zelený, type-check, lint.
- [ ] **Step 5:** commit.

### Task 4: Oznámenia na všetkých miestach

**Files:** `AddSetView.vue`, `PurchaseDialog.vue`, `SeriesPurchaseDialog.vue`, `GhostCard.vue`, `WishlistView.vue`, `SetDetailView.vue`, `stores/collection.ts`, `CategoryManager.vue`, `CategoryMembership.vue`, `PhotosDialog.vue`, `stores/filters.ts`, `SettingsView.vue`, `SourceCard.vue`, `ImportPanel.vue`, `ExportCsvButton.vue`, `locales/sk.json`, `locales/en.json`.

- [ ] **Step 1:** test v `stores/collection.spec.ts`: zlyhaný predaj pošle chybu do `notify` (RED).
- [ ] **Step 2:** vitest → FAIL.
- [ ] **Step 3:** doplniť `notify.success/error` na každé miesto zo specu, odstrániť lokálne snackbary.
- [ ] **Step 4:** vitest, type-check, lint zelené.
- [ ] **Step 5:** commit.

### Task 5: Pamäť formulára

**Files:**
- Create: `frontend/src/composables/useFormMemory.ts`, `frontend/src/composables/useFormMemory.spec.ts`, `frontend/src/components/FormMemoryCard.vue`
- Modify: `backend/src/lego_api/auth/router.py` (`PREFERENCE_KEYS` + `form`), `backend/tests/test_preferences.py`, `stores/preferences.ts` (typ kľúča), `SettingsView.vue` (záložka Formuláre), `AddSetView.vue`, `PurchaseDialog.vue`, `SeriesPurchaseDialog.vue`, locales.

**Interfaces:**
- Produces: `FORM_FIELDS = ['location','condition','purpose','place','date'] as const`; `initialForm(pref: FormPreference | null, today: string): FormValues`; `rememberForm(pref, values): FormPreference`; `useFormMemory()` → `{ initial(): FormValues, remember(values): void, remembered: ComputedRef<Record<FormField, boolean>>, setRemember(field, on) }`.

- [ ] **Step 1: testy (RED)**: vypnuté → `{location:'', condition:'new_sealed', purpose:null, place:'', date:today}`; zapnuté → posledné; `rememberForm` zapíše všetko; backend PUT `/auth/me/preferences/form` → 200.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** implementácia a napojenie.
- [ ] **Step 4:** zelené.
- [ ] **Step 5:** commit.

### Task 6: Skenovanie odkiaľkoľvek, bez Web Serial

**Files:**
- Create: `frontend/src/scanner/scanFlow.ts`, `frontend/src/scanner/scanFlow.spec.ts`
- Modify: `stores/scanner.ts`, `scanner/codes.ts`, `scanner/codes.spec.ts`, `scanner/useScanCodes.ts`, `components/ScannerConnect.vue`, `layouts/AppLayout.vue`, `views/AddSetView.vue`, `env.d.ts`, `package.json`, locales, `CLAUDE.md`, `docs/superpowers/specs/2026-09-10-lego-collection-design.md`

**Interfaces:**
- Produces: `decideScan(current: { code: string | null, pending: boolean }, code: string): 'increment' | 'save-and-load' | 'load'`; `sameCode(a, b)` (porovnanie číslic).

- [ ] **Step 1: testy (RED)**: rovnaký kód a neuložené → increment; rovnaký s medzerami/nulou UPC → increment; iný → save-and-load; nič → load.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** scanFlow, odstránenie sériovej časti, globálny odberateľ v layoute, `?code=`, `saveCurrent`, automatické uloženie so Späť, fronta skenov.
- [ ] **Step 4:** vitest, type-check, lint; overenie na kópii (`scanner.emit` z konzoly).
- [ ] **Step 5:** commit.

### Task 7: Doplnená cena a neúspešné kódy — rozhranie

**Files:** `SourceCard.vue`, `composables/useSources.ts` (+spec), `SetCard.vue`, `SetDetailView.vue`, `PieceDialog.vue`, `stores/filters.ts` (+spec), `components/FilterPanel.vue`, `composables/useFilterLabels.ts`, `AddSetView.vue` (Skúsiť znova), locales.

- [ ] **Step 1: testy (RED)**: `useSources.setAutoPurchase(true)` pošle `{auto_purchase_price: true}`; filters store číta a píše `purchase` z adresy.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** implementácia.
- [ ] **Step 4:** zelené; overenie na kópii.
- [ ] **Step 5:** commit.

### Task 8: Dokumentácia a nasadenie

- [ ] CLAUDE.md: pravidlá pre oznámenia, skenovanie, pamäť formulára, doplnenú cenu, neúspešné kódy; počet testov.
- [ ] Spec: stav „implementované“.
- [ ] `docker compose up -d --build`, `/api/v1/health`.
- [ ] commit.
