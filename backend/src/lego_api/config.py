"""Nastavenia aplikácie načítané z prostredia alebo .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Databáza
    database_url: str = "sqlite+aiosqlite:///./data/lego.db"

    # Autentifikácia
    jwt_secret: str = "zmen-ma-v-produkcii"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    #: Zapamätané prihlásenie („Zapamätať si prihlásenie na tomto počítači“):
    #: trvalé cookie, pri každej obnove tokenu sa posunie.
    refresh_token_days: int = 30
    #: Prihlásenie bez zapamätania: session cookie zanikne so zatvorením
    #: prehliadača, lenže prehliadač s obnovou kariet ho vráti aj po reštarte.
    #: Server ho preto stráži sám: po 12 h bez použitia (noc, zabudnutá
    #: karta na cudzom počítači) sa pýta heslo, cez deň obnova stačí.
    refresh_session_hours: int = 12
    #: Ochranná lehota po výmene obnovovacieho tokenu. Karty obnovené naraz
    #: pošlú to isté cookie; kto príde do lehoty po výmene, dostane len
    #: prístupový token (nové cookie už prehliadač má z prvej odpovede).
    #: Vymenený token po lehote znamená krádež: skončia všetky prihlásenia účtu.
    refresh_grace_seconds: int = 60
    cookie_secure: bool = False
    cookie_domain: str | None = None
    #: Verejná adresa appky (napr. https://kocky.example.sk) pre náhľad odkazu
    #: (Open Graph, `social.py`). Bez nej sa vezme z hlavičiek proxy či požiadavky.
    public_url: str | None = None
    #: Len východisko pre novú inštaláciu. Správca to prebije v Nastaveniach.
    allow_registration: bool = True

    # Kľúče k cudzím službám (Rebrickable, Brickset, BrickEconomy) tu nie sú.
    # Každý používateľ má svoje vlastné, uložené zašifrované pri účte,
    # a teda aj vlastnú dennú kvótu volaní. Pozri services/keys.py.

    #: Denná kvóta kľúča BrickEconomy je 100 volaní; appka ju využije celú.
    #: Po odpovedi 429 sa dávka zastaví, takže prekročenie nič nepokazí.
    brickeconomy_daily_limit: int = 100

    # Obnova cien pri prihlásení
    #: Hromadná obnova ťahá len ceny staršie než týždeň. Zdroj mení hodnoty
    #: zhruba raz za dva týždne, denné ťahanie by vracalo to isté číslo
    #: a pri 100 volaniach denne by zbierka so sériami minula celú kvótu.
    price_max_age_hours: int = 168
    #: Strop na jedno prihlásenie. Jedna položka = jedno volanie, obidva stavy naraz.
    price_refresh_budget: int = 40
    price_refresh_delay_seconds: float = 1.0
    price_currency: str = "EUR"

    # Rozpoznanie zberateľskej série.
    # Rebrickable dáva každej figúrke vlastné číslo (71046-1 až 71046-12)
    # a drží ich pokope nadradená téma s týmto názvom.
    cmf_parent_theme: str = "Collectible Minifigures"
    series_min_members: int = 2

    # Vlastné fotky kusov. V kontajneri leží na tom istom zväzku ako databáza.
    photos_dir: str = "./data/photos"
    #: Najväčší nahrávaný súbor (fotka z mobilu), pred zmenšením.
    photo_max_bytes: int = 20 * 1024 * 1024
    #: Najväčšia uložená fotka po zmenšení a prekódovaní na JPEG.
    photo_stored_max_bytes: int = 1024 * 1024
    photos_per_item: int = 12
    #: Verzia zásad ochrany súkromia (frontend `/sukromie`). Po zmene textu
    #: zvýšiť; prihlásený používateľ uvidí jednorazové oznámenie.
    privacy_version: str = "2026-10-01.3"

    # Ostatné
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    http_timeout_seconds: float = 10.0
    #: Bezplatné vyhľadanie čiarového kódu, bez kľúča, asi 100 dotazov denne.
    upcitemdb_url: str = "https://api.upcitemdb.com/prod/trial/lookup"
    #: Prepočet infláciou (Eurostat). Testy ho vypínajú, aby nešli na sieť.
    inflation_enabled: bool = True
    #: HICP Slovenska, všetky položky, 2015 = 100 (ECOICOP v2).
    eurostat_hicp_url: str = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
