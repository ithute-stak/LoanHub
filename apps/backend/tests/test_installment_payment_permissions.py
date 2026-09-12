from core.access_control import CASHIER_ROLES, LENDING_ROLES
from routers.loans import INSTALLMENT_PAYMENT_ROLES


def test_installment_payment_roles_include_cashier_and_lending_roles():
    assert CASHIER_ROLES <= INSTALLMENT_PAYMENT_ROLES
    assert LENDING_ROLES <= INSTALLMENT_PAYMENT_ROLES
