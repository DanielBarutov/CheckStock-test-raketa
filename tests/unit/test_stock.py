import pytest

import domain.fbs
import domain.movements
import domain.stock


def test_balance_rejects_reservation_greater_than_physical_stock() -> None:
    """Проверяет, что доменная модель отклоняет остаток с резервом больше наличия."""
    with pytest.raises(ValueError):
        domain.stock.Balance(on_hand=3, reserved=4)


def test_reservation_dispatch_consumes_only_the_reserved_units() -> None:
    """Проверяет, что отправка снимает резерв и физический остаток на одно количество."""
    balance = domain.stock.Balance(on_hand=10, reserved=7)
    remaining = balance.release(3, shipped=True)

    assert (remaining.on_hand, remaining.reserved, remaining.available) == (7, 4, 3)


def test_dispatched_reservation_cannot_be_cancelled() -> None:
    """Проверяет, что после отправки клиенту резерв закрыт для отмены."""
    with pytest.raises(domain.fbs.ReservationClosed):
        domain.fbs.finish_reservation(domain.movements.State.IN_TRANSIT, "cancel")
