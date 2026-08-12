"""Tests for craft empower-component mapping."""

from __future__ import annotations

from eq_augs.craft_components import (
    craft_component_for_aug,
    owns_craft_component,
)


def test_craft_component_for_affix_lines():
    assert craft_component_for_aug("Acrobat's Gem of Unraveling Order").name == (
        "Unraveling Focus of Fortitude"
    )
    assert craft_component_for_aug(
        "Reactive Sharpened Gem of Unraveling Order"
    ).item_id == 170818
    assert craft_component_for_aug("Phantasmal Luclinite Gem of Vigor").name == (
        "Otherworldly Focus of Fortitude"
    )
    assert craft_component_for_aug("Adroit Gem of Perpetual Reverie").name == (
        "Gallant Focus of Fortitude"
    )
    assert craft_component_for_aug("Protector's Gem of Uprising").name == (
        "Fortitude Focus of Uprising"
    )
    assert craft_component_for_aug("Luclinite Ensanguined Gem of Security").name == (
        "Ossified Bloodied Ore"
    )
    assert craft_component_for_aug("Joy of the Dancer") is None
    assert craft_component_for_aug(None) is None


def test_owns_craft_component_by_id_or_name():
    component = craft_component_for_aug("Acrobat's Gem of Unraveling Order")
    assert component is not None
    assert owns_craft_component(component, owned_item_ids={170818})
    assert owns_craft_component(
        component,
        owned_item_names={"unraveling focus of fortitude"},
    )
    assert not owns_craft_component(component, owned_item_ids={1}, owned_item_names=set())
