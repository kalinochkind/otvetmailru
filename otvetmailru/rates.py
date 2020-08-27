from typing import List

from .models import Rate

_RATES = [
    # name, min_points, min_kpd
    ('Новичок', 0, 0),
    ('Ученик', 1, 0),
    ('Знаток', 250, 0),
    ('Профи', 500, 0),
    ('Мастер', 1000, 0),
    ('Гуру', 2500, 0),
    ('Мыслитель', 5000, 0),
    ('Мудрец', 10000, 0),
    ('Просветленный', 20000, 0),
    ('Оракул', 50000, 0),
    ('Гений', 50000, 25),
    ('Искусственный Интеллект', 100000, 0),
    ('Высший разум', 100000, 30),
]

rates: List[Rate] = []


def _fill_rates():
    for name, min_points, min_kpd in _RATES[::-1]:
        # noinspection PyUnboundLocalVariable
        next = min([r for r in rates if r.min_points > rate.min_points],
                   key=lambda r: (r.min_points, r.min_kpd), default=None)
        next_by_kpd = min([r for r in rates if r.min_points == rate.min_points and r.min_kpd > rate.min_kpd],
                          key=lambda r: (r.min_points, r.min_kpd), default=None)
        rate = Rate(name=name, min_points=min_points, min_kpd=min_kpd, next=next, next_by_kpd=next_by_kpd)
        rates.append(rate)
    rates.reverse()


_fill_rates()

_by_name = {r.name.lower(): r for r in rates}


def by_user_stats(points: int, kpd: float) -> Rate:
    """Get a rate by points and kpd"""
    return max([r for r in rates if r.min_points <= points and r.min_kpd <= kpd],
               key=lambda r: (r.min_points, r.min_kpd))


def by_name(name: str) -> Rate:
    """Get a rate by name, case-insensitive"""
    return _by_name[name.lower()]
