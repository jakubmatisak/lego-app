"""Obnova cien pri prihlásení a jej poistky proti plytvaniu kvótou."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from lego_api.config import Settings
from lego_api.models import (
    CatalogItem,
    CatalogKind,
    CollectionItem,
    ItemCondition,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
    User,
)
from lego_api.providers.brickeconomy import MarketData, PricePoint, QuotaExhausted
from lego_api.services import refresh as refresh_module
from lego_api.services.refresh import collect_targets, refresh_prices, reset_state


def _market(num: str, **kwargs) -> MarketData:
    defaults = dict(
        catalog_num=num,
        kind=PriceKind.SET,
        currency="EUR",
        source="fake",
        new_value=Decimal("945"),
        used_value=Decimal("700"),
    )
    return MarketData(**{**defaults, **kwargs})


class FakeProvider:
    """Zaznamenáva, na čo sa appka pýtala, a čo vrátila."""

    name = "fake"
    #: Odtlačok kľúča; prístup k stiahnutým cenám sa zapisuje podľa neho.
    fingerprint = "fp-be"

    def __init__(
        self,
        answers: dict | None = None,
        enabled: bool = True,
        budget: int = 100,
        reported: int | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self._answers = answers or {}
        self._enabled = enabled
        self._budget = budget
        # Počítadlo v pamäti môže tvrdiť viac, než server naozaj povolí.
        self._reported = reported

    @property
    def enabled(self) -> bool:
        return self._enabled

    def remaining_calls(self) -> int:
        if self._reported is not None:
            return self._reported
        return max(0, self._budget - len(self.calls))

    async def get_market(self, num, kind, *, cap):
        # Skutočný strop je ``budget``, aj keď počítadlo tvrdí niečo iné.
        if len(self.calls) >= self._budget:
            raise QuotaExhausted("kvóta")
        self.calls.append((num, kind.value))
        if num in self._answers:
            return self._answers[num]
        return _market(num, kind=kind)


@pytest.fixture(autouse=True)
def clean_state():
    reset_state()
    yield
    reset_state()


@pytest.fixture
def fast_settings() -> Settings:
    return Settings(
        brickeconomy_key="be-key",
        price_refresh_delay_seconds=0.0,
        price_max_age_hours=24,
        price_refresh_budget=60,
    )


async def _seed(session, *, catalog_nums: list[str], user_id: int = 1) -> None:
    session.add(User(id=user_id, email=f"u{user_id}@x.sk", password_hash="x"))
    for num in catalog_nums:
        session.add(CatalogItem(catalog_num=num, name=num, kind=CatalogKind.SET))
        session.add(
            CollectionItem(
                user_id=user_id,
                catalog_num=num,
                condition=ItemCondition.NEW_SEALED,
                flags=[],
                purchase_price_eur=Decimal("100"),
            )
        )
    await session.commit()


def _snapshot(num: str, hours_ago: float, condition=PriceCondition.NEW) -> PriceSnapshot:
    return PriceSnapshot(
        catalog_num=num,
        source="brickeconomy",
        price_kind=PriceKind.SET,
        condition=condition,
        avg_price=Decimal("900"),
        captured_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )


async def test_targets_include_owned_items(session, fast_settings) -> None:
    await _seed(session, catalog_nums=["10294-1", "75192-1"])
    plan = await collect_targets(session, 1, fast_settings)
    assert {t.catalog_num for t in plan.targets} == {"10294-1", "75192-1"}


async def test_fresh_snapshot_is_skipped(session, fast_settings) -> None:
    """Prvá poistka: cena mladšia než 24 hodín sa neťahá znova."""
    await _seed(session, catalog_nums=["10294-1"])
    session.add(_snapshot("10294-1", hours_ago=2))
    await session.commit()

    plan = await collect_targets(session, 1, fast_settings)
    assert plan.targets == []
    assert plan.skipped_fresh == 1


async def test_stale_snapshot_is_refreshed(session, fast_settings) -> None:
    await _seed(session, catalog_nums=["10294-1"])
    session.add(_snapshot("10294-1", hours_ago=30))
    await session.commit()

    plan = await collect_targets(session, 1, fast_settings)
    assert len(plan.targets) == 1


async def test_budget_caps_the_batch(session, fast_settings) -> None:
    """Druhá poistka: dávka má strop, zvyšok sa dobehne nabudúce."""
    fast_settings.price_refresh_budget = 3
    await _seed(session, catalog_nums=[f"{i}-1" for i in range(10)])
    plan = await collect_targets(session, 1, fast_settings)
    assert len(plan.targets) == 3
    assert plan.over_budget == 7


async def test_remaining_quota_caps_the_batch(session, fast_settings) -> None:
    """Tretia poistka: zvyšok dennej kvóty je tvrdší strop než dávka."""
    await _seed(session, catalog_nums=[f"{i}-1" for i in range(10)])
    plan = await collect_targets(session, 1, fast_settings, budget=2)
    assert len(plan.targets) == 2
    assert plan.over_budget == 8


async def test_oldest_snapshots_go_first(session, fast_settings) -> None:
    fast_settings.price_refresh_budget = 1
    await _seed(session, catalog_nums=["stary-1", "novsi-1"])
    session.add(_snapshot("stary-1", hours_ago=400))
    session.add(_snapshot("novsi-1", hours_ago=30))
    await session.commit()

    plan = await collect_targets(session, 1, fast_settings)
    assert [t.catalog_num for t in plan.targets] == ["stary-1"]


async def test_both_conditions_share_one_call(session, sessionmaker_, fast_settings) -> None:
    """Štvrtá poistka: nový aj postavený kus toho istého setu = jedno volanie."""
    await _seed(session, catalog_nums=["10294-1"])
    session.add(
        CollectionItem(
            user_id=1,
            catalog_num="10294-1",
            condition=ItemCondition.BUILT,
            flags=[],
            purchase_price_eur=Decimal("100"),
        )
    )
    await session.commit()

    provider = FakeProvider()
    state = await refresh_prices(sessionmaker_, 1, fast_settings, provider)

    assert len(provider.calls) == 1
    assert state.updated == 1

    async with sessionmaker_() as check:
        rows = list((await check.execute(select(PriceSnapshot))).scalars())
    assert {str(r.condition) for r in rows} == {"N", "U"}


async def test_history_is_stored_and_not_duplicated(session, sessionmaker_, fast_settings) -> None:
    """História príde v tej istej odpovedi, druhá obnova ju nezdvojí."""
    await _seed(session, catalog_nums=["10294-1"])
    day = datetime(2026, 8, 1, 12, tzinfo=UTC)
    answer = _market(
        "10294-1",
        used_value=None,
        history_new=[
            PricePoint(captured_at=day, value=Decimal("800")),
            PricePoint(captured_at=day + timedelta(days=7), value=Decimal("850")),
        ],
    )
    provider = FakeProvider(answers={"10294-1": answer})

    await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    async with sessionmaker_() as check:
        first = list((await check.execute(select(PriceSnapshot))).scalars())
    # dve historické udalosti plus aktuálna hodnota
    assert len(first) == 3

    reset_state()
    fast_settings.price_max_age_hours = 0
    await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    async with sessionmaker_() as check:
        second = list((await check.execute(select(PriceSnapshot))).scalars())
    # pribudne len nová aktuálna hodnota, história sa nezopakuje
    assert len(second) == 4


async def test_catalog_learns_from_the_price_answer(session, sessionmaker_, fast_settings) -> None:
    """Odporúčaná cena a číslo figúrky prídu zadarmo, škoda ich zahodiť."""
    await _seed(session, catalog_nums=["71046-1"])
    answer = _market(
        "71046-1",
        rrp_eur=Decimal("3.99"),
        is_retired=True,
        retired_year=2024,
        minifig_no="col436",
    )
    await refresh_prices(sessionmaker_, 1, fast_settings, FakeProvider(answers={"71046-1": answer}))

    async with sessionmaker_() as check:
        catalog = await check.get(CatalogItem, "71046-1")
    assert catalog is not None
    assert catalog.rrp_eur == Decimal("3.99")
    assert catalog.is_retired is True
    assert catalog.retired_at == 2024
    assert catalog.minifig_no == "col436"


async def test_quota_stops_the_batch(session, sessionmaker_, fast_settings) -> None:
    """Keď server povie 429 uprostred dávky, zvyšok sa nepokúša."""
    await _seed(session, catalog_nums=[f"{i}-1" for i in range(5)])
    provider = FakeProvider(budget=2, reported=100)
    state = await refresh_prices(sessionmaker_, 1, fast_settings, provider)

    assert len(provider.calls) == 2
    assert state.updated == 2
    assert state.last_error == "quota"
    assert refresh_module._inflight == set()


async def test_exhausted_quota_skips_the_run(session, sessionmaker_, fast_settings) -> None:
    await _seed(session, catalog_nums=["10294-1"])
    provider = FakeProvider(budget=0)
    state = await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    assert provider.calls == []
    assert state.last_error == "quota"


async def test_disabled_provider_does_nothing(session, sessionmaker_, fast_settings) -> None:
    await _seed(session, catalog_nums=["10294-1"])
    provider = FakeProvider(enabled=False)
    state = await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    assert provider.calls == []
    assert state.updated == 0


async def test_concurrent_run_is_ignored(session, sessionmaker_, fast_settings) -> None:
    """Piata poistka: druhé spustenie počas behu nespustí druhú dávku."""
    await _seed(session, catalog_nums=["10294-1"])
    state = refresh_module.get_state(1)
    state.running = True
    provider = FakeProvider()
    await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    assert provider.calls == []
    state.running = False


async def test_two_users_with_the_same_set_fetch_once(
    session, sessionmaker_, fast_settings
) -> None:
    await _seed(session, catalog_nums=["10294-1"], user_id=1)
    session.add(User(id=2, email="u2@x.sk", password_hash="x"))
    session.add(
        CollectionItem(
            user_id=2,
            catalog_num="10294-1",
            condition=ItemCondition.NEW_SEALED,
            flags=[],
            purchase_price_eur=Decimal("100"),
        )
    )
    await session.commit()

    provider = FakeProvider()
    await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    first_calls = len(provider.calls)

    # Druhý používateľ má teraz čerstvú cenu a už sa neťahá.
    plan = await collect_targets(session, 2, fast_settings)
    assert first_calls == 1
    assert plan.targets == []


async def test_provider_failure_does_not_break_the_batch(
    session, sessionmaker_, fast_settings
) -> None:
    await _seed(session, catalog_nums=["dobry-1", "zly-1"])

    class Flaky(FakeProvider):
        async def get_market(self, num, kind, *, cap):
            if num == "zly-1":
                raise RuntimeError("zdroj spadol")
            return await super().get_market(num, kind, cap=cap)

    provider = Flaky()
    state = await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    assert state.updated == 1
    assert state.last_error is not None


async def test_refresh_can_be_limited_to_one_set(session, sessionmaker_, fast_settings) -> None:
    """Obnova jedného setu nesiaha na zvyšok zbierky, kvóta sa nemíňa."""
    await _seed(session, catalog_nums=["10294-1", "75192-1", "21318-1"])
    provider = FakeProvider()
    await refresh_prices(sessionmaker_, 1, fast_settings, provider, only="75192-1")

    assert provider.calls == [("75192-1", "SET")]


async def test_series_refresh_asks_for_members_not_the_series(
    session, sessionmaker_, fast_settings
) -> None:
    """Číslo série si vyrába appka, zdroj cien ho nepozná.

    Volanie naň by skončilo chybou a zbytočne ukrojilo z kvóty, preto sa
    obnovia figúrky, ktoré používateľ zo série má.
    """
    session.add(User(id=1, email="u1@x.sk", password_hash="x"))
    session.add(CatalogItem(catalog_num="71051", name="Series 28", series_size=12))
    for index in (1, 3):
        session.add(
            CatalogItem(
                catalog_num=f"71051-{index}",
                name=f"Figúrka {index}",
                kind=CatalogKind.MINIFIG,
                parent_num="71051",
            )
        )
        session.add(CollectionItem(user_id=1, catalog_num=f"71051-{index}", flags=[]))
    session.add(CatalogItem(catalog_num="10294-1", name="Titanic"))
    session.add(CollectionItem(user_id=1, catalog_num="10294-1", flags=[]))
    await session.commit()

    provider = FakeProvider()
    await refresh_prices(sessionmaker_, 1, fast_settings, provider, only="71051")

    assert sorted(num for num, _ in provider.calls) == ["71051-1", "71051-3"]


async def test_limited_refresh_reports_fresh_prices(session, sessionmaker_, fast_settings) -> None:
    """Keď je cena z dnes, nič sa neťahá a používateľ sa dozvie prečo."""
    await _seed(session, catalog_nums=["10294-1"])
    session.add(_snapshot("10294-1", hours_ago=2))
    await session.commit()

    provider = FakeProvider()
    state = await refresh_prices(sessionmaker_, 1, fast_settings, provider, only="10294-1")

    assert provider.calls == []
    assert state.skipped_fresh == 1


async def test_manual_refresh_ignores_the_age_guard(session, sessionmaker_, fast_settings) -> None:
    """Ručná obnova z detailu chce cenu teraz, aj keď je snímka mladšia."""
    await _seed(session, catalog_nums=["10294-1"])
    session.add(_snapshot("10294-1", hours_ago=2))
    await session.commit()

    provider = FakeProvider()
    await refresh_prices(sessionmaker_, 1, fast_settings, provider, only="10294-1", force=True)

    assert provider.calls == [("10294-1", "SET")]


async def test_forced_refresh_still_respects_the_quota(
    session, sessionmaker_, fast_settings
) -> None:
    """Aj ručná obnova série končí na zvyšku dennej kvóty."""
    await _seed(session, catalog_nums=[f"{i}-1" for i in range(5)])
    provider = FakeProvider(budget=2)
    await refresh_prices(sessionmaker_, 1, fast_settings, provider, force=True)
    assert len(provider.calls) == 2


def test_bulk_refresh_waits_a_week_by_default() -> None:
    """Zdroj mení hodnoty zhruba raz za dva týždne, denné ťahanie míňa kvótu."""
    assert Settings().price_max_age_hours == 168


async def test_batch_plans_within_the_reserve(session, sessionmaker_, fast_settings) -> None:
    """Rezerva BrickEconomy: dávka si ju nechá pri plánovaní, nehlási „kvóta minutá“."""
    from lego_api.services.fetch_policy import FetchPolicy

    await _seed(session, catalog_nums=[f"{i}-1" for i in range(30)])
    provider = FakeProvider(budget=30)
    provider.policy = FetchPolicy(reserve={"brickeconomy": 10})
    state = await refresh_prices(sessionmaker_, 1, fast_settings, provider)
    assert len(provider.calls) == 20
    assert state.last_error is None
