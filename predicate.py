from __future__ import annotations
import inspect
import itertools
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, Hashable
import re

if True:
    def dprint(*args):
        ...
else:
    def dprint(*args):
        print(*args)

def lazy_product(*args):
    if not args:
        yield ()
        return

    for item in args[0]:
        for rproduct in lazy_product(*args[1:]):
            yield (item, *rproduct)


@dataclass
class Options:
    capture:   str
    available: Iterator
    current:   object = None

class BackTrace:
    def __init__(self):
        self.decision_route: list[Options] = []
        self.cursor:         int | None    = 0

    def clear(self):
        while self.decision_route:
            current = next(self.decision_route[-1].available, None)
            if current is None:
                self.decision_route.pop()
            else:
                self.decision_route[-1].current = current
                return

    def current_choice(self, options: Options):
        route_top = len(self.decision_route) - 1

        if self.cursor is None             \
                or self.cursor > route_top \
                or len(self.decision_route) == 0:

            self.decision_route.append(options)
            options.current = next(options.available)

            self.cursor = None
            return options.current

        self.cursor += 1
        return self.decision_route[self.cursor - 1].current

trace = BackTrace()

class RegNode:
    def __init__(self, s: str):
        self._string = s
        self._next   = None

    def __or__(self, other):
        if not isinstance(other, RegNode):
            raise TypeError

        if not self._next:
            self._next = other
        else:
            self._next.__or__(other)

        return self

    def test(self, s: str) -> bool:
        if s.startswith(self._string):
            if self._next:
                return self._next.test(s[len(self._string):])
            return True
        return False

    def generate(self):
        if not self._next:
            yield self._string
            return

        for out in self._next.generate():
            yield self._string + out

class RegChars(RegNode):
    def __init__(self, chars):
        self._next = None
        self._chars = chars
    def test(self, s: str):
        if s and s[0] in self._chars:
            if self._next:
                return self._next.test(s[1:])
            return True
        return False

    def generate(self):
        if not self._next:
            for c in self._chars:
                yield c
            return

        for out in self._next.generate(): # type: ignore
            for c in self._chars:
                yield c + out

class RegWildcard(RegNode):
    def __init__(self):
        self._next = None

    def test(self, s: str) -> bool:
        if s and self._next:
            return self._next.test(s[1:])
        return True

    def generate(self):
        if not self._next:
            yield '*'
        
        for out in self._next.generate(): # type: ignore
            yield '*' + out

class RegRepeat(RegNode):
    def __init__(self, node: RegNode, b=False):
        self._next = None
        self._node = node
        self._node.__or__(self)
        self._running = False

        self._required_first = b

    def test(self, s: str):
        if not s:
            return self._next == None

        if self._next:
            if self._next.test(s):
                return True

        return self._node.test(s)

    def generate(self):
        if self._running:
            yield ''
            return

        self._running = True

        if not self._next:
            for i in range(10):
                for out in itertools.permutations(self._node.generate(), i):
                    yield ''.join(out)
            self._running = False
            return

        for out in self._next.generate(): # type: ignore
            for i in range(10):
                for selfout in itertools.permutations(self._node.generate(), i):
                    yield ''.join(selfout) + out

        self._running = False

class RegOr(RegNode):
    def __init__(self, a: RegNode, b: RegNode):
        self._next = None
        self._option_a = a
        self._option_b = b

        self._option_a._next = self._next
        self._option_b._next = self._next

    def test(self, s: str):
        return self._option_a.test(s) or self._option_b.test(s)

    def generate(self):
        yield from self._option_a.generate()
        yield from self._option_b.generate()


ALPHA_CHARS      = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
IDENTIFIER_CHARS = ALPHA_CHARS + '_0123456789.'

def regex_test(regex: RegNode, string: Variable | str) -> bool:
    if type(string) not in [Variable, str]:
        raise TypeError

    if isinstance(string, str):
        return regex.test(string)

    current = trace.current_choice(Options('regex_test', iter([True, False])))
    if current:
        assert string._capture.domain._string is not None

        if string._capture.domain._string == ...:
            string._capture.domain._string = regex

        elif type(string._capture.domain._string) == list:
            string._capture.domain._string = [
                s for s in string._capture.domain._string
                    if regex.test(s)
            ]
            assert string._capture.domain
        
        else:
            ...

        return True
    else:
        return False


class Domain:
    def __init__(
            self,
            terms: set,
            numeric = [range(0, 100)],
            string: ellipsis|list|RegNode|None=...,
    ):
        if type(terms) == dict:
            raise TypeError

        self._terms   = terms
        self._numeric = numeric
        self._string  = string

    def __contains__(self, item: object) -> bool:
        if type(item) == int:
            for n in self._numeric:
                if n == item: return True

                return item in n
        
        elif type(item) == str:
            return self._string == ... or item == self._string

        elif item in self._terms:
            return True
        
        return False

    def __iter__(self):
        def domain_iter():
            for t in self._terms:
                yield t

            for n in self._numeric:
                if type(n) == int:
                    yield n
                
                else:
                    yield from n

            if self._string == ...:
                yield '<class str>'
            elif type(self._string) == list:
                yield from self._string
            elif isinstance(self._string, RegNode):
                yield from self._string.generate()

        return domain_iter()

    def __len__(self):
        return len(self._terms)

    def __bool__(self):
        return not self.empty()

    def __and__(self, other: Domain):
        new_terms   = self._terms & other._terms
        new_numeric = []
        new_string  = None

        idx     = 0
        idx_new = 0

        # intersection of two ordered lists of ranges and numbers
        while idx < len(self._numeric) and idx_new < len(other._numeric):
            n_self  = self._numeric[idx]
            n_other = other._numeric[idx_new]

            if n_self == n_other:
                new_numeric.append(n_self)
                idx     += 1
                idx_new += 1

            elif (type(n_self), type(n_other)) == (int, range):
                if n_self in n_other:
                    new_numeric.append(n_self)
                    idx += 1
                elif n_self < n_other.stop:
                    idx += 1
                else:
                    idx_new += 1

            elif (type(n_self), type(n_other)) == (range, int):
                if n_other in n_self:
                    new_numeric.append(n_other)
                    idx_new += 1
                elif n_other < n_self.stop:
                    idx_new += 1
                else:
                    idx += 1

            elif (type(n_self), type(n_other)) == (range, range):
                if n_self.start <= n_other.start:
                    # _____
                    #       _____
                    if n_self.stop <= n_other.start:
                        idx += 1

                    # __***
                    #   ***__
                    elif n_self.stop <= n_other.stop:
                        new_numeric.append(range(n_other.start, n_self.stop))
                        idx += 1
                    
                    # __***__
                    #   ***
                    else:
                        new_numeric.append(n_other)
                        idx_new += 1
                
                else:
                    #       _____
                    # _____
                    if n_other.stop <= n_self.start:
                        idx_new += 1

                    #   ***__
                    # __***
                    elif n_other.stop <= n_self.stop:
                        new_numeric.append(range(n_self.start, n_other.stop))
                        idx_new += 1
                    
                    #   ***
                    # __***__
                    else:
                        new_numeric.append(n_self)
                        idx += 1

        if self._string == other._string:
            new_string = self._string
        elif self._string is None or other._string is None:
            new_string = None
        elif self._string == ...:
            new_string = other._string
        elif other._string == ...:
            new_string = self._string

        elif (type(self._string), type(other._string)) == (list, list):
            new_string = list(set(self._string) & set(other._string)) or None # type: ignore

        elif (type(self._string), type(other._string)) == (RegNode, list):
            new_string = [
                s for s in other._string    # type: ignore
                    if self._string.test(s) # type: ignore
            ] or None

        elif (type(self._string), type(other._string)) == (list, RegNode):
            new_string = [
                s for s in self._string    # type: ignore
                    if other._string.test(s) # type: ignore
            ] or None

        return Domain(new_terms, new_numeric, new_string)

    # FIXME: xor should work as a reflection of and
    def __xor__(self, other):
        new_terms   = self._terms ^ other._terms
        new_numeric = []
        if other._numeric != []:
            new_numeric = other._numeric
        elif self._numeric != []:
            new_numeric = self._numeric
        return Domain(new_terms, new_numeric, string=self._string)

    def empty(self) -> bool:
        return self._terms == set() \
            and self._numeric == [] \
            and self._string  == None


class Capture:
    uid = 0

    def __init__(self, domain: Domain):
        self.domain = domain

        self._uid = Capture.uid
        Capture.uid += 1

    def __hash__(self) -> int:
        return self._uid

# TODO: maybe this should be LazyDomain
class LazyCapture:
    def __init__(self, left: Capture, right: Capture | object, pick_left, pick_right):
        self._left  = left
        self._right = right

        self._pick_first = pick_left
        self._pick_last  = pick_right

    def select(self, val):
        lazy_left  = None
        lazy_right = None

        if isinstance(self._left, LazyCapture):
            lazy_left  = self._left
            self._left = var()._capture

#        if isinstance(self._right, LazyCapture):
#            self._right = self._right.select(val)

        if not isinstance(self._right, Capture):
            self._left.domain = self._pick_last(val, self._right)

        else:
            self._left.domain &= self._pick_first(val)
            assert self._left.domain

            current = trace.current_choice(Options('select', iter(self._left.domain)))
            if lazy_left:
                lazy_left.select(current)

            if type(current) == int:
                self._left.domain = Domain(set(), numeric=[current], string=None)
            elif type(current) == str:
                self._left.domain = Domain(set(), numeric=[], string=[current])
            else:
                self._left.domain = Domain({current}, numeric=[], string=None)

            self._right.domain &= self._pick_last(val, current)
            assert self._right.domain


def add_left(val):
    if type(val) == int:
        return Domain(set(), numeric=[range(val + 1)], string=None)
    elif type(val) == str:
        strings = [val[:i] for i in range(len(val))]
        return Domain(set(), numeric=[], string=[*strings])

def add_right(val, left):
    if type(val) == int:
        return Domain(set(), numeric=[val - left], string=None)
    elif type(val) == str:
        return Domain(set(), numeric=[], string=[val[len(left):]])

class Variable:
    def __init__(self, name: str, domain: Domain|None=None):
        if domain == None:
            domain_set = { True, False }

            for v in fact_set:
                domain_set.add(v)
            
            domain = Domain(domain_set)

        self.name              = name
        self._capture: Capture = Capture(domain)
        self._initial_domain   = domain

    def __eq__(self, value: object) -> bool:
        is_binding = type(value) == Variable

        if not is_binding:
            if type(self._capture) == LazyCapture:
                self._capture.select(value)
                return True

            old_domain = self._capture.domain
            self.restrict({value})
            if not bool(self._capture.domain):
                self._capture.domain = old_domain
                return False
            return True

        else:
            intersection = self._capture.domain & value._capture.domain

            if bool(intersection):
                bound = Capture(intersection)
                self._capture  = bound
                value._capture = bound
                return True
            return False

    def __matmul__(self, other):
        assert self == other
        return True
    def __rmatmul__(self, other):
        return self @ other

    def __add__(self, other):
        if type(other) == Variable:
            other = other._capture

        lazy = LazyCapture(
            left  = self._capture,
            right = other,

            pick_left  = add_left,
            pick_right = add_right
        )

        add_var = Variable('__add__', None)
        add_var._capture = lazy # type: ignore

        return add_var

    def __radd__(self, other):
        return self.__add__(other)

    def __len__(self):
        self._capture.domain = Domain(
            terms   = set(),
            numeric = [],
            string  = self._capture.domain._string
        )
        assert self._capture.domain

        lazy = LazyCapture(
            left  = self._capture,
            right = None,

            pick_left  = None,
            pick_right = (lambda val, _: Domain(set(), [], ['*' * val])),
        )

        len_var = Variable('__len__', Domain(set()))
        len_var._capture = lazy # type: ignore

        return len_var

    def __str__(self) -> str:
        # uh oh
        current = trace.current_choice(Options(self.name, iter(self._capture.domain)))

        self.restrict({current})
        return str(current)

    def __repr__(self):
        return ' --- '

    def __getattr__(self, name: str):
        self._capture.domain._numeric = []

        current = trace.current_choice(Options(self.name, iter([
            i for i in self._capture.domain._terms if hasattr(i, name)
        ])))

        self.restrict({current})
        attr = Variable(f'{self.name}_{name}')
        attr.restrict({getattr(current, name)})

        assert self._capture.domain
        assert attr._capture.domain

        return attr


    def clear(self):
        self._capture = Capture(self._initial_domain)

    def restrict(self, restriction: set[object]) -> None:
        strings = [
            s for s in restriction
                if type(s) == str
        ] or None

        new_domain = Domain(
            terms = {
                t for t in restriction
                    if type(t) not in [int, range, str]
            },
            numeric = [
                n for n in restriction
                    if type(n) in [int, range]
            ],
            string = strings
        )
        self._capture.domain = self._capture.domain & new_domain

    def exclude(self, exclusion: set[object]) -> None:
        new_domain = Domain(
            terms = {
                t for t in exclusion
                    if type(t) not in [int, range]
            },
            numeric = [
                n for n in exclusion
                    if type(n) in [int, range]
            ],
        )
        self._capture.domain = self._capture.domain ^ new_domain


# domain vs seperate class?
class Output:
    def __init__(self, outputs):
        self._outputs_condensed = outputs

    def __iter__(self) -> Iterator:
        def I():
            for out in lazy_product(*self._outputs_condensed):
                out_deref = tuple([out[o.cap] if type(o) == Ref else o for o in out])
                yield out_deref
        
        return I()

    def __bool__(self) -> bool:
        return False


class Predicate:
    def __init__(self):
        self._facts = set()

    # TODO: restructure return to work better for Output class
    def __call__(self, *key) -> set:
        key           = tuple(key)
        possibilities = set()

        for fact in self._facts:
            possible = True

            for i, term in enumerate(fact):
                variable = type(key[i]) == Variable
                choice   = variable or key[i] == ...

                if not choice and key[i] != term:
                    possible = False
                    break
                elif variable and term not in key[i]._capture.domain:
                    possible = False
                    break

            if not possible:
                continue

            possibilities.add(fact)

        if possibilities:
            for i, term in enumerate(key):
                if type(term) == Variable:
                    restriction   = trace.current_choice(Options(term.name, iter([j[i] for j in possibilities])))
                    possibilities = {
                        k for k in possibilities
                            if k[i] == restriction
                    }
                    term.restrict({restriction})

        return possibilities

    def __getitem__(self, key):
        if type(key) != tuple:
            key = (key,)

        if self._facts:
            if len(key) != len(list(self._facts)[0]):
                raise TypeError('mismatched fact term #')

        self._facts.add(key)

        return key

def var():
    return Variable('__var__')


class PredicatesContainer:
    def __init__(self):
        self._predicates = {}

    def __getattr__(self, name):
        self._predicates.setdefault(name, Predicate())
        return self._predicates[name]

p = PredicatesContainer()

def setup_predicates(fn):
    g = inspect.currentframe().f_back.f_globals # type: ignore
    while True:
        try:
            fn()
        except NameError as ne:
            dprint(f'  added predicate `{ne.name}`')
            g[ne.name] = Predicate() # type: ignore
            continue
        break

fact_set = set()

class FactMeta(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        if type(instance) == Variable:
            current = trace.current_choice(Options('instance check', iter([True, False])))

            if current:
                subset = {
                    t
                        for t in instance._capture.domain._terms
                        if type(t).__name__ == cls.__name__
                }

                instance.restrict(subset)
                return bool(instance._capture.domain)
            else:
                subset = {
                    t
                        for t in instance._capture.domain._terms
                        if type(t).__name__ == cls.__name__
                }

                instance._capture.domain._terms ^= subset
                return not bool(instance._capture.domain)

        return False


def fact(clazz: type):
    global fact_set

    members = {
        k: None
            for k in clazz.__annotations__
    }
    members |= {
        k: v
            for k, v in vars(clazz).items()
            if not k.startswith('__')
    }

    class _AsFact(metaclass=FactMeta):
        fact_guid = 0

        def __init__(self, *args, **kwargs):
            self.id = _AsFact.fact_guid
            _AsFact.fact_guid += 1

            for arg, val in members.items():
                if type(val) == list: val = tuple(val)

                setattr(self, arg, val)

            for arg, val in zip(members.keys(), args):
                if type(val) == list: val = tuple(val)

                setattr(self, arg, val)

            for arg, val in kwargs.items():
                if arg not in members: raise TypeError
                if type(val) == list:  val = tuple(val)

                setattr(self, arg, val)
            
            fact_set.add(self)
        
        def __repr__(self) -> str:
            return f'{_AsFact.__name__}[ {", ".join([str(getattr(self, k)) for k in members])} ]'

    _AsFact.__name__ = clazz.__name__
    return _AsFact


globe = {}
def use(g: dict):
    global globe
    globe = g

@dataclass
class Ref:
    cap: int

def rule(fn) -> Callable:
    signature = inspect.signature(fn)
    fn_name   = fn.__name__
    fn_params = list(signature.parameters.items())

    # as a class?
    def f(*args):
        args         = list(args)
        call_count   = 0
        start_cursor = trace.cursor

        temporary_names = set()

        while True:
            args_variable = []
            variables     = []

            name_error = False

            for i, arg in enumerate(args):
                if type(arg) == Variable:
                    args_variable.append(arg)
                    variables.append(arg)

                elif arg == ...:
                    param_name, param = fn_params[i]
                    annotation        = str(param.annotation)

                    new_domain = None
                    domain_set = set()

                    if annotation == 'bool':
                        new_domain = Domain({True, False}, [], string=None)

                    elif annotation == 'int':
                        new_domain = Domain(set(), string=None)

                    elif annotation == 'str':
                        new_domain = Domain(set(), [], ...)

                    elif annotation in ['list', 'dict']:
                        ...

                    else:
                        for v in fact_set:
                            if isinstance(v, Hashable):
                                domain_set.add(v)
                        new_domain = Domain(domain_set)

                    cap = Variable(param_name, new_domain)
                    args_variable.append(cap)
                    variables.append(cap)

                else:
                    args_variable.append(arg)

            trace.cursor = start_cursor

            try:
                call_count += 1
                fn(*args_variable)

                outputs  = []
                captures = {}

                for i, arg in enumerate(args_variable):
                    if type(arg) == Variable:
                        if hash(arg._capture) in captures:
                            outputs.append([Ref(captures[hash(arg._capture)])])
                        else:
                            captures[hash(arg._capture)] = i
                            outputs.append(arg._capture.domain)
                    else:
                        outputs.append([arg])

                for out in lazy_product(*outputs):
                    out_deref = tuple([out[o.cap] if type(o) == Ref else o for o in out])
                    yield out_deref

            except NameError as e:
                temporary_names.add(e.name)
                trace.cursor         = start_cursor
                trace.decision_route = []
                name_error           = True
                continue

            except AssertionError as e:
                continue

            except:
                raise

            finally:
                trace.clear()
                for n in temporary_names:
                    globe[n] = var()

                if not name_error and len(trace.decision_route) == start_cursor:
                    break

        trace.cursor = start_cursor
        for n in temporary_names:
            del globe[n]

    return f

class AssertSyntax:
    def __matmul__(self, other):
        for cond in other:
            assert cond
        return True

T = AssertSyntax()


# =================================================================


def repl(_globals):
    use(_globals)

    print('\033[2J\033[H')
    query = ''
    while query != 'exit':
        query = input('?- ')
        if query != 'exit':
            if query == ';':
                print('\033[A\033[2K')
                query = input('\033[A >  ')

                code  = ''
                while query != '.':
                    code += '\n' + query
                    query = input(' >  ')

                print('\033[A\033[2K')
                exec(code, _globals, _globals)

            elif query == '':
                print('\033[A\033[2K')

            elif ':-' in query:
                code = re.sub(r'([a-zA-Z_])+\s*\((.*)\)\s*:-(.*)', r'\1 = rule(lambda \2: T @ (\3,))', query)
                exec(code, _globals, {})

            else:
                valid = False
                for i in eval(query, _globals, {}):
                    valid = True
                    fmt   = '\n │  '.join([str(a) for a in i])
                    if input(f' │  {fmt} '):
                        trace.decision_route = []
                        trace.cursor         = 0
                        break
                    print(' │')

                print(' ╰─────── ' + 'yes' if valid else 'no')
                print()
