# type: ignore

from __future__ import annotations

import builtins
from predicate import *
from dataclasses import dataclass

# redefine len() to allow for non int returns
def _len(n):
    return n.__len__()
builtins.len = _len



@fact
class UnitTest:
    valid:     str = 'test'
    test:      tuple
    name_real: str

UnitTest(valid = 'yes', test = (), name_real = 'test1')
UnitTest(valid = 'yes', test = (), name_real = 'test2')
UnitTest(valid = 'no',  test = (), name_real = 'test3')
UnitTest(valid = 'yes', test = (), name_real = 'test7')
UnitTest(valid = 'no',  test = (), name_real = 'other')

@rule
def zero(a: int):
    assert a == 0

@rule
def add(a, b, c):
    assert a + b == c

@rule
def add3(a, b, c, d):
    assert a + b + c == d

@rule
def I(a: int):
    ...

@rule
def unify(a, b):
    assert a == b

@rule
def validated(test: UnitTest, name: str):
    assert test.valid == 'yes'
    assert name       == test.name_real

@rule
def boolstr(b: bool, s: str):
    if b == True:
        assert s == 'yes'
    else:
        assert s == 'no'

email_regex = \
    (RegChars(ALPHA_CHARS)
        | RegRepeat(RegChars(IDENTIFIER_CHARS))
        | RegNode('@')
        | RegChars(ALPHA_CHARS)
        | RegRepeat(RegChars(IDENTIFIER_CHARS))
        | RegOr(
            RegNode('.com'),
            RegNode('.net')))

@rule
def email(user: str, domain: str, tld: str, address: str):
    assert address == user + '@' + domain + '.' + tld
    assert regex_test(email_regex, address)


@rule
def length(string: str, length: int):
    assert len(string) == length

@fact
class Parent:
    child:  str
    parent: str

Parent(child = 'daniel', parent = 'kathy')
Parent(child = 'daniel', parent = 'micheal')
Parent(child = 'maggie', parent = 'kathy')
Parent(child = 'maggie', parent = 'micheal')

@rule
def sibling(a: str, b: str):
    T @ (
        y.parent == z.parent,

        a == y.child,
        b == z.child,
        a != b
    )


@fact
class Human:
    x: str

@fact
class Dog:
    x: str

Human(x = 'socrates')
Dog(x = 'dogrates')

@rule
def mortal(thing_name: str):
    T @ (
        not isinstance(thing, Dog),
        thing_name == thing.x,
    )

@fact
class Arr:
    val:    int
    linked: Arr | None

Arr(0, Arr(1, Arr(2, Arr(3, None))))

@rule
def has(array: Arr, value: int):
    assert isinstance(array, Arr)
    assert array.val == value

if __name__ == '__main__':
    repl(globals())
