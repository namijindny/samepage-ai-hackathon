from __future__ import annotations

import re
from fastapi import HTTPException

from .engine import _money

FIELDS = ('price', 'deadline', 'scope')


def clean_terms(values: dict[str, str], *, require_all: bool = True) -> dict[str, str]:
    terms = {}
    for field in FIELDS:
        value = str(values.get(field, '')).strip()
        if not value and require_all:
            raise HTTPException(422, f'{field.title()} is required')
        if value:
            limit = 400 if field == 'scope' else 140
            if len(value) > limit:
                raise HTTPException(422, f'{field.title()} is too long')
            terms[field] = value
    if 'price' in terms:
        parsed = _money(terms['price'])
        if not parsed or parsed[1] < 0:
            raise HTTPException(422, 'Enter a valid amount with its currency, such as ₦120,000')
        symbol, amount = parsed
        terms['price'] = f'{symbol}{amount:,}'
    return terms


def changes_between(current: dict[str, str], suggested: dict[str, str]) -> list[dict[str, str]]:
    result = []
    for field in FIELDS:
        if field not in suggested:
            continue
        value = suggested[field].strip()
        if value.casefold() == str(current.get(field, '')).strip().casefold():
            continue
        if field == 'price':
            old = _money(str(current.get(field, '')))
            new = _money(value)
            if not old or not new or old[0] != new[0]:
                raise HTTPException(422, 'The currency cannot change in an amendment')
        result.append({'field': field, 'old_value': str(current.get(field, '')), 'new_value': value})
    if not result:
        raise HTTPException(422, 'Change at least one term to make a counteroffer')
    return result


def status(row, delivery=None) -> str:
    if row['declined_at']:
        return 'declined'
    if not row['a_confirmed']:
        return 'awaiting_initiator'
    if not row['b_confirmed']:
        return 'awaiting_recipient'
    if delivery:
        return {
            'submitted': 'awaiting_completion_review',
            'accepted': 'completed',
            'disputed': 'disputed',
        }.get(delivery['status'], 'in_progress')
    return 'in_progress'
