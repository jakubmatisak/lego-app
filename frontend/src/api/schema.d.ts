/* Vygenerované z OpenAPI. Needituj ručne, spusti `npm run gen:api`. */
export interface paths {
    "/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register */
        post: operations["register_api_v1_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Refresh */
        post: operations["refresh_api_v1_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        /**
         * Delete Me
         * @description Zmaže účet so všetkými údajmi a fotkami (GDPR, čl. 17). Potvrdzuje sa heslom.
         *
         *     Posledný správca sa zmazať nedá, inštancia by ostala bez správcu.
         */
        delete: operations["delete_me_api_v1_auth_me_delete"];
        options?: never;
        head?: never;
        /** Update Me */
        patch: operations["update_me_api_v1_auth_me_patch"];
        trace?: never;
    };
    "/auth/me/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get My Sources
         * @description Služby, čo odomknú a ktoré ich volania má účet zapnuté.
         */
        get: operations["get_my_sources_api_v1_auth_me_sources_get"];
        /**
         * Set My Sources
         * @description Uloží pravidlá sťahovania. Vynechané pole sa nemení.
         */
        put: operations["set_my_sources_api_v1_auth_me_sources_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me/keys": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get My Keys
         * @description Stav kľúčov. Samotné kľúče sa von nikdy nevracajú, len koncovka.
         */
        get: operations["get_my_keys_api_v1_auth_me_keys_get"];
        /**
         * Set My Keys
         * @description Uloží vlastné kľúče používateľa.
         *
         *     Vynechané pole sa nemení, prázdny reťazec kľúč zmaže. Do databázy ide
         *     kľúč zašifrovaný, von sa už nikdy nedostane.
         */
        put: operations["set_my_keys_api_v1_auth_me_keys_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me/preferences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get My Preferences */
        get: operations["get_my_preferences_api_v1_auth_me_preferences_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me/preferences/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set My Preference
         * @description Zapamätá si stav jednej obrazovky, napríklad filtre Zbierky.
         *
         *     Prázdny objekt stav zmaže, obrazovka sa potom otvorí s predvolenými
         *     hodnotami. Ukladá sa celý nový slovník, inak by SQLAlchemy zmenu
         *     vnútri JSON stĺpca nezbadal.
         */
        put: operations["set_my_preference_api_v1_auth_me_preferences__key__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me/privacy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Privacy
         * @description Používateľ si prečítal aktuálnu verziu zásad (po ich zmene).
         */
        post: operations["accept_privacy_api_v1_auth_me_privacy_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export Me
         * @description Všetky moje údaje v ZIP (JSON a fotky), bez kľúčov k službám (GDPR, čl. 20).
         */
        get: operations["export_me_api_v1_auth_me_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/brickset/backfill": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Brickset Backfill
         * @description Doplní popis, štítky a hodnotenie setom zo zbierky, najviac 40 za beh.
         */
        post: operations["start_brickset_backfill_api_v1_catalog_brickset_backfill_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/{num}/brickset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Fill From Brickset
         * @description Popis, štítky a hodnotenie pre jeden set hneď, keď ho niekto otvorí.
         *
         *     Jedno volanie Brickset, a len raz: set, na ktorý sa už pýtal, sa vráti
         *     bez volania.
         */
        post: operations["fill_from_brickset_api_v1_catalog__num__brickset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/{num}/images": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Set Images
         * @description Ďalšie fotky setu z Brickset (galéria v detaile).
         *
         *     getAdditionalImages sa do denného limitu nepočíta, ale chce interné číslo
         *     Brickset. Nové sety ho majú z getSets pri pridaní; set spred tejto
         *     funkcie sa naň raz opýta (jedno getSets, ako pri otvorení detailu).
         *     Galéria sa stiahne raz a potom sa berie z databázy. Vypnutý prepínač
         *     ``brickset.images`` = žiadna galéria a žiadne volanie.
         */
        get: operations["get_set_images_api_v1_catalog__num__images_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/by-ean/{code}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get By Ean
         * @description Set podľa čiarového kódu z krabice. Cenovú kvótu nemíňa.
         *
         *     Kód, ktorý sa nedávno nenašiel, sa nehľadá znova, kým ``retry`` nepovie.
         */
        get: operations["get_by_ean_api_v1_catalog_by_ean__code__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/{num}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Catalog Item */
        get: operations["get_catalog_item_api_v1_catalog__num__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/{num}/children": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Children */
        get: operations["get_children_api_v1_catalog__num__children_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/{num}/ownership": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Ownership */
        get: operations["get_ownership_api_v1_catalog__num__ownership_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/{num}/ean": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Assign Ean
         * @description Priradí setu kód, ktorý databáza kódov nepoznala.
         *
         *     Používateľ naskenoval neznámy kód a set potom zadal číslom. Kód sa
         *     zapamätá v spoločnom katalógu, takže ďalší sken toho istého setu
         *     (aj u iného účtu) ho nájde doma, bez dotazu von.
         */
        put: operations["assign_ean_api_v1_catalog__num__ean_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog/{num}/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Refresh Catalog Item */
        post: operations["refresh_catalog_item_api_v1_catalog__num__refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Manual Item
         * @description Ručné zadanie setu, ktorý nie je v žiadnom katalógu.
         *
         *     Holé číslo dostane variant ``-1`` ako v Rebrickable. Po pripojení kľúča
         *     sa tak ten istý set nájde pod tým istým číslom a nevznikne druhý raz.
         */
        post: operations["create_manual_item_api_v1_catalog_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Items */
        get: operations["list_items_api_v1_items_get"];
        put?: never;
        /**
         * Create Items
         * @description Pridá kusy; set, ktorý bol v Chcem, odtiaľ v tej istej transakcii vyradí.
         */
        post: operations["create_items_api_v1_items_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items/grouped": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Grouped */
        get: operations["list_grouped_api_v1_items_grouped_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items/facets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Item Facets
         * @description Počty pre panel filtrov. Každá skupina sa ráta bez vlastného výberu.
         */
        get: operations["item_facets_api_v1_items_facets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Locations */
        get: operations["list_locations_api_v1_locations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/suggestions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Suggestions
         * @description Už použité hodnoty pre našepkávače: kde uložené, kde kúpené, kanál predaja.
         */
        get: operations["list_suggestions_api_v1_suggestions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items/bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Series Items
         * @description Naraz pridá vybraných členov zberateľskej série, aj s cenou za celú sériu.
         *
         *     Figúrky, ktoré boli v Chcem, odtiaľ vyradí, rovnako ako `POST /items`.
         */
        post: operations["create_series_items_api_v1_items_bulk_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Item */
        get: operations["get_item_api_v1_items__item_id__get"];
        put?: never;
        post?: never;
        /** Delete Item */
        delete: operations["delete_item_api_v1_items__item_id__delete"];
        options?: never;
        head?: never;
        /** Update Item */
        patch: operations["update_item_api_v1_items__item_id__patch"];
        trace?: never;
    };
    "/items/bulk-update": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Bulk Update
         * @description Zmení naraz viac vlastnených kusov.
         *
         *     Výber je zoznam kusov, čísla setov (karta setu, pri sérii aj jej
         *     členovia) alebo, keď nie je ani jedno, celý výsledok filtra z adresy.
         *     Vždy len kusy, ktoré ten filter ukazuje: Zbierka posiela `sets_only`,
         *     detail série `series` bez neho.
         *     Predané kusy a kusy iného účtu sa nemenia nikdy.
         */
        post: operations["bulk_update_api_v1_items_bulk_update_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items/{item_id}/identify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Identify Item
         * @description Rozbalený sáčok série sa zmení na konkrétnu figúrku.
         */
        patch: operations["identify_item_api_v1_items__item_id__identify_patch"];
        trace?: never;
    };
    "/items/{item_id}/sell": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sell Item */
        post: operations["sell_item_api_v1_items__item_id__sell_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items/{item_id}/unsell": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Unsell Item
         * @description Oprava omylu: kus sa vráti medzi vlastnené.
         */
        post: operations["unsell_item_api_v1_items__item_id__unsell_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/items/{item_id}/photos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Photos */
        get: operations["list_photos_api_v1_items__item_id__photos_get"];
        put?: never;
        /** Upload Photo */
        post: operations["upload_photo_api_v1_items__item_id__photos_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/photos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List All Photos
         * @description Všetky fotky používateľa naraz, pre súpis pre poistku.
         */
        get: operations["list_all_photos_api_v1_photos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/photos/{photo_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Photo */
        get: operations["get_photo_api_v1_photos__photo_id__get"];
        put?: never;
        post?: never;
        /** Delete Photo */
        delete: operations["delete_photo_api_v1_photos__photo_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/categories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Categories */
        get: operations["list_categories_api_v1_categories_get"];
        put?: never;
        /** Create Category */
        post: operations["create_category_api_v1_categories_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/categories/{category_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Category */
        delete: operations["delete_category_api_v1_categories__category_id__delete"];
        options?: never;
        head?: never;
        /** Update Category */
        patch: operations["update_category_api_v1_categories__category_id__patch"];
        trace?: never;
    };
    "/catalog/{num}/categories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Catalog Categories
         * @description Všetky kategórie z pohľadu jedného setu: je v nej a prečo.
         */
        get: operations["catalog_categories_api_v1_catalog__num__categories_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/categories/{category_id}/members/{num}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Member
         * @description Zaradí set do kategórie alebo ho vyradí, aj proti pravidlu.
         */
        put: operations["set_member_api_v1_categories__category_id__members__num__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/views": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Views */
        get: operations["list_views_api_v1_views_get"];
        put?: never;
        /** Create View */
        post: operations["create_view_api_v1_views_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/views/{view_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete View */
        delete: operations["delete_view_api_v1_views__view_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/refresh-status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Refresh Status */
        get: operations["refresh_status_api_v1_prices_refresh_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/refresh-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh All
         * @description Obnoví ceny na pozadí.
         *
         *     Bez ``num`` celá zbierka, a len ceny staršie než týždeň. S ``num`` je
         *     to ručná obnova jednej položky z detailu, pri sérii jej figúrok, a tá
         *     vek snímky nepozerá: používateľ chce cenu teraz. Jedno volanie na
         *     položku a zvyšok kvóty platia v oboch prípadoch.
         */
        post: operations["refresh_all_api_v1_prices_refresh_all_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/checks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Checks
         * @description Naposledy overené sety (Overiť cenu), najnovšie prvé, s uloženou cenou.
         */
        get: operations["list_checks_api_v1_prices_checks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/checks/{num}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Record Check
         * @description Zapíše overenie; opakované overenie set len posunie navrch.
         */
        post: operations["record_check_api_v1_prices_checks__num__post"];
        /** Forget Check */
        delete: operations["forget_check_api_v1_prices_checks__num__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/lookup/{num}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Lookup Price
         * @description Overiť cenu jedným tlačidlom: čo to je a koľko to stojí.
         *
         *     Set sa hľadá v katalógu, potom cez Rebrickable. Keď ho nepozná nikto
         *     a BrickEconomy je pripojené, poslúži jeho odpoveď o cene aj ako
         *     metadáta (názov, séria, rok, dieliky): jedno volanie dá obe. Čerstvá
         *     cena (``CHECK_FRESH_HOURS``) sa neťahá znova. Nájdený set sa zapíše
         *     medzi naposledy overené.
         */
        post: operations["lookup_price_api_v1_prices_lookup__num__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/{num}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Prices */
        get: operations["get_prices_api_v1_prices__num__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/{num}/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh One
         * @description Okamžité volanie poskytovateľa pre jednu položku.
         *
         *     Jedno volanie prinesie nový aj použitý stav a k tomu históriu, takže sa
         *     uložia obidva stavy bez ohľadu na to, ktorý si používateľ práve pozerá.
         *
         *     ``max_age_hours`` (Overiť cenu): keď je cena mladšia, volanie sa ušetrí
         *     a vráti sa uložená; ``fetched`` v odpovedi povie, čo sa stalo.
         */
        post: operations["refresh_one_api_v1_prices__num__refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prices/{num}/manual": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Manual Price
         * @description Ručná cena je plnohodnotná snímka, takže ju graf aj portfólio vidia.
         */
        put: operations["set_manual_price_api_v1_prices__num__manual_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/stats/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Summary
         * @description Rozsah = rovnaké filtre ako GET /items. Parameter status sa ignoruje: rozsah vyberá sety a predané kusy v ňom ostávajú (realizovaný zisk).
         */
        get: operations["get_summary_api_v1_stats_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/stats/breakdown": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Breakdown
         * @description Rozsah = rovnaké filtre ako GET /items. Parameter status sa ignoruje: rozsah vyberá sety a predané kusy v ňom ostávajú (realizovaný zisk).
         */
        get: operations["get_breakdown_api_v1_stats_breakdown_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/stats/sales": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Sales
         * @description Rozsah = rovnaké filtre ako GET /items. Parameter status sa ignoruje: rozsah vyberá sety a predané kusy v ňom ostávajú (realizovaný zisk).
         */
        get: operations["get_sales_api_v1_stats_sales_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/stats/timeline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Timeline
         * @description Rozsah = rovnaké filtre ako GET /items. Parameter status sa ignoruje: rozsah vyberá sety a predané kusy v ňom ostávajú (realizovaný zisk).
         */
        get: operations["get_timeline_api_v1_stats_timeline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/stats/movers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Movers
         * @description Rozsah = rovnaké filtre ako GET /items. Parameter status sa ignoruje: rozsah vyberá sety a predané kusy v ňom ostávajú (realizovaný zisk).
         */
        get: operations["get_movers_api_v1_stats_movers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/stats/series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Series
         * @description Rozsah = rovnaké filtre ako GET /items. Parameter status sa ignoruje: rozsah vyberá sety a predané kusy v ňom ostávajú (realizovaný zisk).
         */
        get: operations["get_series_api_v1_stats_series_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/share": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Share Links */
        get: operations["list_share_links_api_v1_share_get"];
        put?: never;
        /** Create Share Link */
        post: operations["create_share_link_api_v1_share_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/share/{link_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke Share Link */
        delete: operations["revoke_share_link_api_v1_share__link_id__delete"];
        options?: never;
        head?: never;
        /** Update Share Link */
        patch: operations["update_share_link_api_v1_share__link_id__patch"];
        trace?: never;
    };
    "/public/{token}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Public Collection
         * @description Bez prihlásenia. Zrušený odkaz vracia 404.
         */
        get: operations["public_collection_api_v1_public__token__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/minifigs/series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Series
         * @description Všetky série s tým, koľko z nich mám.
         *
         *     Raz za týždeň sa pri tom na pozadí pozrie, či nevyšla nová séria. Stojí
         *     to jedno volanie Rebrickable a nová séria jedno ďalšie, cenovú kvótu nie.
         */
        get: operations["list_series_api_v1_minifigs_series_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/minifigs/series/{series_num}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Series Detail */
        get: operations["series_detail_api_v1_minifigs_series__series_num__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/minifigs/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Sync Status */
        get: operations["sync_status_api_v1_minifigs_sync_get"];
        put?: never;
        /**
         * Start Sync
         * @description Ručné stiahnutie. S ``force`` znova aj série, ktoré už máme.
         */
        post: operations["start_sync_api_v1_minifigs_sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/themes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Themes
         * @description Moje témy a všetky témy. Brickset to do limitu nepočíta.
         */
        get: operations["list_themes_api_v1_themes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/themes/years": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Theme Years */
        get: operations["theme_years_api_v1_themes_years_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/themes/wave": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Theme Wave
         * @description Sety jednej vlny. Prvýkrát jedno volanie Brickset, potom z databázy.
         */
        get: operations["theme_wave_api_v1_themes_wave_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Usage
         * @description Koľko zo dnešných limitov zostáva a posledné volania.
         *
         *     Počty sú podľa UTC dňa, podľa neho limity rátajú aj služby. Brickset
         *     vlastnú štatistiku dáva zadarmo, tá ráta aj volania mimo tejto appky.
         */
        get: operations["usage_api_v1_usage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/img": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Image */
        get: operations["image_api_v1_img_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/imports/template.xlsx": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Template Xlsx */
        get: operations["download_template_xlsx_api_v1_imports_template_xlsx_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/imports/template.csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Template Csv */
        get: operations["download_template_csv_api_v1_imports_template_csv_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/imports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Imports
         * @description Posledné importy, aj nepotvrdené koncepty z posledného dňa.
         */
        get: operations["list_imports_api_v1_imports_get"];
        put?: never;
        /**
         * Create Import
         * @description Súbor sa rozoberie na náhľad. Nič sa ešte neukladá do zbierky.
         */
        post: operations["create_import_api_v1_imports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/imports/{import_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Import
         * @description Náhľad a priebeh dohľadania. Zastavené dohľadanie sa tu rozbehne znova.
         */
        get: operations["get_import_api_v1_imports__import_id__get"];
        put?: never;
        post?: never;
        /**
         * Discard Import
         * @description Zahodí nepotvrdený koncept. Dokončený import sa vracia, nie maže.
         */
        delete: operations["discard_import_api_v1_imports__import_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/imports/{import_id}/commit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Commit Import
         * @description Vytvorí kusy a položky Chcem, všetko naraz v jednej transakcii.
         */
        post: operations["commit_import_api_v1_imports__import_id__commit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/imports/{import_id}/undo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Undo Import
         * @description Zmaže, čo import vytvoril, a vráti do Chcem, čo z neho vyradil.
         */
        post: operations["undo_import_api_v1_imports__import_id__undo_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Providers Status
         * @description Verejné: prihlasovacia stránka podľa toho skryje „Nový účet“.
         */
        get: operations["providers_status_api_v1_providers_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/wishlist": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Wishlist
         * @description Predvolene najbližšie k cieľovej cene navrch (pod cieľom najprv).
         */
        get: operations["list_wishlist_api_v1_wishlist_get"];
        put?: never;
        /**
         * Add Wishlist
         * @description Pridá set do Chcem; Späť po kúpe ho vracia aj s pôvodnými údajmi.
         *
         *     ``unless_owned``: Späť po automatickom uložení zo skenu. Set, ktorý účet
         *     ešte má (vlastnený alebo rezervovaný kus, ako pri vyraďovaní), sa nepridá
         *     a odpoveď je 204: kúpený set v Chcem nie je. Späť pri „Odstránené z Chcem“
         *     ho neposiela, tam kúpa platí a Chcem sa vráti aj tak.
         */
        post: operations["add_wishlist_api_v1_wishlist_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/wishlist/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove Wishlist */
        delete: operations["remove_wishlist_api_v1_wishlist__item_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Wishlist
         * @description Cieľová cena a poznámka; odpoveď už s trhovou cenou a vzdialenosťou od cieľa.
         */
        patch: operations["update_wishlist_api_v1_wishlist__item_id__patch"];
        trace?: never;
    };
    "/export/items.csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export Csv */
        get: operations["export_csv_api_v1_export_items_csv_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Users */
        get: operations["list_users_api_v1_admin_users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get App Settings */
        get: operations["get_app_settings_api_v1_admin_settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update App Settings
         * @description Správca otvorí alebo zavrie registráciu. Platí hneď, bez reštartu.
         */
        patch: operations["update_app_settings_api_v1_admin_settings_patch"];
        trace?: never;
    };
    "/admin/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete User
         * @description Správca zmaže cudzí účet so všetkými údajmi (napríklad na žiadosť podľa GDPR).
         */
        delete: operations["delete_user_api_v1_admin_users__user_id__delete"];
        options?: never;
        head?: never;
        /** Update User */
        patch: operations["update_user_api_v1_admin_users__user_id__patch"];
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AdminSettingsOut */
        AdminSettingsOut: {
            /** Allow Registration */
            allow_registration: boolean;
            /** Env Default */
            env_default: boolean;
            /** Operator Name */
            operator_name?: string | null;
            /** Operator Email */
            operator_email?: string | null;
        };
        /** AdminSettingsUpdate */
        AdminSettingsUpdate: {
            /** Allow Registration */
            allow_registration?: boolean | null;
            /** Operator Name */
            operator_name?: string | null;
            /** Operator Email */
            operator_email?: string | null;
        };
        /** AdminUserUpdate */
        AdminUserUpdate: {
            /** Is Active */
            is_active?: boolean | null;
            role?: components["schemas"]["UserRole"] | null;
        };
        /** ApiCallOut */
        ApiCallOut: {
            /** Id */
            id: number;
            /**
             * At
             * Format: date-time
             */
            at: string;
            /** Provider */
            provider: string;
            /** Action */
            action: string;
            /** Subject */
            subject: string | null;
            /** Purpose */
            purpose: string;
            /** Ok */
            ok: boolean;
            /** Status */
            status: number | null;
            /** Counted */
            counted: boolean;
        };
        /**
         * ApiKeyOut
         * @description Stav jedného kľúča. Samotný kľúč sa von nikdy nevracia.
         */
        ApiKeyOut: {
            /** Is Set */
            is_set: boolean;
            /** Hint */
            hint?: string | null;
        };
        /** ApiKeysOut */
        ApiKeysOut: {
            rebrickable: components["schemas"]["ApiKeyOut"];
            brickset: components["schemas"]["ApiKeyOut"];
            brickeconomy: components["schemas"]["ApiKeyOut"];
            /** Calls Left */
            calls_left: number;
            /**
             * Capabilities
             * @default []
             */
            capabilities: string[];
        };
        /**
         * ApiKeysUpdate
         * @description None znamená nechaj tak, prázdny reťazec znamená zmaž.
         */
        ApiKeysUpdate: {
            /** Rebrickable */
            rebrickable?: string | null;
            /** Brickset */
            brickset?: string | null;
            /** Brickeconomy */
            brickeconomy?: string | null;
        };
        /** ApiUsageOut */
        ApiUsageOut: {
            /** Providers */
            providers: components["schemas"]["ProviderUsageOut"][];
            /** Calls */
            calls: components["schemas"]["ApiCallOut"][];
        };
        /** Body_create_import_api_v1_imports_post */
        Body_create_import_api_v1_imports_post: {
            /** File */
            file: string;
        };
        /** Body_upload_photo_api_v1_items__item_id__photos_post */
        Body_upload_photo_api_v1_items__item_id__photos_post: {
            /** File */
            file: string;
        };
        /** BoxSuggestionOut */
        BoxSuggestionOut: {
            /** Location */
            location: string | null;
            /** Box */
            box: string;
        };
        /** BreakdownRowOut */
        BreakdownRowOut: {
            /** Key */
            key: string | null;
            /** Label */
            label: string;
            /** Pieces */
            pieces: number;
            /** Invested */
            invested: string | null;
            /** Market Value */
            market_value: string | null;
            /** Unrealized */
            unrealized: string | null;
            /** Unrealized Pct */
            unrealized_pct: number | null;
            /** Cagr Pct */
            cagr_pct: number | null;
            /** Cagr Sample */
            cagr_sample: number;
            /** Price Missing */
            price_missing: number;
        };
        /** BricksetBackfillOut */
        BricksetBackfillOut: {
            /** Running */
            running: boolean;
            /** Done */
            done: number;
            /** Total */
            total: number;
            /** Provider Enabled */
            provider_enabled: boolean;
        };
        /**
         * BulkChangesIn
         * @description Čo zmeniť. None = nemeniť; prázdny reťazec pri umiestnení a zozname = zmazať.
         */
        BulkChangesIn: {
            /** Location */
            location?: string | null;
            /** Box */
            box?: string | null;
            /** Purpose */
            purpose?: components["schemas"]["ItemPurpose"] | "" | null;
            condition?: components["schemas"]["ItemCondition"] | null;
            /** Flags Add */
            flags_add?: string[];
            /** Flags Remove */
            flags_remove?: string[];
            /** Category Add */
            category_add?: number | null;
            /** Category Remove */
            category_remove?: number | null;
        };
        /** BulkUpdateOut */
        BulkUpdateOut: {
            /** Items */
            items: number;
            /** Sets */
            sets: number;
        };
        /**
         * BulkUpdateRequest
         * @description Hromadná úprava. Bez `item_ids` aj `catalog_nums` platí filter z adresy.
         */
        BulkUpdateRequest: {
            /** Item Ids */
            item_ids?: number[] | null;
            /** Catalog Nums */
            catalog_nums?: string[] | null;
            changes: components["schemas"]["BulkChangesIn"];
            /**
             * Dry Run
             * @default false
             */
            dry_run: boolean;
        };
        /**
         * CatalogCategoryOut
         * @description Kategória z pohľadu jedného setu, pre detail setu.
         */
        CatalogCategoryOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Color */
            color: string | null;
            /** Member */
            member: boolean;
            /** Reason */
            reason: string | null;
        };
        /** CatalogDetailOut */
        CatalogDetailOut: {
            /** Catalog Num */
            catalog_num: string;
            kind: components["schemas"]["CatalogKind"];
            /** Parent Num */
            parent_num: string | null;
            /** Series Size */
            series_size: number | null;
            /** Name */
            name: string;
            /** Year */
            year: number | null;
            /** Theme */
            theme: string | null;
            /** Subtheme */
            subtheme?: string | null;
            /** Num Parts */
            num_parts: number | null;
            /** Num Minifigs */
            num_minifigs: number | null;
            /** Image Url */
            image_url: string | null;
            /** Rrp Eur */
            rrp_eur: string | null;
            /** Is Retired */
            is_retired: boolean;
            /** Retired At */
            retired_at: number | null;
            /** Retired Date */
            retired_date?: string | null;
            /** Minifig No */
            minifig_no: string | null;
            /** Forecast 2Y Eur */
            forecast_2y_eur?: string | null;
            /** Forecast 5Y Eur */
            forecast_5y_eur?: string | null;
            /** Growth 12M Pct */
            growth_12m_pct?: number | null;
            /** Growth Last Year Pct */
            growth_last_year_pct?: number | null;
            /** Description */
            description?: string | null;
            /** Tags */
            tags?: string[] | null;
            /** Bs Rating */
            bs_rating?: number | null;
            /** Bs Rating Count */
            bs_rating_count?: number | null;
            /** Bs Owned By */
            bs_owned_by?: number | null;
            /** Bs Wanted By */
            bs_wanted_by?: number | null;
            /**
             * Brickset Checked
             * @default false
             */
            brickset_checked: boolean;
            /** Source */
            source: string;
            /**
             * Fetched At
             * Format: date-time
             */
            fetched_at: string;
            ownership?: components["schemas"]["OwnershipOut"] | null;
            /** Members */
            members?: components["schemas"]["CatalogOut"][];
        };
        /**
         * CatalogKind
         * @enum {string}
         */
        CatalogKind: "set" | "minifig";
        /** CatalogOut */
        CatalogOut: {
            /** Catalog Num */
            catalog_num: string;
            kind: components["schemas"]["CatalogKind"];
            /** Parent Num */
            parent_num: string | null;
            /** Series Size */
            series_size: number | null;
            /** Name */
            name: string;
            /** Year */
            year: number | null;
            /** Theme */
            theme: string | null;
            /** Subtheme */
            subtheme?: string | null;
            /** Num Parts */
            num_parts: number | null;
            /** Num Minifigs */
            num_minifigs: number | null;
            /** Image Url */
            image_url: string | null;
            /** Rrp Eur */
            rrp_eur: string | null;
            /** Is Retired */
            is_retired: boolean;
            /** Retired At */
            retired_at: number | null;
            /** Retired Date */
            retired_date?: string | null;
            /** Minifig No */
            minifig_no: string | null;
            /** Forecast 2Y Eur */
            forecast_2y_eur?: string | null;
            /** Forecast 5Y Eur */
            forecast_5y_eur?: string | null;
            /** Growth 12M Pct */
            growth_12m_pct?: number | null;
            /** Growth Last Year Pct */
            growth_last_year_pct?: number | null;
            /** Description */
            description?: string | null;
            /** Tags */
            tags?: string[] | null;
            /** Bs Rating */
            bs_rating?: number | null;
            /** Bs Rating Count */
            bs_rating_count?: number | null;
            /** Bs Owned By */
            bs_owned_by?: number | null;
            /** Bs Wanted By */
            bs_wanted_by?: number | null;
            /**
             * Brickset Checked
             * @default false
             */
            brickset_checked: boolean;
            /** Source */
            source: string;
            /**
             * Fetched At
             * Format: date-time
             */
            fetched_at: string;
        };
        /** CategoryIn */
        CategoryIn: {
            /** Name */
            name: string;
            /** Color */
            color?: string | null;
            /** Rules */
            rules?: components["schemas"]["CategoryRule"][];
        };
        /** CategoryOut */
        CategoryOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Color */
            color: string | null;
            /** Rules */
            rules: components["schemas"]["CategoryRule"][];
            /**
             * Sets
             * @default 0
             */
            sets: number;
            /**
             * Manual In
             * @default 0
             */
            manual_in: number;
            /**
             * Manual Out
             * @default 0
             */
            manual_out: number;
        };
        /**
         * CategoryRule
         * @description Set patrí do kategórie, keď pole katalógu sedí na hodnotu.
         */
        CategoryRule: {
            /**
             * Field
             * @enum {string}
             */
            field: "name" | "theme" | "subtheme";
            /**
             * Op
             * @default word
             * @enum {string}
             */
            op: "word" | "contains" | "equals";
            /** Value */
            value: string;
        };
        /** CategoryUpdate */
        CategoryUpdate: {
            /** Name */
            name?: string | null;
            /** Color */
            color?: string | null;
            /** Rules */
            rules?: components["schemas"]["CategoryRule"][] | null;
        };
        /** CmfMemberOut */
        CmfMemberOut: {
            catalog: components["schemas"]["CatalogOut"];
            /** Owned */
            owned: number;
            /** Wanted */
            wanted: boolean;
        };
        /** CmfOverviewOut */
        CmfOverviewOut: {
            /** Series */
            series: components["schemas"]["CmfSeriesOut"][];
            sync: components["schemas"]["CmfSyncOut"];
        };
        /** CmfSeriesDetailOut */
        CmfSeriesDetailOut: {
            series: components["schemas"]["CmfSeriesOut"];
            /** Members */
            members: components["schemas"]["CmfMemberOut"][];
        };
        /** CmfSeriesOut */
        CmfSeriesOut: {
            /** Series Num */
            series_num: string | null;
            /** Theme Id */
            theme_id: number | null;
            /** Name */
            name: string;
            /** Year */
            year: number | null;
            /** Image Url */
            image_url: string | null;
            /** Total */
            total: number;
            /** Owned */
            owned: number;
            /** Duplicates */
            duplicates: number;
            /** Sealed Bags */
            sealed_bags: number;
            /** Synced */
            synced: boolean;
            /** Category */
            category: string;
        };
        /** CmfSyncOut */
        CmfSyncOut: {
            /** Running */
            running: boolean;
            /** Done */
            done: number;
            /** Total */
            total: number;
            /** Failed */
            failed: number;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Error */
            error: string | null;
            /** Provider Enabled */
            provider_enabled: boolean;
            /**
             * Switched Off
             * @default false
             */
            switched_off: boolean;
        };
        /** DeleteAccountRequest */
        DeleteAccountRequest: {
            /** Password */
            password: string;
        };
        /** EanAssignRequest */
        EanAssignRequest: {
            /** Ean */
            ean: string;
        };
        /**
         * EanLookupOut
         * @description Výsledok hľadania podľa čiarového kódu.
         *
         *     ``outcome``: ``local`` a ``found`` majú set v ``catalog``; ``not_found``
         *     (kód nikto nepozná), ``no_set_number`` (produkt sa našiel, ale číslo
         *     setu sa z názvu vyčítať nedalo, vtedy je tu ``product_title``) a
         *     ``limit`` (bezplatná databáza kódov je na dnes vyčerpaná) a ``disabled``
         *     (hľadanie kódu je vypnuté v Nastaveniach).
         *
         *     ``cached``: neúspech je zapamätaný z hľadania ``checked_at``, von sa
         *     nešlo; ``?retry=true`` sa opýta znova.
         */
        EanLookupOut: {
            /** Outcome */
            outcome: string;
            /** Ean */
            ean: string;
            catalog?: components["schemas"]["CatalogDetailOut"] | null;
            /** Product Title */
            product_title?: string | null;
            /**
             * Cached
             * @default false
             */
            cached: boolean;
            /** Checked At */
            checked_at?: string | null;
        };
        /** FacetOption */
        FacetOption: {
            /** Value */
            value: string;
            /** Label */
            label: string;
            /** Count */
            count: number;
            /** Color */
            color?: string | null;
            /** Extra */
            extra?: string | null;
            /** Parent */
            parent?: string | null;
        };
        /**
         * FacetsOut
         * @description Počty pre panel filtrov, každá skupina bez vlastného výberu.
         */
        FacetsOut: {
            /** Total */
            total: number;
            /**
             * Hidden Figures
             * @default 0
             */
            hidden_figures: number;
            /** Category */
            category: components["schemas"]["FacetOption"][];
            /** Theme */
            theme: components["schemas"]["FacetOption"][];
            /** Subtheme */
            subtheme: components["schemas"]["FacetOption"][];
            /** Condition */
            condition: components["schemas"]["FacetOption"][];
            /** Purpose */
            purpose: components["schemas"]["FacetOption"][];
            /** Location */
            location: components["schemas"]["FacetOption"][];
            /** Flag */
            flag: components["schemas"]["FacetOption"][];
            /**
             * Tag
             * @default []
             */
            tag: components["schemas"]["FacetOption"][];
            /** Price */
            price: components["schemas"]["FacetOption"][];
            totals?: components["schemas"]["SelectionTotalsOut"] | null;
            /**
             * Place
             * @default []
             */
            place: components["schemas"]["FacetOption"][];
            /**
             * Channel
             * @default []
             */
            channel: components["schemas"]["FacetOption"][];
            /**
             * Growth
             * @default []
             */
            growth: components["schemas"]["FacetOption"][];
            /**
             * Source
             * @default []
             */
            source: components["schemas"]["FacetOption"][];
            /**
             * Rating
             * @default []
             */
            rating: components["schemas"]["FacetOption"][];
            /**
             * Imported
             * @default []
             */
            imported: components["schemas"]["FacetOption"][];
            /**
             * Purchase
             * @default []
             */
            purchase: components["schemas"]["FacetOption"][];
            /**
             * Box
             * @default []
             */
            box: components["schemas"]["FacetOption"][];
            /**
             * Retired Recent
             * @default 0
             */
            retired_recent: number;
            /** Bought Min */
            bought_min?: string | null;
            /** Bought Max */
            bought_max?: string | null;
            /** Price Low */
            price_low?: string | null;
            /** Price High */
            price_high?: string | null;
            /** Value Low */
            value_low?: string | null;
            /** Value High */
            value_high?: string | null;
            /** Retired Yes */
            retired_yes: number;
            /** Retired No */
            retired_no: number;
            /** Year Min */
            year_min: number | null;
            /** Year Max */
            year_max: number | null;
            /** Duplicates */
            duplicates: number;
        };
        /** GroupedItemOut */
        GroupedItemOut: {
            catalog: components["schemas"]["CatalogOut"];
            /** Quantity */
            quantity: number;
            /** Sold Quantity */
            sold_quantity: number;
            /** Locations */
            locations: string[];
            /** Conditions */
            conditions: {
                [key: string]: number;
            };
            /** Purchase Total */
            purchase_total: string | null;
            /** Market Total */
            market_total: string | null;
            /** Sold Total */
            sold_total: string | null;
            /** Unrealized */
            unrealized: string | null;
            /** Unrealized Pct */
            unrealized_pct: number | null;
            /** Realized */
            realized: string | null;
            /** Price Missing */
            price_missing: number;
            /**
             * Price Approx
             * @default 0
             */
            price_approx: number;
            /**
             * Purchase Auto
             * @default 0
             */
            purchase_auto: number;
            /** Cagr Pct */
            cagr_pct?: number | null;
            /** Categories */
            categories?: number[];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HealthOut
         * @description Stav appky pre Docker HEALTHCHECK a verzia, ktorú ukazujú Nastavenia.
         */
        HealthOut: {
            /** Status */
            status: string;
            /** Version */
            version: string;
        };
        /** IdentifyRequest */
        IdentifyRequest: {
            /** Catalog Num */
            catalog_num: string;
        };
        /** ImportCommitRequest */
        ImportCommitRequest: {
            /** Include Duplicates */
            include_duplicates?: number[];
        };
        /** ImportCountsOut */
        ImportCountsOut: {
            /** Rows */
            rows: number;
            /** Ok */
            ok: number;
            /** Duplicate */
            duplicate: number;
            /** Error */
            error: number;
            /** Pieces */
            pieces: number;
            /** Sold */
            sold: number;
            /** Wishes */
            wishes: number;
        };
        /** ImportOut */
        ImportOut: {
            /** Id */
            id: number;
            /** Filename */
            filename: string;
            /** State */
            state: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Committed At */
            committed_at: string | null;
            /** Undone At */
            undone_at: string | null;
            /** Progress Done */
            progress_done: number;
            /** Progress Total */
            progress_total: number;
            /** Pieces Created */
            pieces_created: number;
            /** Wishes Created */
            wishes_created: number;
            counts: components["schemas"]["ImportCountsOut"];
            /** Ignored Columns */
            ignored_columns: string[];
            /** Rows */
            rows: components["schemas"]["ImportRowOut"][];
        };
        /**
         * ImportRowOut
         * @description Jeden riadok súboru: čo z neho vznikne a čo je s ním v neporiadku.
         */
        ImportRowOut: {
            /** Line */
            line: number;
            /**
             * State
             * @enum {string}
             */
            state: "ok" | "duplicate" | "error";
            /** Raw Num */
            raw_num: string;
            /** Catalog Num */
            catalog_num: string | null;
            /** Name */
            name: string | null;
            /** Name Hint */
            name_hint: string | null;
            /** Image Url */
            image_url: string | null;
            /** Ownership */
            ownership: string;
            /** Quantity */
            quantity: number;
            /** Condition */
            condition: string;
            /** Purpose */
            purpose: string | null;
            /** Location */
            location: string | null;
            /** Flags */
            flags: string[];
            /** Unidentified */
            unidentified: boolean;
            /** Purchase Price */
            purchase_price: string | null;
            /** Purchase Date */
            purchase_date: string | null;
            /** Purchase Place */
            purchase_place: string | null;
            /** Sold Price */
            sold_price: string | null;
            /** Sold Date */
            sold_date: string | null;
            /** Sold Via */
            sold_via: string | null;
            /** Target Price */
            target_price: string | null;
            /** Note */
            note: string | null;
            /** Errors */
            errors: string[];
            /** Warnings */
            warnings: string[];
            /**
             * Duplicate Of
             * @default 0
             */
            duplicate_of: number;
        };
        /** ImportSummaryOut */
        ImportSummaryOut: {
            /** Id */
            id: number;
            /** Filename */
            filename: string;
            /** State */
            state: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Committed At */
            committed_at: string | null;
            /** Undone At */
            undone_at: string | null;
            /** Progress Done */
            progress_done: number;
            /** Progress Total */
            progress_total: number;
            /** Pieces Created */
            pieces_created: number;
            /** Wishes Created */
            wishes_created: number;
            counts: components["schemas"]["ImportCountsOut"];
        };
        /**
         * ItemBulkCreateRequest
         * @description Naraz pridá vybraných členov série.
         */
        ItemBulkCreateRequest: {
            /** Members */
            members: components["schemas"]["SeriesMemberRequest"][];
            /** @default new_sealed */
            condition: components["schemas"]["ItemCondition"];
            price_variant?: components["schemas"]["PriceVariant"] | null;
            /** Flags */
            flags?: string[];
            /** Purchase Price Eur */
            purchase_price_eur?: number | string | null;
            /** Purchase Total Eur */
            purchase_total_eur?: number | string | null;
            /** Purchase Date */
            purchase_date?: string | null;
            /** Purchase Place */
            purchase_place?: string | null;
            /** Location */
            location?: string | null;
            /** Box */
            box?: string | null;
            purpose?: components["schemas"]["ItemPurpose"] | null;
        };
        /**
         * ItemCondition
         * @enum {string}
         */
        ItemCondition: "new_sealed" | "opened_unbuilt" | "built" | "parted_out";
        /** ItemCreateRequest */
        ItemCreateRequest: {
            /** Catalog Num */
            catalog_num: string;
            /**
             * Quantity
             * @default 1
             */
            quantity: number;
            /** @default new_sealed */
            condition: components["schemas"]["ItemCondition"];
            price_variant?: components["schemas"]["PriceVariant"] | null;
            /**
             * Unidentified
             * @default false
             */
            unidentified: boolean;
            /** Flags */
            flags?: string[];
            /** Purchase Price Eur */
            purchase_price_eur?: number | string | null;
            /** Purchase Date */
            purchase_date?: string | null;
            /** Purchase Place */
            purchase_place?: string | null;
            /** Location */
            location?: string | null;
            /** Box */
            box?: string | null;
            purpose?: components["schemas"]["ItemPurpose"] | null;
            /** Manual Market Price Eur */
            manual_market_price_eur?: number | string | null;
            /** Note */
            note?: string | null;
        };
        /** ItemCreatedOut */
        ItemCreatedOut: {
            /** Id */
            id: number;
            /** Catalog Num */
            catalog_num: string;
            status: components["schemas"]["ItemStatus"];
            condition: components["schemas"]["ItemCondition"];
            price_variant: components["schemas"]["PriceVariant"] | null;
            /** Unidentified */
            unidentified: boolean;
            /** Flags */
            flags: string[];
            /** Purchase Price Eur */
            purchase_price_eur: string | null;
            /**
             * Purchase Price Auto
             * @default false
             */
            purchase_price_auto: boolean;
            /** Purchase Date */
            purchase_date: string | null;
            /** Purchase Place */
            purchase_place: string | null;
            /** Sold Price Eur */
            sold_price_eur: string | null;
            /** Sold Date */
            sold_date: string | null;
            /** Sold Via */
            sold_via: string | null;
            /** Sold Fees Eur */
            sold_fees_eur?: string | null;
            /** Sold Shipping Eur */
            sold_shipping_eur?: string | null;
            /** Location */
            location: string | null;
            /** Box */
            box?: string | null;
            purpose?: components["schemas"]["ItemPurpose"] | null;
            /** Manual Market Price Eur */
            manual_market_price_eur: string | null;
            /** Note */
            note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            catalog: components["schemas"]["CatalogOut"];
            removed_from_wishlist?: components["schemas"]["RemovedWishOut"] | null;
        };
        /** ItemOut */
        ItemOut: {
            /** Id */
            id: number;
            /** Catalog Num */
            catalog_num: string;
            status: components["schemas"]["ItemStatus"];
            condition: components["schemas"]["ItemCondition"];
            price_variant: components["schemas"]["PriceVariant"] | null;
            /** Unidentified */
            unidentified: boolean;
            /** Flags */
            flags: string[];
            /** Purchase Price Eur */
            purchase_price_eur: string | null;
            /**
             * Purchase Price Auto
             * @default false
             */
            purchase_price_auto: boolean;
            /** Purchase Date */
            purchase_date: string | null;
            /** Purchase Place */
            purchase_place: string | null;
            /** Sold Price Eur */
            sold_price_eur: string | null;
            /** Sold Date */
            sold_date: string | null;
            /** Sold Via */
            sold_via: string | null;
            /** Sold Fees Eur */
            sold_fees_eur?: string | null;
            /** Sold Shipping Eur */
            sold_shipping_eur?: string | null;
            /** Location */
            location: string | null;
            /** Box */
            box?: string | null;
            purpose?: components["schemas"]["ItemPurpose"] | null;
            /** Manual Market Price Eur */
            manual_market_price_eur: string | null;
            /** Note */
            note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            catalog: components["schemas"]["CatalogOut"];
        };
        /**
         * ItemPurpose
         * @description Na čo kus je. Umiestnenie hovorí kde, zoznam hovorí prečo.
         * @enum {string}
         */
        ItemPurpose: "investment" | "for_sale" | "display" | "build";
        /**
         * ItemStatus
         * @enum {string}
         */
        ItemStatus: "owned" | "sold" | "reserved";
        /** ItemUpdateRequest */
        ItemUpdateRequest: {
            condition?: components["schemas"]["ItemCondition"] | null;
            price_variant?: components["schemas"]["PriceVariant"] | null;
            /** Flags */
            flags?: string[] | null;
            /** Purchase Price Eur */
            purchase_price_eur?: number | string | null;
            /** Purchase Date */
            purchase_date?: string | null;
            /** Purchase Place */
            purchase_place?: string | null;
            /** Location */
            location?: string | null;
            /** Box */
            box?: string | null;
            purpose?: components["schemas"]["ItemPurpose"] | null;
            /** Manual Market Price Eur */
            manual_market_price_eur?: number | string | null;
            /** Note */
            note?: string | null;
        };
        /** LoginRequest */
        LoginRequest: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Password */
            password: string;
        };
        /**
         * ManualCatalogRequest
         * @description Ručné zadanie setu. Bez kľúča Rebrickable stačí číslo; bez názvu
         *     dostane set názov „Set 10294“.
         */
        ManualCatalogRequest: {
            /** Catalog Num */
            catalog_num: string;
            /** Name */
            name?: string | null;
            /** @default set */
            kind: components["schemas"]["CatalogKind"];
            /** Year */
            year?: number | null;
            /** Theme */
            theme?: string | null;
            /** Num Parts */
            num_parts?: number | null;
            /** Num Minifigs */
            num_minifigs?: number | null;
            /** Image Url */
            image_url?: string | null;
            /** Rrp Eur */
            rrp_eur?: number | string | null;
        };
        /** ManualPriceRequest */
        ManualPriceRequest: {
            /** Price Eur */
            price_eur: number | string;
            /**
             * Condition
             * @default N
             */
            condition: string;
        };
        /**
         * MembershipRequest
         * @description Chcem ho tam, alebo nechcem. Ako to zariadiť, rozhodne server.
         */
        MembershipRequest: {
            /** Member */
            member: boolean;
        };
        /** MoverOut */
        MoverOut: {
            /** Catalog Num */
            catalog_num: string;
            /** Name */
            name: string;
            /** Image Url */
            image_url: string | null;
            /** Price Then */
            price_then: string | null;
            /** Price Now */
            price_now: string | null;
            /** Delta */
            delta: string | null;
            /** Delta Pct */
            delta_pct: number;
        };
        /** OwnershipOut */
        OwnershipOut: {
            /** Owned */
            owned: boolean;
            /** Owned Count */
            owned_count: number;
            /** Sold Count */
            sold_count: number;
            /** Locations */
            locations: string[];
            /** Last Purchase Price */
            last_purchase_price: string | null;
            /** Last Purchase Date */
            last_purchase_date: string | null;
        };
        /** PhotoOut */
        PhotoOut: {
            /** Id */
            id: number;
            /** Item Id */
            item_id: number;
            /** Content Type */
            content_type: string;
            /** Size Bytes */
            size_bytes: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * PriceCheckOut
         * @description Riadok tabuľky naposledy overených setov.
         */
        PriceCheckOut: {
            catalog: components["schemas"]["CatalogOut"];
            /**
             * Checked At
             * Format: date-time
             */
            checked_at: string;
            /** New Value */
            new_value?: string | null;
            /** Used Value */
            used_value?: string | null;
        };
        /** PriceDeltaOut */
        PriceDeltaOut: {
            /** Window Days */
            window_days: number;
            /** Price Then */
            price_then: string | null;
            /** Price Now */
            price_now: string | null;
            /** Delta Pct */
            delta_pct: number | null;
        };
        /**
         * PriceLookupOut
         * @description Overiť cenu: čo to je a čo sa stalo s cenou.
         *
         *     ``outcome``: ok, not_found (nepozná ho nikto), no_sources (neznámy set
         *     a žiadna služba, ktorá by ho dohľadala). ``price``: fetched, cached,
         *     missing (zdroj cenu nemá), disconnected (bez BrickEconomy), quota,
         *     blocked (vypnuté v Nastaveniach), series (séria sama cenu nemá),
         *     unsupported (holá figúrka, overenie ju neceni).
         */
        PriceLookupOut: {
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "ok" | "not_found" | "no_sources";
            catalog?: components["schemas"]["CatalogDetailOut"] | null;
            /** Price */
            price?: ("fetched" | "cached" | "missing" | "disconnected" | "quota" | "blocked" | "series" | "unsupported") | null;
            /** Calls Left */
            calls_left?: number | null;
        };
        /** PriceOverviewOut */
        PriceOverviewOut: {
            /** Catalog Num */
            catalog_num: string;
            current: components["schemas"]["PricePointOut"] | null;
            /** Deltas */
            deltas: components["schemas"]["PriceDeltaOut"][];
            /** History */
            history: components["schemas"]["PricePointOut"][];
            /** Provider Enabled */
            provider_enabled: boolean;
            /** Calls Left */
            calls_left?: number | null;
            /**
             * Fetched
             * @default false
             */
            fetched: boolean;
        };
        /** PricePointOut */
        PricePointOut: {
            /**
             * Captured At
             * Format: date-time
             */
            captured_at: string;
            /** Avg Price */
            avg_price: string | null;
            /** Min Price */
            min_price: string | null;
            /** Max Price */
            max_price: string | null;
            /** Qty */
            qty: number | null;
            /** Condition */
            condition: string;
            /** Price Kind */
            price_kind: string;
            /** Source */
            source: string;
        };
        /**
         * PriceVariant
         * @description Ktorá podoba minifigúrky sa cení. Pri setoch sa nepoužíva.
         * @enum {string}
         */
        PriceVariant: "sealed" | "complete" | "figure_only";
        /**
         * ProviderStatusOut
         * @description Verejná odpoveď, pýta sa na ňu aj neprihlásený.
         *
         *     Kľúče tu nie sú. Každý používateľ má svoje a ich stav vracia
         *     ``GET /auth/me/keys``.
         */
        ProviderStatusOut: {
            /** Registration Open */
            registration_open: boolean;
            /** Operator Name */
            operator_name?: string | null;
            /** Operator Email */
            operator_email?: string | null;
            /** Privacy Version */
            privacy_version?: string | null;
        };
        /** ProviderUsageOut */
        ProviderUsageOut: {
            /** Provider */
            provider: string;
            /** Enabled */
            enabled: boolean;
            /** Used */
            used: number;
            /** Limit */
            limit: number | null;
        };
        /** PublicCollectionOut */
        PublicCollectionOut: {
            /**
             * Kind
             * @default collection
             */
            kind: string;
            /** Owner */
            owner: string;
            /** Set Count */
            set_count: number;
            /** Item Count */
            item_count: number;
            /** Parts */
            parts: number;
            /** Oldest Year */
            oldest_year: number | null;
            /** Show Values */
            show_values: boolean;
            /** Invested */
            invested?: string | null;
            /** Market Value */
            market_value?: string | null;
            /** Price Missing */
            price_missing?: number | null;
            /** Items */
            items: components["schemas"]["PublicItemOut"][];
            /** Wishes */
            wishes?: components["schemas"]["PublicWishOut"][];
        };
        /** PublicItemOut */
        PublicItemOut: {
            /** Catalog Num */
            catalog_num: string;
            /** Name */
            name: string;
            /** Theme */
            theme: string | null;
            /** Year */
            year: number | null;
            /** Num Parts */
            num_parts: number | null;
            /** Image Url */
            image_url: string | null;
            /** Quantity */
            quantity: number;
            /** Is Retired */
            is_retired: boolean;
            /** Purchase Total */
            purchase_total?: string | null;
            /** Market Total */
            market_total?: string | null;
            /** Price Missing */
            price_missing?: number | null;
        };
        /**
         * PublicWishOut
         * @description Set zo zoznamu Chcem na verejnej stránke. Poznámka sa nezdieľa.
         */
        PublicWishOut: {
            /** Catalog Num */
            catalog_num: string;
            /** Name */
            name: string;
            /** Theme */
            theme: string | null;
            /** Year */
            year: number | null;
            /** Num Parts */
            num_parts: number | null;
            /** Image Url */
            image_url: string | null;
            /** Is Retired */
            is_retired: boolean;
            /** Market Price */
            market_price?: string | null;
            /** Target Price Eur */
            target_price_eur?: string | null;
        };
        /** RefreshStatusOut */
        RefreshStatusOut: {
            /** Running */
            running: boolean;
            /** Pending */
            pending: number;
            /** Updated */
            updated: number;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Provider Enabled */
            provider_enabled: boolean;
            /**
             * Calls Left
             * @default 0
             */
            calls_left: number;
            /**
             * Quota Exhausted
             * @default false
             */
            quota_exhausted: boolean;
            /**
             * Skipped Fresh
             * @default 0
             */
            skipped_fresh: number;
        };
        /** RegisterRequest */
        RegisterRequest: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Password */
            password: string;
            /** Display Name */
            display_name?: string | null;
            /**
             * Accept Privacy
             * @default false
             */
            accept_privacy: boolean;
        };
        /**
         * RemovedWishOut
         * @description Položka Chcem, ktorú kúpa vyradila, s tým, čo treba na Späť.
         */
        RemovedWishOut: {
            /** Catalog Num */
            catalog_num: string;
            /** Name */
            name: string;
            /** Target Price Eur */
            target_price_eur: string | null;
            /** Note */
            note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** SalesChannelOut */
        SalesChannelOut: {
            /** Channel */
            channel: string | null;
            /** Label */
            label: string;
            /** Count */
            count: number;
            /** Proceeds */
            proceeds: string | null;
            /** Costs */
            costs: string | null;
            /** Purchase */
            purchase: string | null;
            /** Realized */
            realized: string | null;
            /** Roi Pct */
            roi_pct: number | null;
        };
        /** SavedViewIn */
        SavedViewIn: {
            /** Name */
            name: string;
            /** Query */
            query?: {
                [key: string]: string | number | boolean | string[] | number[];
            };
        };
        /** SavedViewOut */
        SavedViewOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Query */
            query: {
                [key: string]: unknown;
            };
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * SelectionTotalsOut
         * @description Súčty kusov, ktoré filter ukazuje. Reálne = v dnešných peniazoch.
         */
        SelectionTotalsOut: {
            /** Owned */
            owned: number;
            /** Purchase */
            purchase: string | null;
            /** Market Value */
            market_value: string | null;
            /** Unrealized */
            unrealized: string | null;
            /** Unrealized Pct */
            unrealized_pct: number | null;
            /** Price Missing */
            price_missing: number;
            /** Sold */
            sold: number;
            /** Realized */
            realized: string | null;
            /** Real Month */
            real_month: string | null;
            /** Purchase Real */
            purchase_real: string | null;
            /** Unrealized Real */
            unrealized_real: string | null;
            /** Unrealized Real Pct */
            unrealized_real_pct: number | null;
            /** Realized Real */
            realized_real: string | null;
        };
        /** SellRequest */
        SellRequest: {
            /** Sold Price Eur */
            sold_price_eur: number | string;
            /**
             * Sold Date
             * Format: date
             */
            sold_date: string;
            /** Sold Via */
            sold_via?: string | null;
            /** Sold Fees Eur */
            sold_fees_eur?: number | string | null;
            /** Sold Shipping Eur */
            sold_shipping_eur?: number | string | null;
        };
        /** SeriesMemberRequest */
        SeriesMemberRequest: {
            /** Catalog Num */
            catalog_num: string;
            /**
             * Quantity
             * @default 1
             */
            quantity: number;
        };
        /** SeriesMissingOut */
        SeriesMissingOut: {
            /** Catalog Num */
            catalog_num: string;
            /** Name */
            name: string;
            /** Image Url */
            image_url: string | null;
        };
        /** SeriesProgressOut */
        SeriesProgressOut: {
            /** Series Num */
            series_num: string;
            /** Name */
            name: string;
            /** Image Url */
            image_url: string | null;
            /** Owned */
            owned: number;
            /** Total */
            total: number;
            /** Missing */
            missing: components["schemas"]["SeriesMissingOut"][];
        };
        /** SetImageOut */
        SetImageOut: {
            /** Thumbnail Url */
            thumbnail_url: string;
            /** Image Url */
            image_url: string;
        };
        /**
         * SetImagesOut
         * @description Ďalšie fotky setu z Brickset. ``enabled`` = prepínač v Nastaveniach je zapnutý.
         */
        SetImagesOut: {
            /** Enabled */
            enabled: boolean;
            /** Images */
            images?: components["schemas"]["SetImageOut"][];
        };
        /** ShareCreateRequest */
        ShareCreateRequest: {
            /**
             * Show Values
             * @default false
             */
            show_values: boolean;
            /**
             * Kind
             * @default collection
             * @enum {string}
             */
            kind: "collection" | "wishlist";
            /** Catalog Nums */
            catalog_nums?: string[] | null;
            /** Label */
            label?: string | null;
        };
        /** ShareOut */
        ShareOut: {
            /** Id */
            id: number;
            /** Token */
            token: string;
            /** Show Values */
            show_values: boolean;
            /**
             * Kind
             * @default collection
             */
            kind: string;
            /** Catalog Nums */
            catalog_nums?: string[] | null;
            /** Label */
            label: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Last Viewed At */
            last_viewed_at: string | null;
        };
        /** ShareUpdateRequest */
        ShareUpdateRequest: {
            /** Show Values */
            show_values: boolean;
        };
        /** SourceCapabilityOut */
        SourceCapabilityOut: {
            /** Key */
            key: string;
            /** Enabled */
            enabled: boolean;
            /** Required */
            required: boolean;
            /** Counted */
            counted: boolean;
            /** Background */
            background: boolean;
            /**
             * Default Enabled
             * @default true
             */
            default_enabled: boolean;
        };
        /**
         * SourceOut
         * @description Jedna služba v Nastaveniach → Dáta.
         */
        SourceOut: {
            /** Provider */
            provider: string;
            /** Paid */
            paid: boolean;
            /** Needs Key */
            needs_key: boolean;
            key: components["schemas"]["ApiKeyOut"] | null;
            /** Available */
            available: boolean;
            /** Used Today */
            used_today: number | null;
            /** Limit */
            limit: number | null;
            /** Reserve */
            reserve: number | null;
            /** Price Batch */
            price_batch: number | null;
            /** Auto Purchase Price */
            auto_purchase_price?: boolean | null;
            /** Capabilities */
            capabilities: components["schemas"]["SourceCapabilityOut"][];
        };
        /** SourcesOut */
        SourcesOut: {
            /** Sources */
            sources: components["schemas"]["SourceOut"][];
        };
        /** SourcesUpdate */
        SourcesUpdate: {
            /** Disabled */
            disabled?: string[] | null;
            /** Enabled */
            enabled?: string[] | null;
            /** Reserve */
            reserve?: {
                [key: string]: number;
            } | null;
            /** Price Batch */
            price_batch?: number | null;
            /** Auto Purchase Price */
            auto_purchase_price?: boolean | null;
        };
        /**
         * SuggestionsOut
         * @description Už použité hodnoty textových polí, pre našepkávače vo formulároch.
         */
        SuggestionsOut: {
            /** Locations */
            locations: string[];
            /** Purchase Places */
            purchase_places: string[];
            /** Sale Channels */
            sale_channels: string[];
            /** Boxes */
            boxes?: components["schemas"]["BoxSuggestionOut"][];
        };
        /** SummaryOut */
        SummaryOut: {
            /** Invested */
            invested: string | null;
            /** Market Value */
            market_value: string | null;
            /** Unrealized */
            unrealized: string | null;
            /** Unrealized Pct */
            unrealized_pct: number | null;
            /** Realized */
            realized: string | null;
            /** Sold Proceeds */
            sold_proceeds: string | null;
            /** Sold Count */
            sold_count: number;
            /** Set Count */
            set_count: number;
            /** Item Count */
            item_count: number;
            /** Parts */
            parts: number;
            /** Minifigs */
            minifigs: number;
            /** Retired Count */
            retired_count: number;
            /** Purchases */
            purchases: number;
            /** Avg Discount Pct */
            avg_discount_pct: number | null;
            /** Discount Sample */
            discount_sample: number;
            /** Price Missing */
            price_missing: number;
            /**
             * Sold Costs
             * @default 0.00
             */
            sold_costs: string | null;
            /** Cagr Pct */
            cagr_pct?: number | null;
            /**
             * Cagr Sample
             * @default 0
             */
            cagr_sample: number;
            /** Forecast 2Y */
            forecast_2y?: string | null;
            /** Forecast 5Y */
            forecast_5y?: string | null;
            /** Forecast Base */
            forecast_base?: string | null;
            /**
             * Forecast Sample
             * @default 0
             */
            forecast_sample: number;
            /**
             * Forecast Sealed
             * @default 0
             */
            forecast_sealed: number;
            /**
             * Wishlist Hits
             * @default 0
             */
            wishlist_hits: number;
            /**
             * Wishlist Count
             * @default 0
             */
            wishlist_count: number;
            /**
             * Series Figures
             * @default 0
             */
            series_figures: number;
            /**
             * Theme Count
             * @default 0
             */
            theme_count: number;
            /**
             * Collection Set Count
             * @default 0
             */
            collection_set_count: number;
            /**
             * Collection Item Count
             * @default 0
             */
            collection_item_count: number;
            /**
             * Collection Sold Count
             * @default 0
             */
            collection_sold_count: number;
            /**
             * Sealed Bag Count
             * @default 0
             */
            sealed_bag_count: number;
            /** Themes */
            themes: components["schemas"]["ThemeSliceOut"][];
            /** Top Profit */
            top_profit: components["schemas"]["TopProfitOut"][];
            /** Real Month */
            real_month?: string | null;
        };
        /** ThemeOut */
        ThemeOut: {
            /** Theme */
            theme: string;
            /** Set Count */
            set_count: number;
            /** Year From */
            year_from: number | null;
            /** Year To */
            year_to: number | null;
            /** Owned */
            owned: number;
            /**
             * Followed
             * @default false
             */
            followed: boolean;
            /**
             * Complete
             * @default false
             */
            complete: boolean;
        };
        /** ThemeSliceOut */
        ThemeSliceOut: {
            /** Theme */
            theme: string;
            /** Key */
            key: string;
            /** Count */
            count: number;
            /** Pct */
            pct: number;
        };
        /** ThemeWaveOut */
        ThemeWaveOut: {
            /** Theme */
            theme: string;
            /** Year */
            year: number;
            /**
             * Fetched At
             * Format: date-time
             */
            fetched_at: string;
            /** Total */
            total: number;
            /** Owned */
            owned: number;
            /** Members */
            members: components["schemas"]["CmfMemberOut"][];
        };
        /** ThemeYearOut */
        ThemeYearOut: {
            /** Year */
            year: number;
            /** Set Count */
            set_count: number;
            /** Owned */
            owned: number;
            /** Exact */
            exact: boolean;
        };
        /** ThemesOut */
        ThemesOut: {
            /** Mine */
            mine: components["schemas"]["ThemeOut"][];
            /** All */
            all: components["schemas"]["ThemeOut"][];
            /** Provider Enabled */
            provider_enabled: boolean;
        };
        /** TimelinePointOut */
        TimelinePointOut: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Invested */
            invested: string | null;
            /** Market Value */
            market_value: string | null;
            /** Proceeds */
            proceeds: string | null;
        };
        /** TokenResponse */
        TokenResponse: {
            /** Access Token */
            access_token: string;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
            /** Expires In */
            expires_in: number;
        };
        /** TopProfitOut */
        TopProfitOut: {
            /** Catalog Num */
            catalog_num: string;
            /** Name */
            name: string;
            /** Theme */
            theme: string | null;
            /** Image Url */
            image_url: string | null;
            /** Quantity */
            quantity: number;
            /** Purchase */
            purchase: string | null;
            /** Market Value */
            market_value: string | null;
            /** Profit */
            profit: string | null;
            /** Profit Pct */
            profit_pct: number | null;
        };
        /** UpdateMeRequest */
        UpdateMeRequest: {
            /** Display Name */
            display_name?: string | null;
            /** Locale */
            locale?: string | null;
            /** Current Password */
            current_password?: string | null;
            /** New Password */
            new_password?: string | null;
        };
        /** UserOut */
        UserOut: {
            /** Id */
            id: number;
            /** Email */
            email: string;
            /** Display Name */
            display_name: string | null;
            role: components["schemas"]["UserRole"];
            /** Is Active */
            is_active: boolean;
            /** Locale */
            locale: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Privacy Accepted At */
            privacy_accepted_at?: string | null;
            /** Privacy Version */
            privacy_version?: string | null;
            /** Privacy Current */
            privacy_current?: string | null;
        };
        /**
         * UserRole
         * @enum {string}
         */
        UserRole: "user" | "admin";
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** ValuedItemOut */
        ValuedItemOut: {
            /** Id */
            id: number;
            /** Catalog Num */
            catalog_num: string;
            status: components["schemas"]["ItemStatus"];
            condition: components["schemas"]["ItemCondition"];
            price_variant: components["schemas"]["PriceVariant"] | null;
            /** Unidentified */
            unidentified: boolean;
            /** Flags */
            flags: string[];
            /** Purchase Price Eur */
            purchase_price_eur: string | null;
            /**
             * Purchase Price Auto
             * @default false
             */
            purchase_price_auto: boolean;
            /** Purchase Date */
            purchase_date: string | null;
            /** Purchase Place */
            purchase_place: string | null;
            /** Sold Price Eur */
            sold_price_eur: string | null;
            /** Sold Date */
            sold_date: string | null;
            /** Sold Via */
            sold_via: string | null;
            /** Sold Fees Eur */
            sold_fees_eur?: string | null;
            /** Sold Shipping Eur */
            sold_shipping_eur?: string | null;
            /** Location */
            location: string | null;
            /** Box */
            box?: string | null;
            purpose?: components["schemas"]["ItemPurpose"] | null;
            /** Manual Market Price Eur */
            manual_market_price_eur: string | null;
            /** Note */
            note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            catalog: components["schemas"]["CatalogOut"];
            /** Market Value */
            market_value: string | null;
            /** Price Source */
            price_source: string;
            /** Unrealized */
            unrealized: string | null;
            /** Realized */
            realized: string | null;
            /** Purchase Real Eur */
            purchase_real_eur?: string | null;
            /** Cagr Pct */
            cagr_pct?: number | null;
            /** Categories */
            categories?: number[];
        };
        /** WishlistCreateRequest */
        WishlistCreateRequest: {
            /** Catalog Num */
            catalog_num: string;
            /** Target Price Eur */
            target_price_eur?: number | string | null;
            /** Note */
            note?: string | null;
            /** Created At */
            created_at?: string | null;
        };
        /** WishlistOut */
        WishlistOut: {
            /** Id */
            id: number;
            /** Catalog Num */
            catalog_num: string;
            /** Target Price Eur */
            target_price_eur: string | null;
            /** Note */
            note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            catalog: components["schemas"]["CatalogOut"];
            /** Market Price */
            market_price?: string | null;
            /**
             * Target Reached
             * @default false
             */
            target_reached: boolean;
            /** Distance Pct */
            distance_pct?: number | null;
        };
        /**
         * WishlistUpdateRequest
         * @description Úprava položky Chcem. Vynechané pole sa nemení, null cieľ zmaže.
         */
        WishlistUpdateRequest: {
            /** Target Price Eur */
            target_price_eur?: number | string | null;
            /** Note */
            note?: string | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    register_api_v1_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_api_v1_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                lego_refresh?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                lego_refresh?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
        };
    };
    delete_me_api_v1_auth_me_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeleteAccountRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_me_api_v1_auth_me_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateMeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_my_sources_api_v1_auth_me_sources_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourcesOut"];
                };
            };
        };
    };
    set_my_sources_api_v1_auth_me_sources_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourcesUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourcesOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_my_keys_api_v1_auth_me_keys_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiKeysOut"];
                };
            };
        };
    };
    set_my_keys_api_v1_auth_me_keys_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApiKeysUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiKeysOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_my_preferences_api_v1_auth_me_preferences_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: {
                            [key: string]: unknown;
                        };
                    };
                };
            };
        };
    };
    set_my_preference_api_v1_auth_me_preferences__key__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: {
                            [key: string]: unknown;
                        };
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    accept_privacy_api_v1_auth_me_privacy_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
        };
    };
    export_me_api_v1_auth_me_export_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    start_brickset_backfill_api_v1_catalog_brickset_backfill_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BricksetBackfillOut"];
                };
            };
        };
    };
    fill_from_brickset_api_v1_catalog__num__brickset_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_set_images_api_v1_catalog__num__images_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SetImagesOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_by_ean_api_v1_catalog_by_ean__code__get: {
        parameters: {
            query?: {
                retry?: boolean;
            };
            header?: never;
            path: {
                code: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EanLookupOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_catalog_item_api_v1_catalog__num__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_children_api_v1_catalog__num__children_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_ownership_api_v1_catalog__num__ownership_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OwnershipOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    assign_ean_api_v1_catalog__num__ean_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EanAssignRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_catalog_item_api_v1_catalog__num__refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_manual_item_api_v1_catalog_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ManualCatalogRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_items_api_v1_items_get: {
        parameters: {
            query?: {
                sort?: "profit" | "profit_pct" | "cagr" | "value" | "purchase" | "purchased" | "year" | "parts" | "name" | "recent";
                /** @description Smer zoradenia; bez neho predvolený smer kľúča. */
                dir?: ("asc" | "desc") | null;
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ValuedItemOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_items_api_v1_items_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ItemCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemCreatedOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_grouped_api_v1_items_grouped_get: {
        parameters: {
            query?: {
                by?: "set" | "series";
                sort?: "profit" | "profit_pct" | "cagr" | "value" | "purchase" | "purchased" | "year" | "parts" | "name" | "recent";
                /** @description Smer zoradenia; bez neho predvolený smer kľúča. */
                dir?: ("asc" | "desc") | null;
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupedItemOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    item_facets_api_v1_items_facets_get: {
        parameters: {
            query?: {
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FacetsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_locations_api_v1_locations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": string[];
                };
            };
        };
    };
    list_suggestions_api_v1_suggestions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SuggestionsOut"];
                };
            };
        };
    };
    create_series_items_api_v1_items_bulk_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ItemBulkCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemCreatedOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_item_api_v1_items__item_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_item_api_v1_items__item_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_item_api_v1_items__item_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ItemUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    bulk_update_api_v1_items_bulk_update_post: {
        parameters: {
            query?: {
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BulkUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkUpdateOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    identify_item_api_v1_items__item_id__identify_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IdentifyRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sell_item_api_v1_items__item_id__sell_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SellRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unsell_item_api_v1_items__item_id__unsell_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_photos_api_v1_items__item_id__photos_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_photo_api_v1_items__item_id__photos_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_photo_api_v1_items__item_id__photos_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_all_photos_api_v1_photos_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoOut"][];
                };
            };
        };
    };
    get_photo_api_v1_photos__photo_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_photo_api_v1_photos__photo_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_categories_api_v1_categories_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryOut"][];
                };
            };
        };
    };
    create_category_api_v1_categories_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CategoryIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_category_api_v1_categories__category_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                category_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_category_api_v1_categories__category_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                category_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CategoryUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    catalog_categories_api_v1_catalog__num__categories_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogCategoryOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_member_api_v1_categories__category_id__members__num__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                category_id: number;
                num: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MembershipRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogCategoryOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_views_api_v1_views_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedViewOut"][];
                };
            };
        };
    };
    create_view_api_v1_views_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SavedViewIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedViewOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_view_api_v1_views__view_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                view_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedViewOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_status_api_v1_prices_refresh_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RefreshStatusOut"];
                };
            };
        };
    };
    refresh_all_api_v1_prices_refresh_all_post: {
        parameters: {
            query?: {
                num?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RefreshStatusOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_checks_api_v1_prices_checks_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PriceCheckOut"][];
                };
            };
        };
    };
    record_check_api_v1_prices_checks__num__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    forget_check_api_v1_prices_checks__num__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lookup_price_api_v1_prices_lookup__num__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PriceLookupOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_prices_api_v1_prices__num__get: {
        parameters: {
            query?: {
                condition?: string;
                price_kind?: string;
            };
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PriceOverviewOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_one_api_v1_prices__num__refresh_post: {
        parameters: {
            query?: {
                condition?: string;
                price_kind?: string;
                max_age_hours?: number | null;
            };
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PriceOverviewOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_manual_price_api_v1_prices__num__manual_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                num: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ManualPriceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PriceOverviewOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_summary_api_v1_stats_summary_get: {
        parameters: {
            query?: {
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SummaryOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_breakdown_api_v1_stats_breakdown_get: {
        parameters: {
            query?: {
                by?: "theme" | "subtheme" | "purpose";
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BreakdownRowOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_sales_api_v1_stats_sales_get: {
        parameters: {
            query?: {
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SalesChannelOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_timeline_api_v1_stats_timeline_get: {
        parameters: {
            query?: {
                step?: "day" | "week";
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TimelinePointOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_movers_api_v1_stats_movers_get: {
        parameters: {
            query?: {
                window?: number;
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MoverOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_series_api_v1_stats_series_get: {
        parameters: {
            query?: {
                status?: "owned" | "sold" | "all";
                q?: string | null;
                category?: number[] | null;
                kind?: ("set" | "minifig")[] | null;
                series?: string[] | null;
                theme?: string[] | null;
                subtheme?: string[] | null;
                condition?: string[] | null;
                purpose?: string[] | null;
                location?: string[] | null;
                flag?: string[] | null;
                tag?: string[] | null;
                variant?: string[] | null;
                year_from?: number | null;
                year_to?: number | null;
                retired?: boolean | null;
                price?: ("gain" | "loss" | "even" | "missing")[] | null;
                duplicates?: boolean;
                incomplete?: boolean;
                bought_from?: string | null;
                bought_to?: string | null;
                price_min?: number | string | null;
                price_max?: number | string | null;
                value_min?: number | string | null;
                value_max?: number | string | null;
                place?: string[] | null;
                channel?: string[] | null;
                rating_min?: number | null;
                growth?: ("up" | "down" | "none")[] | null;
                source?: ("market" | "market_approx" | "manual" | "missing" | "stale")[] | null;
                retired_recent?: boolean;
                imported?: number[] | null;
                purchase?: ("manual" | "auto" | "none")[] | null;
                box?: string[] | null;
                /** @description Sumy v dnešných peniazoch, prepočítané infláciou. */
                real?: boolean;
                /** @description Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú. */
                sets_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SeriesProgressOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_share_links_api_v1_share_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShareOut"][];
                };
            };
        };
    };
    create_share_link_api_v1_share_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ShareCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShareOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_share_link_api_v1_share__link_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                link_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_share_link_api_v1_share__link_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                link_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ShareUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShareOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    public_collection_api_v1_public__token__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                token: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicCollectionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_series_api_v1_minifigs_series_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CmfOverviewOut"];
                };
            };
        };
    };
    series_detail_api_v1_minifigs_series__series_num__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                series_num: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CmfSeriesDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sync_status_api_v1_minifigs_sync_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CmfSyncOut"];
                };
            };
        };
    };
    start_sync_api_v1_minifigs_sync_post: {
        parameters: {
            query?: {
                force?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CmfSyncOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_themes_api_v1_themes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ThemesOut"];
                };
            };
        };
    };
    theme_years_api_v1_themes_years_get: {
        parameters: {
            query: {
                theme: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ThemeYearOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    theme_wave_api_v1_themes_wave_get: {
        parameters: {
            query: {
                theme: string;
                year: number;
                force?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ThemeWaveOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    usage_api_v1_usage_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiUsageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    image_api_v1_img_get: {
        parameters: {
            query: {
                u: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_template_xlsx_api_v1_imports_template_xlsx_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    download_template_csv_api_v1_imports_template_csv_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    list_imports_api_v1_imports_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportSummaryOut"][];
                };
            };
        };
    };
    create_import_api_v1_imports_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_import_api_v1_imports_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_import_api_v1_imports__import_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discard_import_api_v1_imports__import_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    commit_import_api_v1_imports__import_id__commit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportCommitRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    undo_import_api_v1_imports__import_id__undo_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    providers_status_api_v1_providers_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderStatusOut"];
                };
            };
        };
    };
    list_wishlist_api_v1_wishlist_get: {
        parameters: {
            query?: {
                sort?: "distance" | "market" | "target" | "name" | "theme" | "added";
                dir?: ("asc" | "desc") | null;
                q?: string | null;
                reached?: boolean;
                retired?: boolean;
                no_price?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WishlistOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_wishlist_api_v1_wishlist_post: {
        parameters: {
            query?: {
                unless_owned?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WishlistCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WishlistOut"];
                };
            };
            /** @description S unless_owned: set účet ešte má, do Chcem sa nevrátil. */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_wishlist_api_v1_wishlist__item_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_wishlist_api_v1_wishlist__item_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WishlistUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WishlistOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_csv_api_v1_export_items_csv_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    list_users_api_v1_admin_users_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"][];
                };
            };
        };
    };
    get_app_settings_api_v1_admin_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminSettingsOut"];
                };
            };
        };
    };
    update_app_settings_api_v1_admin_settings_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdminSettingsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminSettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_user_api_v1_admin_users__user_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_user_api_v1_admin_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdminUserUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
        };
    };
}
