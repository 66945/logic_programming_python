# type: ignore

import builtins
from predicate import *
from dataclasses import dataclass

# redefine len() to allow for non int returns
def _len(n):
    return n.__len__()
builtins.len = _len



@fact
class UnitTest:
    valid:     str
    test:      tuple
    name_real: str

UnitTest('yes', (), 'test1')
UnitTest('yes', (), 'test2')
UnitTest('no',  (), 'test3')
UnitTest('yes', (), 'test7')
UnitTest('no',  (), 'other')

@rule
def zero(a: int):
    assert a == 0

@rule
def add(a, b, c):
    assert a + b == c

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

@rule
def email(user: str, domain: str, tld: str, address: str):
    email_regex = \
        (RegChars(ALPHA_CHARS)
            | RegRepeat(RegChars(IDENTIFIER_CHARS))
            | RegNode('@')
            | RegChars(ALPHA_CHARS)
            | RegRepeat(RegChars(IDENTIFIER_CHARS))
            | RegOr(
                RegNode('.com'),
                RegNode('.net')))

    assert address == user + '@' + domain + '.' + tld
    assert regex_test(email_regex, address)


@rule
def length(string: str, length: int):
    assert len(string) == length

@fact
class Parent:
    child:  str
    parent: str

Parent('daniel', 'kathy')
Parent('daniel', 'micheal')
Parent('maggie', 'kathy')
Parent('maggie', 'micheal')

@rule
def sibling(a: str, b: str):
    T @ (
        y.parent == z.parent,

        a == y.child,
        b == z.child,
        a != b
    )


if __name__ == '__main__':
    repl(globals())
