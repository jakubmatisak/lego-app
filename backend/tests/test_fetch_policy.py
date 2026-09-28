"""Pravidlá sťahovania: register schopností, nastavenia účtu a brána."""

import pytest

from lego_api.capabilities import CAPABILITIES, PROVIDERS, Cap
from lego_api.models import User
from lego_api.services.fetch_policy import FetchPolicy, gate, parse_settings, policy_of


def test_every_capability_belongs_to_a_known_provider() -> None:
    assert set(CAPABILITIES) == set(Cap)
    for spec in CAPABILITIES.values():
        assert spec.provider in PROVIDERS


def test_everything_is_enabled_by_default() -> None:
    policy = FetchPolicy()
    assert all(policy.enabled(cap) for cap in Cap)


def test_required_capability_cannot_be_disabled() -> None:
    policy = FetchPolicy(disabled=frozenset({Cap.REBRICKABLE_SET, Cap.BRICKSET_ON_ADD}))
    assert policy.enabled(Cap.REBRICKABLE_SET)
    assert not policy.enabled(Cap.BRICKSET_ON_ADD)


async def test_gate_blocks_disabled_capability() -> None:
    policy = FetchPolicy(disabled=frozenset({Cap.BRICKSET_BARCODE}))
    assert await gate(policy, Cap.BRICKSET_BARCODE, remaining=100) == "disabled"
    assert await gate(policy, Cap.BRICKSET_ON_ADD, remaining=100) is None


async def test_background_stops_at_reserve_on_demand_goes_to_the_limit() -> None:
    policy = FetchPolicy(reserve={"brickset": 20})
    # Dopĺňanie na pozadí nechá rezervu pre skenovanie a pridávanie.
    assert await gate(policy, Cap.BRICKSET_BACKFILL, remaining=21) is None
    assert await gate(policy, Cap.BRICKSET_BACKFILL, remaining=20) == "reserve"
    assert await gate(policy, Cap.BRICKSET_ON_ADD, remaining=1) is None
    assert await gate(policy, Cap.BRICKSET_ON_ADD, remaining=0) == "limit"
    # Služba bez limitu (Rebrickable) sa nepočíta.
    assert await gate(policy, Cap.REBRICKABLE_SERIES_SYNC, remaining=None) is None


def test_parse_settings_validates() -> None:
    assert parse_settings({"disabled": ["brickset.waves"], "reserve": {"brickset": 10}}) == {
        "disabled": ["brickset.waves"],
        "reserve": {"brickset": 10},
    }
    with pytest.raises(ValueError, match="nepoznám"):
        parse_settings({"disabled": ["brickset.neexistuje"]})
    with pytest.raises(ValueError, match="vypnúť nedá"):
        parse_settings({"disabled": ["rebrickable.set"]})
    with pytest.raises(ValueError):
        parse_settings({"reserve": {"brickset": -1}})
    with pytest.raises(ValueError):
        parse_settings({"price_batch": 0})


def test_policy_of_user_reads_stored_settings() -> None:
    user = User(id=5, fetch_settings={"disabled": ["brickset.waves"], "price_batch": 10})
    policy = policy_of(user)
    assert policy.user_id == 5
    assert not policy.enabled(Cap.BRICKSET_WAVES)
    assert policy.price_batch == 10
    assert policy.reserve["brickset"] == 20
