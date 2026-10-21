"""Properties check exact arithmetic and historical-row replacement."""


from hypothesis import given
from hypothesis import HealthCheck
from hypothesis import settings
from hypothesis import strategies as st
from kokudaily.staging import Store
from sqlalchemy import text

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
    with Store() as store:
        store.create("history", {"date": "date", "value": "numeric(33, 2)"})
        store.overlay("history", history)
        store.overlay("history", fresh)

        def read():
            return list(
                store.select(
                    "SELECT * FROM history ORDER BY date",
                    store.schemas["history"],
                )[1]
            )

        result = read()
        assert {row["date"]: row["value"] for row in result} == expected
        assert [row["date"] for row in result] == sorted(expected)
        store.overlay("history", fresh)
        assert read() == result
        store.overlay("history", list(reversed(fresh)))
        assert read() == result


@given(st.lists(st.one_of(money, st.none()), max_size=30))
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_sql_numeric_sum_preserves_decimal_and_null(pg, values):
    _, reader = pg
    with reader.connect() as con:
        expected = con.execute(
            text(
                "SELECT SUM(value) FROM unnest(CAST(:values AS numeric[])) AS value"
            ),
            {"values": values},
        ).scalar_one()
    with Store() as store:
        store.create("amounts", {"amount": "numeric(33, 2)"})
        with store.attempt():
            store.insert("amounts", ({"amount": value} for value in values))
        _, rows = store.select(
            "SELECT decimal_sum(amount) AS total FROM amounts",
            {"total": "numeric"},
        )
        assert list(rows) == [{"total": expected}]
