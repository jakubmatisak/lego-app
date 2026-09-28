# Pravidlá sťahovania a karty služieb: implementačný plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Každé volanie cudzej služby prejde bránou, ktorú riadia prepínače účtu, a Nastavenia → Dáta ukazujú služby ako karty s tým, čo odomknú.

**Architecture:** Register schopností `lego_api/capabilities.py`, pravidlá účtu `services/fetch_policy.py` (`FetchPolicy` v `UserKeys.policy`), brána pred jediným miestom volania v každom zdroji. História volaní berie účel zo schopnosti. API `/auth/me/sources`; frontend kreslí karty zo zoznamu a skrýva cez `auth.can(cap)`.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest + respx; Vue 3, Vuetify 4, Pinia, vue-i18n.

**Spec:** `docs/superpowers/specs/2026-09-27-pravidla-stahovania-design.md`

## Global Constraints

- Predvolene je všetko zapnuté; bez zmeny nastavení sa appka správa ako dnes.
- Povinné schopnosti (`rebrickable.set`, `brickset.usage`) sa vypnúť nedajú.
- Rezerva platí len pre triedu „na pozadí“; predvolene Brickset 20, BrickEconomy 0.
- Zablokované volanie neodíde a zdroj vráti „nič“; appka nespadne.
- Nastavenia pri účte (`users.fetch_settings`), záložka Dáta v Nastaveniach.
- Texty kariet a prepínačov v `locales` (sk, en), kľúč `capabilities.<cap>`, `sources.<provider>`.

## Review Focus

- Schopnosť s rezervou pri takmer minutom limite: dopĺňanie na pozadí sa zastaví, pridanie setu ešte prejde (úloha 1).
- Vypnutý Brickset pri pridaní setu: set vznikne z Rebrickable bez Brickset údajov, bez chyby (úloha 2).
- Vypnuté hľadanie kódu v Brickset aj UPCitemdb: sken povie „vypnuté v Nastaveniach“, nie „nenašlo sa“ (úloha 3).
- Uloženie nastavení s neznámym kľúčom alebo vypnutím povinnej schopnosti: 422 (úloha 3).
- Prepínač inflácie vypnutý: súčty výberu nesťahujú Eurostat (úloha 3).

---

### Task 1: Register, pravidlá účtu, brána

**Files:** Create `backend/src/lego_api/capabilities.py`, `backend/src/lego_api/services/fetch_policy.py`,
migrácia `users.fetch_settings`; Modify `models/user.py`, `services/keys.py` (`UserKeys.policy`, `keys_of`);
Test `backend/tests/test_fetch_policy.py`.

**Interfaces — Produces:**
- `Cap(StrEnum)`: `REBRICKABLE_SET, REBRICKABLE_SERIES_SYNC, BRICKSET_ON_ADD, BRICKSET_BACKFILL, BRICKSET_ON_DETAIL, BRICKSET_BARCODE, BRICKSET_WAVES, BRICKSET_THEMES, BRICKSET_USAGE, BRICKECONOMY_PRICES, BRICKECONOMY_PRICE_DETAIL, UPCITEMDB_BARCODE, EUROSTAT_INFLATION`.
- `CAPABILITIES: dict[Cap, CapSpec(provider, counted, background, required, hidden)]`, `PROVIDERS: dict[str, ProviderSpec(paid, needs_key, daily_limit)]`.
- `FetchPolicy(user_id, disabled: frozenset[str], reserve: dict[str,int], price_batch: int|None)`, `.enabled(cap)`, `policy_of(user)`, `parse_settings(raw) -> dict` (vyhodí `ValueError`).
- `async gate(policy, cap, *, remaining: int | None) -> str | None` — dôvod zablokovania (`"disabled"`, `"reserve"`, `"limit"`) alebo `None`.

- [ ] Test: vypnutá schopnosť → `"disabled"`; povinná vždy zapnutá; na pozadí pri `remaining <= reserve` → `"reserve"`, na požiadanie prejde až po 0 → `"limit"`; `parse_settings` odmietne neznámy kľúč a vypnutie povinnej.
- [ ] RED → implementácia → GREEN; migrácia; `UserKeys.policy` z `keys_of`. Commit.

### Task 2: Zdroje za bránou, história so schopnosťou

**Files:** Modify `providers/rebrickable.py`, `providers/brickset.py`, `providers/brickeconomy.py`,
`providers/upcitemdb.py`, `services/inflation.py`, `api_log.py`, `auth/deps.py`, volajúci
(`services/catalog.py`, `brickset_extras.py`, `refresh.py`, `cmf.py`, `themes.py`, `barcode.py`,
`importer.py`, routre). Test `backend/tests/test_fetch_gate.py`.

**Interfaces — Consumes:** úloha 1. **Produces:**
- `…Provider.for_user(settings, keys)`; konštruktor berie `policy=None` (povolí všetko).
- `BricksetProvider.get_item(num, *, cap)`, `BrickEconomyProvider.get_market(num, kind, *, cap)`; ostatné metódy nesú schopnosť v sebe.
- `api_log.record(provider, action, subject, ok, status=None, counted=True, *, cap)`, `api_log.set_user(user_id)`; `ENDPOINT_PURPOSES` a `set_purpose` zaniknú.

- [ ] Test: pri vypnutej schopnosti každý zdroj nepošle požiadavku (respx nula volaní) a vráti nič; pridanie setu s vypnutým `brickset.on_add` vytvorí set z Rebrickable; záznam histórie nesie `purpose == cap`.
- [ ] RED → implementácia → GREEN; celá sada (úpravy existujúcich testov, kde volajú `get_item` Brickset bez `cap`). Commit.

### Task 3: API zdrojov, Eurostat, čiarový kód

**Files:** Modify `auth/router.py` (`/auth/me/sources`, `ApiKeysOut.capabilities`), `schemas`,
`services/inflation.py` (`deflator_for(session, real, policy)`), `routers/items.py`, `routers/stats.py`,
`services/barcode.py` (`EanResult("disabled")`), `routers/catalog.py`. Test `backend/tests/test_sources_api.py`.

- [ ] Test: GET vráti služby v poradí úrovní so schopnosťami a stavom; PUT uloží a odmietne neznáme a povinné (422); `capabilities` v `/auth/me/keys` bez služby bez kľúča; vypnutá inflácia → súčty bez Eurostatu; vypnuté hľadanie kódu → `status == "disabled"`.
- [ ] RED → implementácia → GREEN. Commit.

### Task 4: Frontend

**Files:** Create `frontend/src/components/SourceCard.vue`; Modify `stores/auth.ts` (`can`),
`views/SettingsView.vue` (záložka Dáta), `layouts/AppLayout.vue`, `views/DashboardView.vue`,
`components/FilterPanel.vue`, `views/CollectionView.vue`, `views/SetDetailView.vue`,
`views/AddSetView.vue` (hláška „vypnuté“), `components/ApiUsageDialog.vue` (popis účelu zo schopnosti), locales.

- [ ] Vitest: `auth.can`. Type-check, lint, test. Overenie na kópii DB, commit, nasadenie.

### Task 5: Dokumentácia

- [ ] CLAUDE.md (brána, schopnosti, zánik `ENDPOINT_PURPOSES`), úplný spec (kapitola zdroje, API, Nastavenia), počet testov. Commit.
