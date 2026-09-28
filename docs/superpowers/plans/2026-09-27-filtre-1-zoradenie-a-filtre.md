# Filtre 1: zoradenie, rozsahy, nové filtre, hľadanie, import

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbierka sa dá zoradiť desiatimi spôsobmi v oboch smeroch (aj zoskupená), filtrovať rozsahmi, novými skupinami a podľa importu, a hľadanie ignoruje diakritiku.

**Architecture:** Zoradenie dostane register `services/sorting.py`, ktorý používa zoznam kusov aj zoskupený zoznam; router nič neradí sám. Nové filtre sú polia `ItemFilter`, predikáty v `PREDICATES` a skupiny vo `facets()` v `services/filters.py`. Frontend ich číta z `FacetsOut` a kreslí cez `FilterOption`.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest; Vue 3, Vuetify 4, Pinia, vue-i18n.

**Spec:** `docs/superpowers/specs/2026-09-27-filtre-a-prehlad-design.md` (body 1–5 a ich časť v paneli). Plán 2 (tabuľka, hromadná úprava) a plán 3 (Chcem, Témy, Figúrky, rozsah Prehľadu) nasledujú.

## Global Constraints

- Filtre len v `services/filters.py`, zoradenie len v `services/sorting.py`; router ich len volá.
- Prázdne hodnoty (bez ceny, bez dátumu, bez hodnotenia) sú pri zoradení vždy na konci, v oboch smeroch.
- Poradie volieb v paneli je podľa celej zbierky (`universe`), vybraná voľba červená (`FilterOption`).
- Hodnota „nič“ je `__none__` (`NONE`) na oboch stranách.
- Parametre API a adresy stránky majú rovnaké mená; predvolené hodnoty sa do adresy nepíšu.
- Rozhranie po slovensky aj anglicky, sumy cez `utils/format.ts`, dátumy cez `DateField`.
- Nič nevolá cudzie služby.

## Review Focus

- Zisk vzostupne pri kusoch bez ceny: kus bez ceny je na konci, nie navrchu (test v úlohe 1).
- Zoskupená karta série pri zoradení podľa roku: rozhoduje rok série, nie prvej figúrky (test v úlohe 1).
- Hľadanie „lego   technic“ s viacerými medzerami a veľkými písmenami funguje ako „lego technic“ (test v úlohe 3).
- Rozsah ceny „od 50“ bez „do“ a kus bez kúpnej ceny: kus bez ceny do rozsahu nepatrí (test v úlohe 2).
- Filter importu s id, ktoré patrí inému účtu: neukáže nič a nepadne (test v úlohe 2).

---

### Task 1: Register zoradenia a oprava zoskupeného zoznamu

**Files:**
- Create: `backend/src/lego_api/services/sorting.py`
- Modify: `backend/src/lego_api/routers/items.py` (parametre `sort`, `dir`; `list_items`, `list_grouped`)
- Test: `backend/tests/test_sorting.py`

**Interfaces:**
- Produces: `SORT_KEYS: tuple[str, ...]`, `Group(head: CatalogItem, members: list[ValuedItem])`,
  `sort_items(valued: list[ValuedItem], key: str, direction: str | None) -> list[ValuedItem]`,
  `sort_groups(groups: list[Group], key: str, direction: str | None) -> list[Group]`.
  `direction` je `"asc"`, `"desc"` alebo `None` (predvolený smer kľúča).

- [ ] **Step 1: Test** – `tests/test_sorting.py` nad `ValuedItem` postavenými v pamäti:
  zisk zostupne a vzostupne, kus bez ceny na konci v oboch smeroch; rok zostupne;
  názov A→Z predvolene; skupina série sa radí podľa roku hlavičky; skupiny podľa
  súčtu zisku; neznámy kľúč vyhodí `ValueError`.

```python
def test_missing_value_is_last_in_both_directions():
    a, b, none = _v("1-1", 100, 150), _v("2-1", 100, 120), _v("3-1", 100, None)
    assert [v.catalog.catalog_num for v in sort_items([none, b, a], "profit", "desc")] == ["1-1", "2-1", "3-1"]
    assert [v.catalog.catalog_num for v in sort_items([none, a, b], "profit", "asc")] == ["2-1", "1-1", "3-1"]
```

- [ ] **Step 2:** `uv run pytest tests/test_sorting.py` → FAIL (modul neexistuje).
- [ ] **Step 3: Implementácia** – `SortSpec(item, group, descending)`; hodnota `None` ide
  mimo radenia na koniec; zhoda sa rozhodne názvom. Kľúče: `profit, profit_pct, cagr,
  value, purchase, purchased, year, parts, name, recent`. Hodnoty kusu:

```python
def _profit(v): return v.realized if v.item.status == ItemStatus.SOLD else (None if v.price_source == "missing" else v.unrealized)
def _value(v): return v.gross_proceeds if v.item.status == ItemStatus.SOLD else (None if v.price_source == "missing" else v.market_value)
```

  Skupina: súčet známych hodnôt kusov (zisk, hodnota, kúpna), `collection_cagr`,
  najnovší dátum (kúpa, pridané), inak hodnota hlavičky (rok, dieliky, názov).
- [ ] **Step 4: Router** – `sort: Literal[*SORT_KEYS] = "profit"`, `dir: Literal["asc","desc"] | None = None`
  v `list_items` aj `list_grouped`; `list_grouped` si drží `Group` pri každom riadku a radí
  cez `sort_groups` (dnes vždy podľa zisku – chyba).
- [ ] **Step 5:** `uv run pytest` → PASS; `ruff check`.
- [ ] **Step 6: Commit** „Zoradenie: register, smer, zoskupený zoznam sa radí“.

### Task 2: Nové filtre a rozsahy v `ItemFilter`

**Files:**
- Modify: `backend/src/lego_api/services/filters.py`, `backend/src/lego_api/routers/items.py` (`item_filter`),
  `backend/src/lego_api/schemas/__init__.py` (`FacetsOut`), `backend/src/lego_api/services/portfolio.py`
  (`ValuedItem.price_at`, `SnapshotIndex.captured_at`)
- Test: `backend/tests/test_filters_extra.py`

**Interfaces:**
- Produces (query parametre = polia `ItemFilter`): `bought_from: date|None`, `bought_to: date|None`,
  `price_min/price_max: Decimal|None` (kúpna za kus), `value_min/value_max: Decimal|None`
  (trhová za kus), `place: list[str]` (kde kúpené, `NONE`), `channel: list[str]` (kanál predaja),
  `rating_min: float|None`, `growth: list["up"|"down"|"none"]`,
  `source: list["market"|"market_approx"|"manual"|"missing"|"stale"]`, `retired_recent: bool`,
  `imported: list[int]` (id importu).
- `FacetsOut` pribudne: `place, channel, growth, source, imported: list[FacetOption]`,
  `rating: list[FacetOption]` (hodnoty `"3.5","4","4.5"`, počet kusov s hodnotením aspoň toľko),
  `retired_recent: int`, hranice `bought_min/bought_max: date|None`,
  `price_low/price_high`, `value_low/value_high: Money|None`.
- `ValuedItem.price_at: datetime | None` – čas snímky, z ktorej je hodnota; `stale` = starší ako 30 dní.

- [ ] **Step 1: Test** pre každý predikát (zahrnie/vylúči, `NONE`, prázdny výber nefiltruje),
  rozsah bez druhej hranice, kus bez ceny mimo rozsahu hodnoty, `source=stale`,
  `retired_recent`, `imported` s cudzím id, a že nové skupiny sú vo `facets()`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: Implementácia** – polia, predikáty, skupiny vo `facets()` cez `_options`
  s `universe`; import skupina s popisom „súbor · dátum“ z `ImportBatch` účtu;
  hranice rozsahov z `base(skip)` ako pri roku. `SnapshotIndex.value_at_any` vráti aj čas.
- [ ] **Step 4:** PASS, `ruff`.
- [ ] **Step 5: Commit** „Filtre: rozsahy kúpy a hodnoty, kde kúpené, kanál, hodnotenie, rast, pôvod ceny, import“.

### Task 3: Hľadanie bez diakritiky, viac polí, viac slov

**Files:** Modify `backend/src/lego_api/services/filters.py` (`_q`); Test `backend/tests/test_filters_extra.py`.

- [ ] **Step 1: Test** – „hradna“ nájde „Hradná“, „TECHNIC   2024“ = obe slová, hľadá aj
  v poznámke, kde kúpené, podtéme a štítkoch.
- [ ] **Step 2:** FAIL. **Step 3:** `fold()` = NFKD bez znamienok, `casefold`; všetky slová
  musia byť v spojenom texte polí. **Step 4:** PASS. **Step 5: Commit**.

### Task 4: Panel filtrov, čipy a zoradenie vo Zbierke

**Files:**
- Modify: `frontend/src/stores/filters.ts` (polia, `query`, `fromRoute`, `activeCount`),
  `frontend/src/components/FilterPanel.vue` (sekcie Kúpa a hodnota, Predaj, Brickset,
  Pôvod ceny, Import), `frontend/src/components/ActiveFilters.vue` (čipy),
  `frontend/src/stores/collection.ts` (`sortDir`), `frontend/src/views/CollectionView.vue`
  (voľby zoradenia, tlačidlo smeru, adresa `sort`/`dir`), `frontend/src/components/ImportPanel.vue`
  (Otvoriť Zbierku s `imported=<id>`), `frontend/src/locales/sk.json`, `en.json`.

- [ ] **Step 1:** `npm run gen:api` po exporte schémy.
- [ ] **Step 2:** Úložisko: nové zoznamy do `LIST_KEYS` (`place, channel, growth, source`),
  `imported: number[]`, rozsahy a `rating_min`, `retired_recent`; zápis do adresy a späť.
- [ ] **Step 3:** Panel: sekcie z `facets`, rozsahy cez `DateField` a číselné polia s hranicami
  ako placeholder; hodnotenie ako výber „aspoň 3,5 / 4 / 4,5“ s počtami.
- [ ] **Step 4:** Čipy pre každý nový filter (rozsah ako „Kúpené 1. 1. 2024 – …“).
- [ ] **Step 5:** Zoradenie: 10 volieb, tlačidlo ↑↓, `dir` do API aj adresy len mimo predvoleného.
- [ ] **Step 6:** `npm run type-check && npm run lint && npm test`.
- [ ] **Step 7:** Overenie na kópii DB na :8001 (zoradenie Podľa setu reaguje, rozsah, hľadanie
  „hradna“, filter importu), commit, `docker compose up -d --build`, health.

### Task 5: Dokumentácia

- [ ] CLAUDE.md: register zoradenia (`services/sorting.py`), pravidlo „prázdne na konci“, nové
  filtre. Úplný spec: kapitola Zbierka a API. Počet testov. Commit.
