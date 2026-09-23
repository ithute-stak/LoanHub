from services.cdas_daily_intelligence import classify_daily_collection_action


def test_daily_collection_action_requires_existing_balance_and_positive_capacity():
    assert (
        classify_daily_collection_action(outstanding=5000, affordability=750)
        == "READY_FOR_COLLECTION_REVIEW"
    )


def test_daily_collection_action_monitors_when_no_capacity():
    assert (
        classify_daily_collection_action(outstanding=5000, affordability=0)
        == "MONITOR_NO_CAPACITY"
    )
    assert (
        classify_daily_collection_action(outstanding=5000, affordability=-20)
        == "MONITOR_NO_CAPACITY"
    )


def test_daily_collection_action_does_nothing_without_existing_debt():
    assert (
        classify_daily_collection_action(outstanding=0, affordability=1000)
        == "NO_OUTSTANDING_BALANCE"
    )
    assert (
        classify_daily_collection_action(outstanding=-1, affordability=1000)
        == "NO_OUTSTANDING_BALANCE"
    )
