# Mena zobrazenia, diely setu a alternatívne stavby (verzia 1.1.0)

Schválené používateľom 1. 10. 2026. Synchronizácia s účtom Rebrickable
a „Postavíš z toho, čo máš?“ sa nerobia.

## 1. Mena zobrazenia

**Čo vidí používateľ**

- Nastavenia → Zobrazenie: výber „Mena zobrazenia“. Na výber sú EUR
  (predvolené), CZK, USD, GBP, PLN, HUF a CHF.
- Pod výberom je riadok s kurzom, napríklad „1 € = 24,32 Kč · ECB, 30. 9. 2026“.
- Všetky sumy v appke sú v tejto mene: karty, detail, súčty, Prehľad, grafy,
  Chcem, Overiť cenu, Súpis a verejný odkaz.
- Pri inej mene než EUR sa pri prvom zobrazení ukáže krátka poznámka,
  že ide o prepočet kurzom ECB.
- Voľba „Kúpu a predaj zadávať aj v inej mene“ (predvolene vypnutá): pri
  cene vo formulári kusu a v dialógu predaja pribudne výber meny.

**Pravidlá**

- Ukladá sa ďalej v eurách. Mena je len zobrazenie a prepočíta sa na
  jednom mieste: `utils/format.ts` (`money`, `exactMoney`). Platí tam aj
  `pricesHidden` (Skryť ceny).
  - Zobrazenie ide dnešným kurzom, aj pri histórii a grafe. Zisk v percentách
    sa tak nemení, len sumy.
  - Grafy majú závislosť na mene, ako dnes na `pricesHidden`.
- Kúpa alebo predaj v cudzej mene:
  - `collection_items` dostane `purchase_currency`
    a `purchase_price_original`, rovnako `sale_currency`
    a `sale_price_original`.
  - Suma v eurách sa vypočíta kurzom ECB zo dňa kúpy (predaja), bez dátumu
    kurzom z dnešného dňa. Uloží sa do existujúceho `purchase_price_eur`
    (`sale_price_eur`).
  - Pôvodná suma ostane viditeľná pri kuse („1 290 Kč, kurzom 24,95 z 12. 3. 2024“).
- V dnešných peniazoch (inflácia Slovenska) sa počíta ďalej v eurách, výsledok
  sa iba prepočíta na menu zobrazenia.
- Export CSV ostáva v eurách; hlavička stĺpca to povie. Import, šablóna
  a export dostanú stĺpce `mena_kupy` a `kupna_cena_v_mene`, ostatné stĺpce
  sa nemenia. Pravidlo: stĺpce všetkých troch sú tie isté.
- Verejný odkaz ukazuje menu majiteľa. Server pošle kurz a kód meny,
  pri vypnutých sumách nič.

**Kurzy**

- Zdroj je ECB priamo, bez služby tretej strany: `eurofxref-hist.zip` raz,
  potom `eurofxref-daily.xml`.
- Tabuľka `exchange_rates (currency, day, rate)`. Obnova raz denne, a len keď
  je kurz potrebný: niekto má inú menu zobrazenia alebo zadáva cudziu menu.
- Po chybe hodinu pokoj, starý kurz ostáva, rovnako ako pri `services/inflation.py`.
- Na deň bez kurzu (víkend, sviatok) sa použije posledný kurz pred ním.
- Volanie má schopnosť `ecb.rates` v `capabilities.py`, ide cez bránu
  a zapisuje sa do `api_calls`. Texty sú v locales.
- Zásady súkromia: riadok, že sa sťahujú len kurzy z ECB a nič o používateľovi
  neodchádza. Zvýšiť `privacy_version`.
- Preferencia je v `preferences.display.currency` (`mergeDisplay`).

## 2. Diely setu a alternatívne stavby (Rebrickable)

**Čo vidí používateľ (detail setu, len sety, nie figúrky zo sérií)**

- **Karta „Diely · N“.**
  - Zoznam dielikov zoskupený podľa farby: obrázok, číslo, názov, farba
    a počet. Náhradné diely sú zvlášť.
  - Stiahne sa až po rozbalení karty.
  - Pri každom kuse setu režim „Kontrola úplnosti“: pri dieliku sa zadá, koľko
    ho je. Ukladajú sa len odchýlky (chýbajúce počty).
  - Kus s chýbajúcimi dielikmi má štítok „chýbajú N“ v detaile aj na karte
    v Zbierke.
  - Tlačidlo „Zoznam chýbajúcich“ stiahne CSV (cez klienta a blob, s BOM).
- **Karta „Čo ešte z neho postavíš · N“.**
  - Alternatívne stavby (MOC) z dielikov setu: obrázok, názov, autor, počet
    dielikov a odkaz na stránku stavby na Rebrickable.
  - Stiahne sa až po rozbalení karty.
- Bez kľúča Rebrickable sa karty neukážu (`auth.can(...)`), rovnako ako
  ostatné údaje z Rebrickable.

**Dáta a volania**

- Rebrickable `GET /lego/sets/{num}/parts/?page_size=1000` (aj ďalšie
  stránky) a `GET /lego/sets/{num}/alternates/`.
  - Schopnosti `rebrickable.parts` a `rebrickable.alternates`, cez bránu,
    zapisujú sa do `api_calls`.
  - Rebrickable nemá dennú kvótu, len obmedzenie rýchlosti; volá sa raz na set.
- Spoločná vyrovnávacia pamäť katalógu (podmienky Rebrickable to dovoľujú):
  - tabuľky `set_parts` a `set_alternates` s `fetched_at`;
  - obnova najskôr po 90 dňoch;
  - prázdny výsledok sa pamätá tiež, aby sa nepýtal znova.
- Viditeľnosť: ako ostatné údaje z Rebrickable, len s vlastným kľúčom
  (`visibility.py`).
- Obrázky dielikov a stavieb idú cez `GET /img` (cdn.rebrickable.com je
  povolený).
- Kontrola úplnosti je údaj účtu: tabuľka `item_part_checks` (`item_id`,
  `part_num`, `color_id`, `is_spare`, `missing`).
  - Pridať do `_OWNED` v `services/account.py` a do exportu účtu.
  - Maže sa so zmazaným kusom.

## Overenie

- Testy:
  - backend: prepočet a kurz pri víkende, uloženie kúpy v cudzej mene,
    brána, zdroje proti uloženým odpovediam cez `respx`, viditeľnosť bez
    kľúča, `item_part_checks` pri zmazaní účtu a v exporte;
  - frontend: formátovač v rôznych menách, karta dielov (načítavanie,
    prázdne, chyba).
- Migrácie sa píšu ručne (nie autogenerate) a idú za sebou za 9332cb64e9a6.
- CLAUDE.md dostane pravidlá „Mena je len zobrazenie“ a „Diely a stavby
  z Rebrickable raz na set“.
