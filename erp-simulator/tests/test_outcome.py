import inspect
import math
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from generator import OrderGenerator
from outcome import eligibility_probability, eligibility_score, express_eligible

TODAY = date(2026, 11, 20)
SIMULATOR_DIR = Path(inspect.getfile(express_eligible)).parent

# An ERP order shaped like generator.build() output, with round values.
ORDER = {
    "order_id": "ERP-00011001",
    "order_date": date(2026, 11, 18),
    "hour": 14,
    "day_of_week": 2,
    "weekend": 0,
    "distance_km": 5.0,
    "order_value_eur": 80.0,
    "weight_kg": 2.0,
    "stock_available": 1,
    "preparation_time_min": 20.0,
    "carrier_capacity": 40.0,
    "weather": "rain",
    "delivery_zone": "suburb",
    "customer_type": "business",
}


def test_score_is_the_course_heuristic_with_erp_values():
    # Notebook cell 8, term by term: rain 0.10, suburb 0.175, business +0.15, capacity 40/50.
    expected = (
        2.5 - 0.18 * 5 - 0.035 * 20 - 0.035 * 2 - 0.175 - 0.10 + 1.8 + 1.3 * 40 / 50 + 0.15
    )

    assert eligibility_score(ORDER) == pytest.approx(expected)


def test_probability_is_the_sigmoid_of_the_score():
    score = eligibility_score(ORDER)

    assert eligibility_probability(ORDER) == pytest.approx(1 / (1 + math.exp(-score)))


def test_late_orders_lose_eligibility_after_18h():
    at_18 = eligibility_score({**ORDER, "hour": 18})

    assert eligibility_score({**ORDER, "hour": 19}) == pytest.approx(at_18 - 0.08)
    assert eligibility_score({**ORDER, "hour": 10}) == pytest.approx(at_18)


def test_carrier_capacity_is_converted_to_a_share_of_the_maximum():
    full = eligibility_score({**ORDER, "carrier_capacity": 50})
    low = eligibility_score({**ORDER, "carrier_capacity": 5})

    # Raw values would add 1.3 * 45 = 58.5 to the score and make almost every order eligible.
    assert full - low == pytest.approx(1.3 * 45 / 50)


@pytest.mark.parametrize("capacity", [-1, 50.01, 120])
def test_capacity_outside_the_assumed_range_is_rejected(capacity):
    with pytest.raises(ValueError, match="carrier_capacity"):
        express_eligible({**ORDER, "carrier_capacity": capacity})


@pytest.mark.parametrize(
    ("field", "value"),
    # The application's vocabulary is not the ERP's: these must not be scored silently.
    [("weather", "pluie"), ("delivery_zone", "banlieue"), ("customer_type", "premium")],
)
def test_unknown_values_are_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        express_eligible({**ORDER, field: value})


def test_missing_preparation_time_gives_no_outcome():
    assert express_eligible({**ORDER, "preparation_time_min": None}) is None


def test_missing_weekend_column_is_scored_from_the_real_weekday():
    saturday = {**ORDER, "day_of_week": 5, "weekend": 1}
    before_migration = {**saturday, "weekend": None}

    assert eligibility_score(before_migration) == pytest.approx(eligibility_score(saturday))
    assert express_eligible(before_migration) == express_eligible(saturday)


def test_orders_before_july_2017_have_no_outcome():
    orders = OrderGenerator().old_history(3000, TODAY)

    for order in orders:
        has_no_outcome = express_eligible(order) is None
        assert has_no_outcome == (order["order_date"] < date(2017, 7, 1)), order["order_id"]


def test_same_order_always_gets_the_same_outcome():
    assert len({express_eligible(dict(ORDER)) for _ in range(20)}) == 1


def _outcomes_in_a_new_process(hash_seed: str) -> str:
    code = (
        "from datetime import date\n"
        "from generator import OrderGenerator\n"
        "from outcome import express_eligible\n"
        "orders = OrderGenerator().recent_history(300, date(2026, 11, 20))\n"
        "print(''.join(str(express_eligible(o)) for o in orders))\n"
    )
    env = {**os.environ, "PYTHONPATH": str(SIMULATOR_DIR), "PYTHONHASHSEED": hash_seed}
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_outcomes_do_not_depend_on_the_process():
    # hash() changes with PYTHONHASHSEED; a seed built from it would relabel orders on restart.
    in_this_process = "".join(
        str(express_eligible(o)) for o in OrderGenerator().recent_history(300, TODAY)
    )

    assert _outcomes_in_a_new_process("1") == _outcomes_in_a_new_process("2") == in_this_process


def test_outcome_is_a_random_draw_not_a_threshold():
    orders = OrderGenerator().recent_history(2000, TODAY)
    pairs = [(eligibility_probability(o), express_eligible(o)) for o in orders]

    # A threshold would make the label a function of the features: a model would score ~100%.
    assert any(p > 0.5 and y == 0 for p, y in pairs)
    assert any(p < 0.5 and y == 1 for p, y in pairs)


def test_share_of_eligible_orders_matches_the_documented_assumption():
    orders = OrderGenerator().recent_history(5000, TODAY)
    outcomes = [express_eligible(o) for o in orders]
    share = sum(outcomes) / len(outcomes)
    mean_probability = sum(eligibility_probability(o) for o in orders) / len(orders)

    # About 34% with ERP distributions (the notebook's data gives 79%): see the README.
    assert 0.30 < share < 0.39
    assert share == pytest.approx(mean_probability, abs=0.03)
