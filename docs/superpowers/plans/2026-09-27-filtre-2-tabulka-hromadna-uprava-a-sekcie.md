# Filtre 2 a 3: tabuľka, hromadná úprava, Chcem, Témy, Figúrky, rozsah Prehľadu — plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Body 6–11 zo specu filtrov: hromadná úprava kusov, zobrazenie
tabuľkou, zoradenie a filtre v Chcem, Témach a Figúrkach a rozsah Prehľadu
podľa filtra Zbierky.

**Architecture:** Všetko ide cez `ItemFilter` (`services/filters.py`)
a register zoradenia (`services/sorting.py`). Hromadná úprava je jeden
endpoint, ktorý dostane zoznam kusov alebo filter. Štatistiky Prehľadu
berú ten istý filter ako Zbierka. Chcem a Témy radí a filtruje server,
Figúrky klient (zoznam sérií je malý a celý na obrazovke).

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest; Vue 3, Vuetify 4 (`v-data-table-virtual`), Pinia, vitest.

**Spec:** `docs/superpowers/specs/2026-09-27-filtre-a-prehlad-design.md` (body 6–11)

## Global Constraints

- Filter Zbierky je jazyk celej appky: hromadná úprava, tabuľka aj Prehľad berú `ItemFilter`, router nič nefiltruje ani neradí sám.
- Nerealizovaný a realizovaný zisk sa nesčítavajú; do hodnoty vstupujú len vlastnené kusy.
- Bez trhovej ceny pomlčka, odvodená cena so znakom ≈.
- Nič z toho nevolá cudzie služby.
- Rozhranie po slovensky, množné čísla cez `…Plural`, každá akcia ohlási výsledok cez `notify`.
- Testovať na kópii DB na :8001, po každom kroku commit a `docker compose up -d --build`.
- Commit končí `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Hromadná úprava filtrom sa nesmie dotknúť predaných kusov ani kusov iného účtu a musí meniť presne to, čo Zbierka s tým filtrom ukazuje.
2. Hromadné vyradenie z kategórie musí vytvoriť výnimku len tam, kde by set inak do kategórie patril (pravidlo), a nič neduplikovať.
3. Prehľad s rozsahom: súčty dlaždíc sa musia zhodovať so súčtami výberu v Zbierke s tým istým filtrom.
4. Tabuľka pri 1500 riadkoch: nesmie načítať nič navyše a zoradenie hlavičkou musí ísť cez server.
5. Chcem bez trhovej ceny: blízkosť k cieľu je prázdna a radí sa na koniec v oboch smeroch.

---

### Task 1: Hromadná úprava — backend

**Files:** Create `backend/src/lego_api/services/bulk.py`; Modify `routers/items.py`, `schemas/__init__.py`; Test `backend/tests/test_bulk.py`.

**Interfaces:**
- Produces: `POST /items/bulk-update` s rovnakými query parametrami ako `GET /items` (filter) a telom `BulkUpdateRequest{item_ids: list[int] | None, catalog_nums: list[str] | None, changes: BulkChanges, dry_run: bool = False}`; `BulkChanges{location?, purpose?, condition?, flags_add: list[str], flags_remove: list[str], category_add: int | None, category_remove: int | None}` (prázdny reťazec pri location/purpose = zmazať); odpoveď `BulkUpdateOut{items: int, sets: int}`.
- Výber: `item_ids` → tie kusy; `catalog_nums` → vlastnené kusy s tým číslom alebo s rodičom série; inak celý výsledok filtra. Vždy len `status=owned` a len kusy účtu.

- [ ] Step 1: testy (RED): podľa zoznamu, podľa filtra (téma), podľa čísla setu aj série, predané sa nemenia, iný účet nie, príznaky pridať/odobrať bez duplicít, zlý príznak 422, kategória zaradiť/vyradiť (výnimka len proti pravidlu), `dry_run` nič nezmení a vráti počty.
- [ ] Step 2: FAIL. Step 3: implementácia. Step 4: `uv run pytest -q` zelené. Step 5: export schémy, gen:api, commit.

### Task 2: Hromadná úprava — Zbierka

**Files:** Create `frontend/src/composables/useSelection.ts` (+spec), `frontend/src/components/BulkBar.vue`, `frontend/src/components/BulkEditDialog.vue`; Modify `CollectionView.vue`, `SetCard.vue`, locales.

**Interfaces:**
- Produces: `createSelection()` → `{ active, all, itemIds, catalogNums, count(total), toggleItem(id), toggleGroup(num), selectAll(), clear(), payload(): {item_ids?, catalog_nums?} }`.

- [ ] Step 1: testy (RED) pre `createSelection`: prepínanie, „vybrať všetko“ = filter (payload bez zoznamov), vymazanie po zmene filtra.
- [ ] Step 2–4: implementácia, tlačidlo Vybrať, začiarkávatká na kartách a riadkoch, lišta s počtom a akciami, dialóg s hodnotou, potvrdenie s počtom z `dry_run`, oznámenie výsledku. Overenie na kópii.
- [ ] Step 5: commit, nasadenie.

### Task 3: Zobrazenie tabuľkou

**Files:** Create `frontend/src/components/CollectionTable.vue`, `frontend/src/utils/tableColumns.ts` (+spec); Modify `CollectionView.vue`, `stores/collection.ts` (`view: 'cards' | 'table'`), locales.

**Interfaces:** `COLUMNS` s kľúčom zoradenia (`sort: SortKey | null`); `sortFromHeader(column, current)` → `{ sort, dir }`.

- [ ] Step 1: test (RED) `sortFromHeader`: klik na stĺpec nastaví jeho kľúč s predvoleným smerom, druhý klik otočí smer, stĺpec bez kľúča nič.
- [ ] Step 2–4: `v-data-table-virtual`, stĺpce podľa specu, pri zoskupení riadok = set/séria, pri každom kuse kus; pomlčka a ≈; výber (Task 2) aj v tabuľke; prepínač sa pamätá v `preferences.collection.view`.
- [ ] Step 5: commit, nasadenie.

### Task 4: Chcem — zoradenie a filtre na serveri

**Files:** Modify `services/wishlist.py`, `routers/misc.py`, `schemas/__init__.py` (`WishlistOut.distance_pct`), `views/WishlistView.vue`; Test `backend/tests/test_wishlist.py`.

**Interfaces:** `GET /wishlist?sort=distance|market|target|name|theme|added&dir=&reached=&retired=&no_price=&q=`; `distance_pct = (market − target) / target · 100` (None bez ceny alebo cieľa), prázdne na konci v oboch smeroch.

- [ ] Step 1: testy (RED): každé zoradenie oboma smermi s prázdnymi na konci, filtre, hľadanie bez diakritiky (`filters.fold`).
- [ ] Step 2–4: implementácia a ovládanie v Chcem (hľadanie, čipy, zoradenie, smer).
- [ ] Step 5: commit, nasadenie.

### Task 5: Témy a Figúrky — zoradenie a filtre

**Files:** Create `frontend/src/utils/themeList.ts` (+spec), `frontend/src/utils/seriesList.ts` (+spec); Modify `ThemesView.vue`, `MinifigsView.vue`, locales.

**Interfaces:** `sortThemes(rows, key)` pre `mine|completeness|name`, `filterThemes(rows, { followed, withSets, incomplete })`; v Figúrkach stav `almost` (vlastním aspoň jednu, chýbajú najviac 2) a zoradenie `leastMissing`.

- [ ] Step 1: testy (RED) čistých funkcií.
- [ ] Step 2–4: napojenie do obrazoviek (Figúrky: presun `state`/`compare` do `seriesList.ts`).
- [ ] Step 5: commit, nasadenie.

### Task 6: Rozsah Prehľadu

**Files:** Modify `routers/stats.py`, `services/portfolio.py` (`series_progress` s obmedzením), `auth/router.py` (`PREFERENCE_KEYS` + `dashboard`), `stores/collection.ts` (`scope`, `navSummary`), `stores/preferences.ts`, `views/DashboardView.vue`, `layouts/AppLayout.vue`, `BreakdownCard.vue`, `PortfolioCard.vue`, `SalesCard.vue`; Create `frontend/src/components/ScopePicker.vue`; Test `backend/tests/test_stats_scope.py`.

**Interfaces:** `summary`, `timeline`, `breakdown`, `sales`, `movers`, `series` berú `FilterDep`; rozsah = `{ label, query }` (uložený pohľad, kategória, zoznam, téma).

- [ ] Step 1: testy (RED): súhrn s filtrom témy = súčty výberu (`/items/facets` totals) s tým istým filtrom; séria mimo rozsahu sa v `/stats/series` neukáže; bez filtra ako doteraz.
- [ ] Step 2–4: implementácia; štítok „Rozsah: …“ s krížikom; ponuka ostáva za celú zbierku (`navSummary`); rozsah sa pamätá pri účte.
- [ ] Step 5: commit, nasadenie.

### Task 7: Dokumentácia

- [ ] Spec filtrov: stav „body 6–11 implementované“; úplný spec a CLAUDE.md doplniť; počet testov.
