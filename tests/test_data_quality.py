import pandas as pd
import pytest

from livraison_express.core.data_quality import clean_orders_data, validate_dataset


def test_valid_dataset_passes(orders):
    validate_dataset(orders)


def test_duplicated_order_id_is_rejected(orders):
    with_duplicate = pd.concat([orders, orders.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="dupliqués"):
        validate_dataset(with_duplicate)


def test_missing_column_is_rejected(orders):
    with pytest.raises(ValueError, match="distance_km"):
        validate_dataset(orders.drop(columns=["distance_km"]))


def test_negative_distance_is_rejected(orders):
    invalid = orders.copy()
    invalid.loc[0, "distance_km"] = -1

    with pytest.raises(ValueError, match="distance"):
        validate_dataset(invalid)


def test_cleaning_fixes_duplicates_and_invalid_rows(orders):
    dirty = pd.concat([orders, orders.iloc[[0]]], ignore_index=True)
    dirty.loc[5, "carrier_capacity"] = 3

    cleaned = clean_orders_data(dirty)

    validate_dataset(cleaned)
    assert len(cleaned) == len(orders) - 1


def test_cleaning_does_not_modify_input(orders):
    original = orders.copy()

    clean_orders_data(orders)

    pd.testing.assert_frame_equal(orders, original)
