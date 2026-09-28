# Moje kocky

Evidencia zbierky LEGO® setov pre jednu rodinu alebo pár známych, na vlastnom
serveri. Zadáš alebo naskenuješ set, appka dotiahne názov, fotku, dieliky
a sériu z katalógu, ty doplníš kúpnu cenu, stav a kde ho máš uložený. Potom
vidíš trhovú hodnotu, zisk, ročný výnos a graf vývoja portfólia. Predané kusy
ostávajú v evidencii, takže vidíš aj to, koľko si na predaji naozaj zarobil.

Appka vznikla pre zberateľa, ktorý mal zbierku v tabuľke a chcel vedieť, čo
má, kde to má a koľko to dnes stojí. Nie je to obchod ani burza, len evidencia.

![Prehľad: hodnota portfólia, zisk a rozdelenie podľa sérií](docs/screenshots/prehlad.png)

![Zbierka: karty setov s filtrami](docs/screenshots/zbierka.png)

*Snímky sú z ukážkového účtu, sumy sú len na ilustráciu.*

## Čo to vie

**Evidencia**

- **Po kusoch.** Tri rovnaké sety sú tri záznamy, každý s vlastným stavom
  (v krabici, postavený, rozobratý…), cenou, dátumom a umiestnením.
- **Umiestnenie v dvoch úrovniach**: miestnosť a číslo krabice, s našepkávačom.
- **Mám to už?** Pri zadaní čísla sa ukáže výrazný pás, keď set v zbierke je.
- **Zberateľské minifigúrky.** Séria sa pridáva výberom z mriežky figúrok,
  nerozbalený sáčok sa po rozbalení priradí ku konkrétnej figúrke. Sekcia
  Figúrky pozná všetky série, aj nezačaté, a ukáže, čo chýba. Rovnako
  blind-box série iných radov (Mighty Machines, Super Mario a pod.).
- **Série a vlny.** Koľko setov z témy a roku máš, podľa zoznamu Brickset.
- **Vlastné kategórie** s pravidlami (napr. všetko s „F1“ v názve naprieč
  sériami) aj ručným zaradením.
- **Chcem**: zoznam želaných setov s cieľovou cenou a poznámkou. Set, ktorý na
  cieľ klesol, sa zvýrazní. „Kúpil som“ ho presunie do zbierky.
- **Vlastné fotky kusu** a **súpis pre poistku** na tlač alebo do PDF.
- **Galéria ďalších oficiálnych fotiek setu** z Brickset (dá sa vypnúť).

**Pridávanie**

- **Čítačka čiarových kódov** (USB, v režime klávesnice) aj **kamera** v
  prehliadači. Sken funguje z ktorejkoľvek obrazovky. Rovnaký kód zvýši
  počet, iný kód uloží rozpracovaný set a načíta nový; každé uloženie sa dá
  vrátiť tlačidlom Späť.
- **Pamäť formulára**: stav, dátum a umiestnenie z minulého setu sa predvyplnia.
- **Hromadný import** z Excelu alebo CSV so šablónou, náhľadom a vrátením.
  Export do CSV.
- **Bez kľúča Rebrickable** sa set dá uložiť ručne, len číslom.

**Peniaze**

- **Dva druhy zisku oddelene.** Nerealizovaný (trhová hodnota mínus kúpna
  cena toho, čo vlastníš) a realizovaný (čistý z predajov, po poplatkoch
  a poštovnom). Nikdy sa nesčítajú do jedného čísla.
- **Ročný výnos** kusu, série, zoznamu aj celej zbierky, od roka držania.
- **V dnešných peniazoch**: prepočet kúpnych cien infláciou (HICP Slovensko).
- **Odhad hodnoty** kusov v krabici o 2 a 5 rokov.
- **Kto sa hýbe**: zmena trhovej ceny za 30, 90 a 365 dní.
- **Overiť cenu**: v obchode naskenuješ krabicu a hneď vidíš, čo to je, či to
  máš, cenu nového aj použitého kusu a graf histórie. Overené sety sa
  pamätajú v tabuľke.
- **Návrh ceny a text inzerátu** pre Aukro alebo Bazoš.
- **Skryť ceny** jedným klikom, keď niekomu ukazuješ portfólio.

**Prehľad a zoznamy**

- Filtre, ktoré sa skladajú (v skupine ALEBO, medzi skupinami A), hľadanie
  bez diakritiky, desať spôsobov zoradenia, uložené pohľady, karty alebo
  tabuľka, hromadná úprava vybraných kusov.
- Prehľad sa dá zúžiť na sériu, kategóriu alebo uložený pohľad.
- **Odkaz na pozretie** zbierky alebo zoznamu Chcem, celého alebo len
  vybraných setov, bez hesla. Pri vypnutých sumách server ceny vôbec
  neposiela, nedajú sa nájsť ani v zdrojovom kóde stránky.

**Ostatné**

- Viac účtov na jednej inštancii, každý so svojou zbierkou a kľúčmi.
  Registráciu otvára a zatvára správca v appke.
- Rozhranie po slovensky aj po anglicky, svetlý a tmavý režim, telefón aj
  počítač. Nastavenia zobrazenia sa pamätajú pri účte.
- Prehľad spotreby volaní cudzích služieb a prepínače, čo sa z ktorej
  služby smie sťahovať.

## Rýchly štart cez Docker

```bash
cp .env.example .env
```

Do `.env` doplň aspoň `JWT_SECRET` (náhodný reťazec, aspoň 32 znakov). Potom:

```bash
docker compose up --build -d
```

Otvor `http://localhost:8000`. Prvý založený účet sa stane správcom. Schéma
databázy sa pri štarte sama posunie na najnovšiu verziu.

Databáza je jeden súbor `data/lego.db`, fotky sú v `data/photos/`. Záloha je
kópia priečinka `data/`:

```bash
cp -r data "zaloha-$(date +%F)"
```

Za HTTPS nastav v `.env` `COOKIE_SECURE=true`. Kamera na skenovanie ide len
cez HTTPS alebo na `localhost`.

## Kľúče k službám

Appka funguje aj bez kľúčov; vtedy je to evidencia, kde si názov setu a cenu
vyplníš sám. Každá služba pridá niečo navyše.

Kľúče nie sú v `.env`. **Každý používateľ si svoje vloží v appke**,
v Nastaveniach na karte Dáta. Ukladajú sa zašifrované pri jeho účte a von
sa už nedostanú, rozhranie ukáže len ich koncovku. Šifra je odvodená
z `JWT_SECRET`; po jeho zmene treba kľúče zadať znova. Každý kľúč má vlastnú
dennú kvótu, nikto ju nemíňa niekomu inému.

| Služba | Na čo je | Cena a limit | Kľúč |
|---|---|---|---|
| [Rebrickable](https://rebrickable.com/api/) | názvy, roky, dieliky, fotky, série, figúrky | zdarma, ~1 volanie/s | nastavenia účtu na rebrickable.com |
| [Brickset](https://brickset.com/article/52664/api-version-3-documentation) | pôvodná cena, čiarové kódy, popis, štítky, vlny sérií, ďalšie fotky setu | zdarma, 100 volaní/deň | [žiadosť o kľúč](https://brickset.com/tools/webservices/requestkey) |
| [BrickEconomy](https://www.brickeconomy.com/api-reference) | trhová cena nového a použitého kusu, história, odhady | súčasť Premium, 100 volaní/deň | profil na brickeconomy.com |
| [UPCitemdb](https://www.upcitemdb.com/) | záložné hľadanie podľa čiarového kódu | zdarma, bez kľúča, ~100 dotazov/deň na server | netreba |
| [Eurostat](https://ec.europa.eu/eurostat/) | inflácia pre prepočet do dnešných peňazí | zdarma, bez kľúča | netreba |

### Ako sa šetria volania

Nič sa nedeje samo od seba, nie je tu plánovač. Obnovu cien spúšťa tlačidlo
v hornej lište a beží na pozadí. Denná kvóta BrickEconomy je 100 volaní,
preto:

1. Hromadná obnova neťahá ceny mladšie než týždeň (`PRICE_MAX_AGE_HOURS`).
2. Na jedno spustenie najviac 40 položiek (`PRICE_REFRESH_BUDGET`), od
   najstaršej; zvyšok pri ďalšom.
3. Platí zvyšok dennej kvóty, po odpovedi 429 sa dávka zastaví.
4. Jedno volanie na set: odpoveď nesie cenu nového aj použitého kusu
   a históriu, takže nový aj postavený kus sa obnovia spolu.
5. Overiť cenu nepýta cenu, ktorá je mladšia než 24 hodín.

História cien príde v tej istej odpovedi, graf a „Kto sa hýbe“ teda majú čo
ukazovať hneď po pridaní setu. Brickset a Rebrickable majú v Nastaveniach
vlastné prepínače a rezervu, aby dopĺňanie na pozadí nezjedlo limit
potrebný na pridávanie.

## Vývoj

Potrebuješ Python 3.13 (cez [uv](https://docs.astral.sh/uv/)) a Node 22.

```bash
cd backend && uv run uvicorn lego_api.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Frontend beží na `http://localhost:5173` a volania na `/api` posiela na
backend. Po zmene API sa typy pre frontend generujú z OpenAPI schémy:

```bash
cd backend && uv run python -m lego_api.openapi_export
```

```bash
cd frontend && npm run gen:api
```

Testy a kontroly:

```bash
cd backend && uv run pytest && uv run ruff check src tests
```

```bash
cd frontend && npm run type-check && npm run lint && npm test
```

Testy poskytovateľov bežia proti uloženým odpovediam, bez siete a bez kľúčov.
Podrobný popis návrhu, dát, API a rozhodnutí je v
[docs/superpowers/specs/2026-09-10-lego-collection-design.md](docs/superpowers/specs/2026-09-10-lego-collection-design.md).

```
backend/     FastAPI, SQLAlchemy 2, SQLite, migrácie Alembic
frontend/    Vue 3, Vuetify 4, TypeScript, Pinia, vue-i18n, Chart.js
data/        databáza a fotky, pripojené ako zväzok do kontajnera
docs/        návrh a snímky obrazovky
```

## Zdroje dát a poďakovanie

Moje kocky je nezávislý projekt fanúšika. Nie je spojený so skupinou LEGO
Group ani s nižšie uvedenými službami a nie je nimi sponzorovaný ani schválený.

LEGO® je ochranná známka skupiny spoločností LEGO Group, ktorá tento projekt
nesponzoruje, neautorizuje ani neschvaľuje. *(LEGO® is a trademark of the LEGO
Group of companies which does not sponsor, authorize or endorse this site.)*
Obrázky setov a minifigúrok sú chránené autorským právom LEGO Group
a zobrazujú sa len na nekomerčné informačné účely v súlade s pravidlami
[LEGO Fair Play](https://www.lego.com/en-us/legal/notices-and-policies/fair-play).

- **Katalóg setov, minifigúrok a obrázky:** [Rebrickable](https://rebrickable.com),
  cez [Rebrickable API](https://rebrickable.com/api/).
- **Pôvodné ceny, čiarové kódy, popisy, série, vlny a ďalšie fotky setov:**
  [Brickset](https://brickset.com), cez Brickset API v3. Image(s) courtesy of Brickset.com.
- **Trhové ceny a odhady hodnoty:** [BrickEconomy](https://www.brickeconomy.com),
  len pre používateľov s vlastným kľúčom BrickEconomy Premium. Ceny sú odhady
  BrickEconomy, nie investičné poradenstvo.
- **Vyhľadanie podľa čiarového kódu (záložné):** [UPCitemdb](https://www.upcitemdb.com).
- **Inflácia (HICP Slovensko):** Zdroj: Eurostat, dátový súbor
  [prc_hicp_minr](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table).
  Appka z indexu počíta prepočet cien do dnešných peňazí; je to úprava dát,
  za ktorú Eurostat nezodpovedá
  ([podmienky opätovného použitia](https://ec.europa.eu/eurostat/help/copyright-notice)).

Kľúče k službám patria jednotlivým používateľom a ich použitie sa riadi
podmienkami danej služby.

### Softvér tretích strán

Backend: [FastAPI](https://fastapi.tiangolo.com), [SQLAlchemy](https://www.sqlalchemy.org),
[Alembic](https://alembic.sqlalchemy.org), [Pydantic](https://docs.pydantic.dev),
[Uvicorn](https://www.uvicorn.org), [HTTPX](https://www.python-httpx.org),
[argon2-cffi](https://argon2-cffi.readthedocs.io), [PyJWT](https://pyjwt.readthedocs.io),
[cryptography](https://cryptography.io), [openpyxl](https://openpyxl.readthedocs.io)
a ďalšie (MIT, BSD, Apache-2.0).

Frontend: [Vue](https://vuejs.org), [Vuetify](https://vuetifyjs.com),
[Pinia](https://pinia.vuejs.org), [Vue Router](https://router.vuejs.org),
[vue-i18n](https://vue-i18n.intlify.dev), [VueUse](https://vueuse.org),
[Chart.js](https://www.chartjs.org) s [vue-chartjs](https://vue-chartjs.org)
a chartjs-plugin-zoom, [openapi-fetch](https://openapi-ts.dev) (MIT);
čítanie kódov [ZXing-C++](https://github.com/zxing-cpp/zxing-cpp) cez
[zxing-wasm](https://github.com/Sec-ant/zxing-wasm) (Apache-2.0, MIT, BSD-3-Clause);
ikony [Material Design Icons](https://pictogrammers.com/library/mdi/) (Apache-2.0);
písmo [Roboto](https://github.com/googlefonts/roboto-classic) (SIL Open Font License 1.1).

Žiadna závislosť nie je pod GPL, AGPL ani LGPL.

## Licencia

Zdrojový kód je pod licenciou [MIT](LICENSE). Licencia sa nevzťahuje na dáta,
ceny a obrázky zo služieb tretích strán ani na ochrannú známku LEGO® a obrázky
výrobkov LEGO; tie patria svojim vlastníkom.

## Právne poznámky pre prevádzku

Nie je to právna rada, len to, ako appka rieši podmienky služieb (k septembru
2026). Podrobne v [specu](docs/superpowers/specs/2026-09-28-licencne-cista-architektura-design.md).

**Kým účet nezadá vlastný kľúč, zo služby nevidí nič.**

- **Rebrickable** (katalóg a fotky): API dovoľuje akékoľvek použitie.
  Spoločný katalóg vidí každý účet s vlastným kľúčom Rebrickable, bez neho
  len čísla setov.
- **Brickset a BrickEconomy** (osobné licencie): údaj sa ukladá raz, ale
  účet ho vidí, len keď si ho jeho vlastný kľúč sám stiahol. Ceny
  BrickEconomy len do času jeho posledného volania. Verejné odkazy z týchto
  služieb neukazujú nič.
- **UPCitemdb a Eurostat** nemajú kľúč: sú predvolene vypnuté, účet ich
  zapne sám v Nastaveniach → Dáta. Zdroj Eurostatu je uvedený vyššie.
- **Obrázky setov** idú cez server appky, takže tieto služby nevidia IP
  adresy návštevníkov.
- **GDPR:** stránka Zásady ochrany súkromia (prevádzkovateľa vyplní
  správca v Nastaveniach → Aplikácia), potvrdenie pri registrácii, export
  všetkých údajov a zmazanie účtu v Nastaveniach → Účet. Fotky sa ukladajú
  zmenšené a bez polohy GPS. Appka používa len nevyhnutné cookie na
  prihlásenie, bez analytiky a reklamy, takže lišta so súhlasom netreba.

Čo zostáva na prevádzkovateľovi:

- **Nekomerčne.** Bez reklám, predplatného a affiliate odkazov. Pravidlá
  LEGO Fair Play aj licencia BrickEconomy platia len pre osobné, nekomerčné
  použitie.
- **Brickset** dáva kľúč „na testovanie a vzdelávanie“. Pri otvorenej
  verejnej inštancii mu napíš o súhlas.
- **BrickEconomy:** údaje sa na serveri ukladajú raz pre všetky kľúče ako
  vyrovnávacia pamäť (nikomu bez vlastného kľúča sa neukážu). Kto chce mať
  úplnú istotu, nech si vyžiada ich súhlas.
- **Slovo LEGO nepatrí do domény** ani do názvu verejnej stránky, logo LEGO
  sa nepoužíva.
- **HTTPS** a vyplnený prevádzkovateľ, keď sa registrujú cudzí ľudia.
