from __future__ import annotations
from itertools  import islice, product
from typing     import Callable, Iterator

class DecisionTree:
    def __init__(self):
        self._trace  = []
        self._cursor = 0

    def iterate(self):
        self._cursor = 0

        while self._trace:
            current, options = self._trace[-1]
            current          = next(options)

            if current is None:
                self._trace.pop()
            else:
                self._trace[-1] = current, options
                return

    def decide(self, options: Iterator):
        route_top = len(self._trace) - 1

        if self.cursor is None             \
                or self.cursor > route_top \
                or len(self._trace) == 0:

            self._trace.append((next(options), options))

            self.cursor = None
            return self._trace[-1][0]

        self.cursor += 1
        return self._trace[self.cursor - 1][0]


# contains everything
class SolutionSpace:
    def __init__(self, space:set[SolutionSpace]|None=None):
        if space is None:
            self._domain = {Terms(), Integers(), Arrays()}
        else:
            self._domain = space

    def __contains__(self, item) -> bool:
        for region in self._domain:
            if item in region:
                return True

        return False

    def __iter__(self):
        def _I():
            for region in self._domain:
                for item in region:
                    yield item
        
        return _I()

    def __and__(self, other: SolutionSpace) -> SolutionSpace:
        new_space = set()

        for l, r in product(self._domain, other._domain):
            intersection = l & r
            if not intersection.empty():
                new_space.add(l & r)
        
        return SolutionSpace(new_space)

    def __or__(self, other):
        return SolutionSpace()

    def __xor__(self, other):
        return SolutionSpace()

    def empty(self):
        return self._domain == set()


class Terms(SolutionSpace):
    def __init__(self, *terms:object):
        if terms:
            self._domain = set(*terms)
            return

        self._domain = set()

        for predicate, facts in database.items():
            for fact in facts:
                self._domain.add(fact)

    def __contains__(self, item) -> bool:
        return item in self._domain

    def __iter__(self): # type: ignore
        return iter(self._domain)

    def __and__(self, other: SolutionSpace) -> SolutionSpace:
        if not isinstance(other, Terms):
            return SolutionSpace(set())
        
        reduced_terms = set()

        for term in self._domain:
            if term in other._domain:
                reduced_terms.add(term)

        return SolutionSpace(reduced_terms)


class Integers(SolutionSpace):
    def __init__(self, space: set[SolutionSpace] | None = None):
        self._domain = set()

class Arrays(SolutionSpace):
    def __init__(self, space: set[SolutionSpace] | None = None):
        self._domain = set()

class Strings(Arrays):
    def __init__(self, space: set[SolutionSpace] | None = None):
        self._domain = set()


# most of the logic should be contained in the proxy/domain layer,
# Variable should just be a name binding
class Proxy:
    proxy_guid = 0

    def __init__(self, lazy_left:Proxy|None = None, lazy_right:Proxy|None=None, op:Callable|None=None):
        self._guid = Proxy.proxy_guid
        Proxy.proxy_guid += 1

        self._lazy_left  = lazy_left
        self._lazy_right = lazy_right
        self._domain     = SolutionSpace(set())

        if (self._lazy_left or self._lazy_right) and not op:
            raise ValueError

        self._lazy_operation = op

        if not self._lazy_left and not self._lazy_right:
            self._domain = SolutionSpace()


    def collect(self, ctx: DecisionTree, value:object=None):
        if self._lazy_left:
            self._lazy_left.collect(ctx, value)
            value = self._lazy_operation(self._lazy_left._domain, value) # type: ignore

        if self._lazy_right:
            self._lazy_right.collect(ctx, value)
            self._domain = self._lazy_operation(self._lazy_right._domain, value) # type: ignore

        return self._domain


    def __hash__(self) -> int:
        return self._guid



class Variable:
    def __init__(self, ctx: DecisionTree, proxy=None):
        self._ctx  = ctx
        self.proxy = proxy or Proxy()

    # should function as a binding operation
    def __eq__(self, other) -> Variable: # type: ignore
        return Variable(self._ctx, Proxy(self.proxy, other, lambda: None))

    def __add__(self, other) -> Variable:
        return Variable(self._ctx, Proxy(self.proxy, other, lambda: None))

    def __bool__(self) -> bool:
        # TODO: add decision for True and False
        return True in self.proxy.collect(self._ctx)


# atoms vs terms vs predicates

definitions: dict[str, type] = { }
database:    dict[str, set]  = { }
rules:       dict[str, list] = { }

def query(name: str, members: list[str]):

    def _Q(*args, **kwargs):
        if name in definitions:
            _Fact = definitions[name]
            # TODO: allow variables in arguments for recursive functions
            is_query = False
            for item in [*args, *kwargs.values()]:
                if isinstance(item, Variable) or item == ...:
                    is_query = True
                    break

            if not is_query:
                return _Fact(*args, **kwargs)

        proxy         = Proxy()
        proxy._domain = SolutionSpace(set())

        if name in database:
            field_dict = {}
            for field, val in zip(members, args):
                field_dict[field] = val
            for field, val in kwargs.items():
                field_dict[field] = val

            # search for item and return Variable
            matching = set()
            for fact in database[name]:
                matches = True

                for field, val in field_dict.items():
                    if not hasattr(fact, field):
                        matches = False
                        break

                    if not isinstance(val, Variable) and val != ... and getattr(fact, field) != val:
                        matches = False
                        break

                    if isinstance(val, Variable) and getattr(fact, field) not in val.proxy._domain:
                        matches = False
                        break

                if matches:
                    matching.add(fact)

            proxy._domain = Terms(matching)
        
        if name in rules:
            for rule in rules[name]:
                solve(rule, args, kwargs)

        return Variable(DecisionTree(), proxy)
    return _Q


def solve(rule: Callable, args: tuple, kwargs: dict):
    while True:
        try:
            rule(*args, **kwargs)

        except AssertionError:
            raise

        except Exception:
            raise


def predicate(clazz: type) -> Callable:
    global database
    global rules

    name = clazz.__name__

    members = {
        k: None
            for k in clazz.__annotations__
    }
    members |= {
        k: v
            for k, v in vars(clazz).items()
            if not k.startswith('__')
    }

    class _Fact:
        def __init__(self, *args, **kwargs):
            for arg, val in members.items():
                if type(val) == list: val = tuple(val)

                setattr(self, arg, val)

            for arg, val in zip(members, args):
                if type(val) == list: val = tuple(val)

                setattr(self, arg, val)

            for arg, val in kwargs.items():
                if arg not in members: raise TypeError
                if type(val) == list:  val = tuple(val)

                setattr(self, arg, val)

            database.setdefault(name, set()) 
            database[name].add(self)


        def __repr__(self) -> str:
            return f'{name}[ {", ".join([str(getattr(self, k)) for k in members])} ]'

    definitions[name] = _Fact
    return query(name, list(members.keys()))


def rule(fn: Callable) -> Callable:
    name = fn.__name__

    rules.setdefault(name, [])
    rules[name].append(fn)

    return query(name, list(fn.__annotations__.keys()))