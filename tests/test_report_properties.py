"""Properties check exact arithmetic and historical-row replacement."""

from decimal import Decimal

from hypothesis import given
from hypothesis import HealthCheck
from hypothesis import settings
from hypothesis import strategies as st
from kokudaily.replica import bind_datasets
from kokudaily.replica import merge_history
from kokudaily.replica import read_rows

money = st.decimals(
    min_value="-1000000000000",
    max_value="1000000000000",
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@given(
    st.dictionaries(st.dates(), st.one_of(money, st.none())),
    st.dictionaries(st.dates(), st.one_of(money, st.none())),
)
def test_history_overlay_is_exact_idempotent_and_order_independent(
    old, current
):
    history = [{"date": day, "value": value} for day, value in old.items()]
    fresh = [{"date": day, "value": value} for day, value in current.items()]
    expected = dict(old, **{})
    expected.update(current)
    result = merge_history(history, fresh)
    assert {row["date"]: row["value"] for row in result} == expected
    assert [row["date"] for row in result] == sorted(expected)
    assert merge_history(result, fresh) == result
    assert (
        merge_history(list(reversed(history)), list(reversed(fresh))) == result
    )


@given(st.lists(st.one_of(money, st.none()), max_size=30))
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_sql_numeric_sum_preserves_decimal_and_null(pg, values):
    _, reader = pg
    sql, params = bind_datasets(
        "SELECT sum(amount) AS total FROM __amounts",
        {"__amounts": [{"amount": v} for v in values]},
        {"__amounts": "amount numeric(33, 2)"},
    )
    result = read_rows(reader, sql, params)
    present = [value for value in values if value is not None]
    expected = sum(present, Decimal(0)) if present else None
    assert result.rows == [{"total": expected}]
