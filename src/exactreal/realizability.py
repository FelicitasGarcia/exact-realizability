"""Standard and exact realizability, minimal unrealizable sets of goals, and HOA export."""
from collections import deque
from dataclasses import dataclass
from itertools import combinations

from .hoa import load, valuations

# ----------------------------------------------------------------------------
# Goals and checks
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Goal:
    name: str
    hoa: str           # HOA text or path to a .hoa file
    cstr: frozenset    # propositions the goal intends to constrain

    def __repr__(self):
        a = load(self.hoa)
        return (f'{self.name}: {a.n_states} states, AP {a.ap_names}  '
                f'[Cstr = {{{", ".join(sorted(self.cstr))}}}]')


def goal(name, hoa, cstr=None):
    """A goal given as an automaton. cstr defaults to the HOA's controllable-AP header."""
    if cstr is None:
        cstr = load(hoa).controllable
        if cstr is None:
            raise ValueError(f'{name}: give cstr, or export the HOA with a controllable-AP header')
    if isinstance(cstr, str):
        cstr = cstr.replace(',', ' ').split()
    return Goal(name, hoa, frozenset(cstr))


def _fmt(vals, universe):
    return '{' + ', '.join(n if n in vals else '!' + n for n in sorted(universe)) + '}'


def _explore(automata, IV, OV):
    """Product of the automata over the alphabet. Prefixes the conjunction cannot extend forever
    are dropped: each automaton accepts some continuation, but they may not agree on one."""
    init = tuple(a.init for a in automata)
    succ, parent, order, queue = {}, {init: None}, [init], deque([init])
    while queue:
        q = queue.popleft()
        succ[q] = {}
        for i in IV:
            for o in OV:
                L, nxt = i | o, []
                for a, s in zip(automata, q):
                    r = a.next(s, L)
                    if r is None:
                        break
                    nxt.append(r)
                else:
                    nxt = tuple(nxt)
                    succ[q][(i, o)] = nxt
                    if nxt not in parent:
                        parent[nxt] = (q, (i, o))
                        order.append(nxt)
                        queue.append(nxt)
    live, changed = set(succ), True
    while changed:
        changed = False
        for q in list(live):
            if not any(r in live for r in succ[q].values()):
                live.discard(q)
                changed = True
    if init not in live:
        return None
    succ = {q: {k: r for k, r in succ[q].items() if r in live} for q in live}
    return {'init': init, 'succ': succ, 'parent': parent, 'order': [q for q in order if q in live]}


@dataclass
class Result:
    goals: list
    inputs: list
    outputs: list
    standard: bool
    exact: bool
    witness: str = ''
    semantics: str = 'moore'

    def __repr__(self):
        names = ', '.join(g.name for g in self.goals) or '(no goals)'
        lines = [f'Goals {names}  ({self.semantics} steps)',
                 f'  inputs  (env)  : {self.inputs}',
                 f'  outputs (actor): {self.outputs}',
                 f'  standard realizable: {self.standard}',
                 f'  exactly realizable : {self.exact}']
        if self.witness:
            lines.append('  not exactly realizable, conflict-inducing condition:\n' + self.witness)
        return '\n'.join(lines)


SEMANTICS = ('moore', 'mealy')


def check(goals, dom=(), semantics='moore'):
    """Check standard and exact realizability of a set of goals within a domain theory.

    goals     : list of Goal. The actor controls the union of their Cstr; everything else is input.
    dom       : list of HOA automata (text or paths) for the domain properties. Never assumptions.
    semantics : 'moore', the actor commits its outputs before it sees that step's inputs;
                'mealy', the actor sees that step's inputs before it chooses its outputs.
    """
    if semantics not in SEMANTICS:
        raise ValueError(f"semantics must be 'moore' or 'mealy', not {semantics!r}")
    da = [load(d) for d in dom]
    ga = [load(g.hoa) for g in goals]
    vocab = set().union(*(a.aps for a in da + ga))
    outputs = sorted(set().union(*(g.cstr for g in goals)) & vocab) if goals else []
    inputs = sorted(vocab - set(outputs))
    IV, OV = valuations(inputs), valuations(outputs)
    res = Result(list(goals), inputs, outputs, False, False, semantics=semantics)

    D = _explore(da, IV, OV)
    A = _explore(da + ga, IV, OV)
    if D is None:
        res.witness = '    the domain theory is unsatisfiable'
        return res
    if A is None:
        res.witness = '    the goals are unsatisfiable within the domain'
        return res
    k = len(da)
    sA, sD, order, parent = A['succ'], D['succ'], A['order'], A['parent']

    def okD(q, i, o):          # the domain allows this step
        return (i, o) in sD[q[:k]]

    def prefix(q):
        steps = []
        while parent[q] is not None:
            q, (i, o) = parent[q]
            steps.append((i, o))
        steps.reverse()
        if not steps:
            return '    at the initial step'
        return '\n'.join(f'    step {n}: env {_fmt(i, inputs)}  actor {_fmt(o, outputs)}'
                         for n, (i, o) in enumerate(steps))

    def inputs_of(q):          # inputs the domain allows, with some output
        return [i for i in IV if any(okD(q, i, o) for o in OV)]

    # Exact: every reachable state is input-enabled.
    for q in order:
        if semantics == 'moore':
            # Every output the goals allow for some input must be allowed for every input.
            for o in OV:
                allowed = {i for i in IV if (i, o) in sA[q]}
                if not allowed:
                    continue
                missing = {i for i in IV if okD(q, i, o)} - allowed
                if missing:
                    bad = sorted(missing, key=sorted)[0]
                    res.witness = (prefix(q) + f'\n    then the actor may output {_fmt(o, outputs)},'
                                   f' but env {_fmt(bad, inputs)} would violate the goals')
                    break
        else:
            # Every input must have some output the goals allow.
            missing = [i for i in inputs_of(q) if not any((i, o) in sA[q] for o in OV)]
            if missing:
                bad = sorted(missing, key=sorted)[0]
                res.witness = (prefix(q) + f'\n    then env {_fmt(bad, inputs)},'
                               f' and no output of the actor satisfies the goals')
        if res.witness:
            break
    res.exact = not res.witness

    # Standard: safety game, greatest fixpoint of winning states.
    win, changed = set(order), True
    while changed:
        changed = False
        for q in list(win):
            def good(i, o):
                return (i, o) in sA[q] and sA[q][(i, o)] in win

            if semantics == 'moore':   # some output is safe for every input
                ok = any(any(okD(q, i, o) for i in IV) and
                         all(good(i, o) for i in IV if okD(q, i, o)) for o in OV)
            else:                      # every input has a safe output
                ok = all(any(good(i, o) for o in OV) for i in inputs_of(q))
            if not ok:
                win.discard(q)
                changed = True
    res.standard = A['init'] in win
    return res


def check_hoa(hoa, outputs=None, dom=(), name='automaton', semantics='moore'):
    """Check one automaton (HOA text or .hoa path). outputs default to its controllable-AP header."""
    return check([goal(name, hoa, outputs)], dom, semantics)


def minimal_conflicts(goals, dom=(), notion='exact', semantics='moore'):
    """All minimal sets of goals that are not realizable together (every strict subset is).

    Such goals are not inconsistent: they can be satisfied together, but the environment can create a
    conflict-inducing condition (see Result.witness) in which no output satisfies all of them."""
    assert notion in ('exact', 'standard')
    goals = list(goals)
    realizable, all_sub_ok, found = {frozenset(): True}, {frozenset(): True}, []
    for k in range(1, len(goals) + 1):
        for combo in combinations(goals, k):
            s = frozenset(combo)
            r = check(list(combo), dom, semantics)
            realizable[s] = r.exact if notion == 'exact' else r.standard
            all_sub_ok[s] = all(realizable[s - {g}] and all_sub_ok[s - {g}] for g in s)
            if not realizable[s] and all_sub_ok[s]:
                found.append([g.name for g in combo])
    return found


# ----------------------------------------------------------------------------
# Writing HOA (e.g. to save the automaton of a conjunction)
# ----------------------------------------------------------------------------
def _short_label(minterms, n):
    """Compact DNF for a set of minterms over n variables (Quine-McCluskey, greedy cover)."""
    if not minterms:
        return 'f'
    terms, primes = {tuple(m) for m in minterms}, set()
    while terms:
        merged, used = set(), set()
        tl = list(terms)
        for a, b in combinations(tl, 2):
            diff = [j for j in range(n) if a[j] != b[j]]
            if len(diff) == 1 and '-' not in (a[diff[0]], b[diff[0]]):
                c = list(a)
                c[diff[0]] = '-'
                merged.add(tuple(c))
                used |= {a, b}
        primes |= terms - used
        terms = merged
    covers = lambda p, m: all(x == '-' or x == y for x, y in zip(p, m))
    todo, chosen = {tuple(m) for m in minterms}, []
    while todo:
        best = max(primes, key=lambda p: (sum(covers(p, m) for m in todo), p.count('-')))
        chosen.append(best)
        todo = {m for m in todo if not covers(best, m)}
    def term(p):
        lits = [str(j) if x == 1 else f'!{j}' for j, x in enumerate(p) if x != '-']
        return '&'.join(lits) or 't'
    return ' | '.join(sorted(term(p) for p in chosen))


def to_hoa(goals, dom=(), name=None):
    """The deterministic automaton of the goals within the domain (all states accepting), with the
    actor's outputs in a controllable-AP header."""
    da = [load(d) for d in dom]
    ga = [load(g.hoa) for g in goals]
    vocab = set().union(*(a.aps for a in da + ga))
    outputs = sorted(set().union(*(g.cstr for g in goals)) & vocab)
    inputs = sorted(vocab - set(outputs))
    aps = inputs + outputs
    A = _explore(da + ga, valuations(inputs), valuations(outputs))
    states = A['order'] if A else []
    num = {q: n for n, q in enumerate(states)}
    out = ['HOA: v1', f'name: "{name or " & ".join(g.name for g in goals)}"',
           f'States: {max(len(states), 1)}', 'Start: 0',
           f'AP: {len(aps)} ' + ' '.join(f'"{a}"' for a in aps),
           'acc-name: Buchi', 'Acceptance: 1 Inf(0)',
           'properties: trans-labels explicit-labels state-acc deterministic']
    if outputs:
        out.append('controllable-AP: ' + ' '.join(str(aps.index(a)) for a in outputs))
    out.append('--BODY--')
    if not states:
        out.append('State: 0 {0}')
    for q in states:
        out.append(f'State: {num[q]} {{0}}')
        by_dst = {}
        for (i, o), r in A['succ'][q].items():
            by_dst.setdefault(num[r], []).append([1 if a in (i | o) else 0 for a in aps])
        for d, ms in sorted(by_dst.items()):
            out.append(f'[{_short_label(ms, len(aps))}] {d}')
    out.append('--END--')
    return '\n'.join(out)
