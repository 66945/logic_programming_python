from __future__ import annotations
import inspect
import itertools
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator

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

    def push(self, options: Options):
        self.decision_route.append(options)

    def current_choice(self, options: Options):
        route_top = len(self.decision_route) - 1

        if self.cursor is None              \
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

    def __xor__(self, other):
        new_terms   = self._terms ^ other._terms
        new_numeric = []
        if other._numeric != []:
            new_numeric = other._numeric
        elif self._numeric != []:
            new_numeric = self._numeric
        return Domain(new_terms, new_numeric)

    def empty(self) -> bool:
        return self._terms == set() \
            and self._numeric == [] \
            and self._string  == None

term_types = []


class Capture:
    uid = 0

    def __init__(self, domain: Domain):
        self.domain = domain

        self._uid = Capture.uid
        Capture.uid += 1

    def __hash__(self) -> int:
        return self._uid

class LazyCapture:
    def __init__(self, left: Capture, right: Capture | object, pick_left, pick_right):
        self._left  = left
        self._right = right

        self._pick_first = pick_left
        self._pick_last  = pick_right

    def select(self, val):
        if not isinstance(self._right, Capture):
            self._left.domain = self._pick_last(val, self._right)

        else:
            self._left.domain &= self._pick_first(val)
            assert self._left.domain

            current = trace.current_choice(Options('select', iter(self._left.domain)))
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
        return Domain(set(), numeric=[range(val)], string=None)
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

            for v in globe.values():
                if type(v) in term_types:
                    domain_set.add(v)
            
            domain = Domain(domain_set)

        self.name            = name
        self._capture        = Capture(domain)
        self._initial_domain = domain

    def __eq__(self, value: object) -> bool:
        is_binding = type(value) == Variable
        current    = trace.current_choice(Options('__eq__', iter([True, False])))

        if not is_binding:
            if current:
                if type(self._capture) == LazyCapture:
                    self._capture.select(value)
                    return True

                self.restrict({value})

                assert self._capture.domain
                return True

            else:
                if type(self._capture) == LazyCapture:
                    return False

                self.exclude({value})
                assert self._capture.domain
                return False

        else:
            if current:
                intersection = self._capture.domain & value._capture.domain
                assert intersection

                bound = Capture(intersection)
                self._capture  = bound
                value._capture = bound

                return True
            else:
                # TODO
                return False

    def __add__(self, other):
        if type(other) == Variable:
            other = other._capture
        
        lazy = LazyCapture(
            left  = self._capture,
            right = other,

            pick_left  = add_left,
            pick_right = add_right
        )

        add_var = Variable('__add__', self._capture.domain)
        add_var._capture = lazy

        return add_var

    def __radd__(self, other):
        return self.__add__(other)

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


class Predicate:
    def __init__(self):
        self._facts = set()

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
    return Variable('unique')


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

    def f(*args):
        args         = list(args)
        call_count   = 0
        start_cursor = trace.cursor

        if fn_name in p._predicates:
            for tup in p._predicates[fn_name](*args):
                out_fmt = tuple([f'{fn_params[i][0]} = {o}' for i, o in enumerate(tup)])
                yield out_fmt

        while True:
            if fn_name in p._predicates:
                for tup in p._predicates[fn_name](*args):
                    out_fmt = tuple([f'{fn_params[i][0]} = {o}' for i, o in enumerate(tup)])
                    yield out_fmt

            args_variable = []
            variables     = []

            for i, arg in enumerate(args):
                if type(arg) == Variable:
                    args_variable.append(arg)
                    variables.append(arg)

                elif arg == ...:
                    param_name, param = fn_params[i]
                    annotation        = param.annotation

                    new_domain = None
                    domain_set = set()

                    if annotation == bool:
                        new_domain = Domain({True, False}, [], string=None)

                    elif annotation == int:
                        new_domain = Domain(set(), string=None)

                    elif annotation == str:
                        new_domain = Domain(set(), [], ...)

                    elif annotation in [list, dict]:
                        ...

                    else:
                        for v in globe.values():
                            if type(v) == annotation:
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

                # cross product the results, but ensure that bound variables
                # don't get applied to themselves.
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
                    out_fmt   = tuple([f'{fn_params[i][0]} = {o}' for i, o in enumerate(out_deref)])
                    yield out_fmt

            except AssertionError as e:
                continue

            except:
                raise

            finally:
                trace.clear()
                if len(trace.decision_route) == start_cursor:
                    trace.cursor = start_cursor
                    return

    return f






# =================================================================




def repl():
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
                exec(code, globals=globals(), locals=globals())
            elif query == '':
                print('\033[A\033[2K')

            else:
                valid = False
                for i in eval(query, globals=globals(), locals=globals()):
                    valid = True
                    fmt   = '\n │  '.join([str(a) for a in i])
                    if input(f' │  {fmt} '):
                        break
                    print(' │')

                print(' ╰─────── ' + 'yes' if valid else 'no')
                print()