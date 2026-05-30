from predicate   import *
from dataclasses import dataclass

@dataclass(frozen=True)
class UnitTest:
    valid: str
    test:  tuple
    name_real: str

term_types.append(UnitTest)

test1 = UnitTest('yes', (), 'test1')
test2 = UnitTest('yes', (), 'test2')
test3 = UnitTest('no',  (), 'test3')
test4 = UnitTest('yes', (), 'test7')
test5 = UnitTest('no',  (), 'other')

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


if __name__ == '__main__':
    use(globals())
    repl()