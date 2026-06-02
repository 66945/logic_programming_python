# type: ignore

from __future__ import annotations
from logic import *

@predicate
class human:
    name: str

@rule
def mortal(name: str):
    assert human(name)

human('socrates')

@rule
def human(name: str): pass


@predicate
class arr:
    head: object
    tail: object

arr(0, arr(1, arr(2, arr(3, None))))
arr(0, arr(2, arr(2, arr(3, None))))

for item in arr(0, ...).proxy._domain:
    print(item)