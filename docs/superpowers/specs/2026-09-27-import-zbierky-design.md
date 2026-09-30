# Hromadný import zbierky z CSV a Excelu

Stav: implementované 2026-09-27 (`services/import_file.py`, `services/importer.py`,
`services/import_template.py`, `routers/imports.py`, `components/ImportPanel.vue`).

## Prečo

Zbierka otca a známych existuje v tabuľkách. Pridávať stovky setov po
jednom cez „Pridať set“ je hodiny práce. Import má z tabuľky urobiť zbierku
na jeden krok. Musí sa pritom dať vopred skontrolovať, čo vznikne, a omyl
vrátiť.

## Kde to je

V Nastaveniach je záložka **Import a export**. Presunula sa na ňu karta
exportu zo záložky Dáta. Na hlavných obrazovkách nie je nič nové, import
je občasná vec. Tlačidlo Export CSV zostáva aj v Zbierke.

## Súbor

Import prijme `.csv` aj `.xlsx`, najviac 5 MB a 5000 riadkov. Pri Exceli
sa číta prvý hárok a hlavička je prvý neprázdny riadok.

Pri CSV sa kódovanie a oddeľovač zisťujú samy:

- Kódovanie: UTF-8 s BOM, potom bez neho a nakoniec Windows-1250. Slovenský
  Excel pri „Uložiť ako CSV“ ukladá práve vo Windows-1250.
- Oddeľovač: `;`, `,` alebo tabulátor, podľa toho, ktorý rozdelí hlavičku
  na najviac stĺpcov.

### Stĺpce

Povinný je len `cislo_setu`, ostatné stĺpce môžu chýbať. Stĺpce navyše
import ignoruje. Mená stĺpcov sú rovnaké ako v exporte, takže vyexportovaný
súbor sa dá upraviť v Exceli a nahrať späť.

Hlavičky sa porovnávajú bez diakritiky a bez ohľadu na veľké písmená.
Medzera, bodka aj pomlčka sa berú ako `_`. Každý stĺpec má aj synonymá,
napríklad „Číslo“, „set“ či „množstvo“ (úplný zoznam je v `services/importer.py`).

| stĺpec | význam | príklad |
|---|---|---|
| `cislo_setu` | katalógové číslo | 10294, 10294-1, 71046-3 |
| `pocet` | koľko kusov vznikne, predvolene 1 | 2 |
| `vlastnictvo` | vlastnené / predané / chcem, predvolene vlastnené | predané |
| `stav` | nové v krabici / rozbalené / postavené / rozobrané | postavené |
| `zoznam` | investícia / na predaj / vystavené / na stavanie | investícia |
| `umiestnenie` | voľný text | Obývačka |
| `priznaky` | krabica, manuál, stojan, kompletný, poškodená krabica, chýbajú dieliky | krabica, manuál |
| `kupna_cena_eur` | cena za kus | 39,99 |
| `datum_kupy` | d.m.rrrr alebo rrrr-mm-dd | 12.3.2019 |
| `kde_kupene` | voľný text | Alza |
| `predajna_cena_eur` | len pri predaných | 120 |
| `datum_predaja` | len pri predaných | 1.2.2024 |
| `kanal_predaja` | len pri predaných | Bazoš |
| `poplatky_eur`, `postovne_eur` | len pri predaných, platil predávajúci | 3,50 |
| `cielova_cena_eur` | len pri Chcem | 80 |
| `poznamka` | voľný text | |

Hodnoty sa čítajú zhovievavo:

- Pri stave, zozname, vlastníctve a príznakoch prejdú slovenské názvy
  z rozhrania, anglické kódy z exportu (`new_sealed`, `owned`) aj názvy bez
  diakritiky.
- Pri sumách prejde `39,99`, `39.99`, `1 234,50`, `1.234,50` aj `39,99 €`.
  Keď sú v čísle čiarka aj bodka, desatinná je tá posledná.
- Pri dátumoch prejde `12.3.2019`, `12. 3. 2019`, `2019-03-12`,
  `12/3/2019` aj dátumová bunka z Excelu.

### Šablóna

Šablóna sa sťahuje v Exceli aj v CSV. Obsahuje hlavičku a tri sivé
vzorové riadky: vlastnený, predaný a želaný. Majú poznámku „príklad, zmaž
tento riadok“; keby ostali v súbore, import ich ukáže ako chybu a preskočí.

Excelová šablóna má navyše:

- výberové zoznamy (overenie údajov) pri stave, vlastníctve a zozname;
- formát súm a dátumov na prvých 1000 riadkoch;
- druhý hárok „Návod“ s popisom stĺpcov.

## Priebeh

1. **Nahratie.** `POST /imports` súbor prečíta a vytvorí koncept
   (`import_batches`, `state=ready` alebo `looking_up`). Každý riadok sa uloží už rozobraný.
   Zatiaľ nevznikol žiadny kus.
2. **Dohľadanie.** Čísla, ktoré katalóg nepozná, sa dohľadajú cez
   Rebrickable na pozadí (`state=looking_up`), sekundu od seba, lebo
   Rebrickable znesie zhruba jedno volanie za sekundu. Rozhranie sa každé
   dve sekundy pýta `GET /imports/{id}` a ukazuje priebeh
   „Dohľadávam sety 12 / 40“.

   Katalóg sa pri tom volá s vypnutým Brickset. Bežné `resolve` pri novom
   sete pýta aj Brickset `getSets`, čo by 300 novými setmi minulo jeho
   denný limit na tri dni. Keď dohľadanie ostane stáť (napríklad reštart
   servera), `GET /imports/{id}` ho rozbehne znova.
3. **Náhľad.** Každý riadok má stav:
   - `ok`: pripravený na import;
   - `duplicate`: v zbierke už je. Pri vlastnenom to znamená rovnaký set
     s rovnakým dátumom a cenou, pri predanom rovnaký dátum a cena predaja,
     pri Chcem už je v Chcem. Predvolene sa preskočí, dá sa zaškrtnúť
     „importovať aj tak“. Pri Chcem to nejde, set je tam najviac raz;
   - `error`: riadok sa preskočí. Príčina je vždy po slovensky pri riadku:
     neznáme číslo, zlý dátum, záporná cena, chýba predajná cena
     predaného kusu.

   Popri stave môže mať riadok aj upozornenia, ktoré ho neblokujú:
   - holé číslo zberateľskej série sa importuje ako nerozbalený sáčok;
   - set je v Chcem a importom sa odtiaľ vyradí; položka Chcem
     z predošlého importu ostane (`keep_imported`) a upozornenie to povie;
   - želaný set už v zbierke je.
4. **Potvrdenie.** `POST /imports/{id}/commit` s čiarovými číslami
   duplicít, ktoré sa majú importovať aj tak. Všetko prebehne v jednej
   transakcii. Vlastnené a predané riadky vytvoria `pocet` kusov
   s `import_batch_id`, Chcem vytvorí položku v Chcem. Kúpený set sa vyradí
   z Chcem, rovnako ako pri ručnom „Kúpil som“. Vyradené položky Chcem sa
   uložia do konceptu, aby ich vrátenie vedelo obnoviť.
5. **Vrátenie.** `POST /imports/{id}/undo` zmaže kusy a položky Chcem
   z tohto importu vrátane fotiek na disku a obnoví vyradené položky Chcem.
   Ručne pridané veci ostanú nedotknuté. Rozhranie sa pred vrátením pýta
   a ukáže, koľko kusov zmizne.

História posledných importov je v tej istej záložke: dátum, súbor, počty
a tlačidlo Vrátiť. Nepotvrdený koncept sa zmaže po 24 hodinách.

## Koľko to stojí volaní

| služba | koľko | kvóta |
|---|---|---|
| Rebrickable | jedno volanie na set, ktorý ešte nie je v katalógu | bez dennej kvóty, ~1/s |
| BrickEconomy | nič | ceny sa nepýtajú, inak by 300 setov minulo kvótu na tri dni |
| Brickset | nič hneď | popis a štítky doplní existujúce dopĺňanie po 40 setoch |

Nové sety dostanú cenu až cez tlačidlo obnovy v hornej lište. Bez kľúča
Rebrickable sa neznáme čísla nedohľadajú a ich riadky majú chybu
s odkazom do Nastavení.

Volania sa zapisujú do histórie volaní s účelom `import`.

## Čo import nerobí

- **Neupravuje existujúce kusy.** Každý riadok iba pridáva. Úprava podľa
  tabuľky by potrebovala kľúč kusu, ktorý v Exceli nikto neudrží.
- **Nepriraďuje fotky.**
- **Nepriraďuje figúrky zo série.** Holé číslo série nevie povedať, ktorá
  figúrka to je. Vznikne nerozbalený sáčok, figúrka sa doplní v detaile
  po rozbalení.
- **Nepozná kategórie ani ručnú trhovú cenu.** Kategórie visia na sete
  a počítajú sa samy z pravidiel.

## Dátový model

- `import_batches`: `id`, `user_id`, `filename`, `state`
  (looking_up / ready / committed / undone), `ignored_columns`, `rows` (JSON riadkov
  po rozobratí aj so stavom), `progress_done`, `progress_total`,
  `removed_wishes` (JSON), `pieces_created`, `wishes_created`,
  `created_at`, `committed_at`, `undone_at`.
- Chyby a upozornenia zo súboru sú v riadku (`errors`, `warnings`), výsledok
  porovnania so zbierkou zvlášť (`check_errors`, `check_warnings`). Tie
  druhé sa pri potvrdení počítajú znova, lebo zbierka sa medzitým mohla
  zmeniť.
- `collection_items.import_batch_id` a `wishlist_items.import_batch_id`,
  nullable, pri zmazaní importu `SET NULL`.

## Testy

- Čítanie CSV v UTF-8 s BOM aj vo Windows-1250, oddeľovač `;` aj `,`,
  a `.xlsx` vytvorené cez openpyxl.
- Hlavičky so synonymami a diakritikou, všetky formáty súm a dátumov.
- Stavy riadkov: duplicita vlastneného, predaného aj Chcem, chyby,
  holé číslo série.
- Potvrdenie vytvorí správny počet kusov, predaných aj Chcem a vyradí
  kúpené z Chcem. Vrátenie ich zmaže a Chcem obnoví.
- Opätovné nahratie exportu označí všetko ako duplicitu.
- Dohľadanie neznámeho čísla cez Rebrickable beží proti `respx`, bez siete.
