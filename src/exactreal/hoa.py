"""Reading HOA automata: deterministic Büchi automata whose states are all accepting."""
import os
import re
from functools import lru_cache
from itertools import product

# ----------------------------------------------------------------------------
# Reading HOA
# ----------------------------------------------------------------------------
_BODY_TOKEN = re.compile(r'State:|\[[^\]]*\]|\{[^}]*\}|"(?:[^"\\]|\\.)*"|\d+|&|\S+')
_LABEL_TOKEN = re.compile(r'\d+|@[A-Za-z0-9_.-]+|[tf!&|()]')


def _compile_label(text, aliases):
    """Turn an HOA label such as `0&!1 | 2` into a function of the set of true AP indices."""
    toks, pos = _LABEL_TOKEN.findall(text), [0]
    if ''.join(toks) != re.sub(r'\s+', '', text):
        raise SyntaxError(f'Cannot read HOA label [{text}]')

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def eat():
        pos[0] += 1
        return toks[pos[0] - 1]

    def disj():
        parts = [conj()]
        while peek() == '|':
            eat()
            parts.append(conj())
        return parts[0] if len(parts) == 1 else (lambda v, ps=parts: any(p(v) for p in ps))

    def conj():
        parts = [neg()]
        while peek() == '&':
            eat()
            parts.append(neg())
        return parts[0] if len(parts) == 1 else (lambda v, ps=parts: all(p(v) for p in ps))

    def neg():
        if peek() == '!':
            eat()
            p = neg()
            return lambda v: not p(v)
        return atom()

    def atom():
        tok = eat() if peek() is not None else None
        if tok == '(':
            p = disj()
            if peek() != ')':
                raise SyntaxError(f'Unbalanced parentheses in [{text}]')
            eat()
            return p
        if tok == 't':
            return lambda v: True
        if tok == 'f':
            return lambda v: False
        if tok and tok.startswith('@'):
            if tok not in aliases:
                raise SyntaxError(f'Unknown alias {tok}')
            return aliases[tok]
        if tok and tok.isdigit():
            n = int(tok)
            return lambda v: n in v
        raise SyntaxError(f'Unexpected {tok!r} in label [{text}]')

    p = disj()
    if peek() is not None:
        raise SyntaxError(f'Unexpected {peek()!r} in label [{text}]')
    return p


def _acceptance_sets(text):
    """Acceptance sets that every edge must carry: t -> none; Inf(i) & Inf(j)... -> {i, j}."""
    parts = text.split(None, 1)
    cond = re.sub(r'\s+', '', parts[1] if len(parts) > 1 else 't') or 't'
    while cond.startswith('((') or cond in ('(t)', '(f)'):
        cond = cond[1:-1]
    if cond == 't':
        return set()
    if cond == 'f':
        raise ValueError('The automaton accepts nothing (Acceptance: f)')
    sets = set()
    for c in cond.split('&'):
        m = re.fullmatch(r'\(?Inf\((\d+)\)\)?', c)
        if not m:
            raise ValueError(f'Unsupported acceptance {text!r}: expected Büchi or generalized Büchi')
        sets.add(int(m.group(1)))
    return sets


def parse_hoa(text):
    if '--BODY--' not in text:
        raise SyntaxError('Not an HOA automaton: missing --BODY--')
    head, body = text.split('--BODY--', 1)
    body = body.split('--END--', 1)[0]
    n_states, starts, aps, aliases, acc, ctrl, name = None, [], [], {}, set(), None, ''
    for line in head.splitlines():
        if ':' not in line:
            continue
        key, rest = (x.strip() for x in line.split(':', 1))
        if key == 'States':
            n_states = int(rest)
        elif key == 'Start':
            if '&' in rest:
                raise ValueError('Universal initial states are not supported')
            starts.append(int(rest))
        elif key == 'AP':
            aps = [a[1:-1] for a in re.findall(r'"(?:[^"\\]|\\.)*"', rest)]
        elif key == 'Alias':
            alias, expr = rest.split(None, 1)
            aliases[alias] = _compile_label(expr, aliases)
        elif key == 'Acceptance':
            acc = _acceptance_sets(rest)
        elif key == 'controllable-AP':
            ctrl = [int(x) for x in rest.split()]
        elif key == 'name':
            name = rest.strip('"')

    edges, cur, state_label, state_marks = {}, None, None, set()
    toks, k = _BODY_TOKEN.findall(body), 0
    marks = lambda tok: {int(x) for x in tok[1:-1].split()}
    while k < len(toks):
        tok = toks[k]
        if tok == 'State:':
            k += 1
            state_label = None
            if toks[k].startswith('['):
                state_label = _compile_label(toks[k][1:-1], aliases)
                k += 1
            cur = int(toks[k])
            k += 1
            edges.setdefault(cur, [])
            if k < len(toks) and toks[k].startswith('"'):
                k += 1
            state_marks = set()
            if k < len(toks) and toks[k].startswith('{'):
                state_marks = marks(toks[k])
                k += 1
            continue
        label = state_label
        if tok.startswith('['):
            label = _compile_label(tok[1:-1], aliases)
            k += 1
        if label is None:
            raise ValueError('Implicit edge labels are not supported: export with explicit labels')
        dst = int(toks[k])
        k += 1
        if k < len(toks) and toks[k] == '&':
            raise ValueError('Alternating (universal) automata are not supported')
        m = set(state_marks)
        if k < len(toks) and toks[k].startswith('{'):
            m |= marks(toks[k])
            k += 1
        edges[cur].append((label, dst, frozenset(m)))
    n_states = n_states if n_states is not None else (max(edges) + 1 if edges else 0)
    for s in range(n_states):
        edges.setdefault(s, [])
    return {'name': name, 'aps': aps, 'starts': starts, 'edges': edges, 'acc': acc,
            'controllable': [aps[i] for i in ctrl] if ctrl is not None else None}


def valuations(names):
    names = sorted(names)
    return [frozenset(n for n, v in zip(names, bits) if v)
            for bits in product([False, True], repeat=len(names))]


class Automaton:
    """A deterministic automaton whose states are all accepting."""

    def __init__(self, text):
        h = parse_hoa(text)
        self.name, self.ap_names, self.controllable = h['name'], h['aps'], h['controllable']
        self.aps = frozenset(h['aps'])
        self.index = {a: i for i, a in enumerate(h['aps'])}
        self.n_states = len(h['edges'])
        if len(h['starts']) != 1:
            raise ValueError(f'Expected exactly one initial state, found {len(h["starts"])}')
        self.init = h['starts'][0]
        self.edges = {s: [(lab, d) for lab, d, _ in es] for s, es in h['edges'].items()}
        for s, es in h['edges'].items():   # every state accepting
            for _, d, m in es:
                if not h['acc'] <= m:
                    raise ValueError(f'State {s} is not accepting (edge to {d} lacks marks '
                                     f'{sorted(h["acc"] - m)}); expected only accepting states')
        if len(self.aps) <= 16:            # deterministic
            for s, es in self.edges.items():
                for v in valuations(range(len(self.ap_names))):
                    if sum(1 for lab, _ in es if lab(v)) > 1:
                        letter = {self.ap_names[i] for i in v}
                        raise ValueError(f'Not deterministic: state {s} has several edges for {sorted(letter)}')
        self._cache = {}

    def next(self, q, letter):
        """Successor of state q on `letter` (frozenset of true propositions), or None."""
        key = (q, letter & self.aps)
        if key not in self._cache:
            v = frozenset(self.index[a] for a in key[1])
            self._cache[key] = next((d for lab, d in self.edges[q] if lab(v)), None)
        return self._cache[key]


@lru_cache(maxsize=None)
def load(spec):
    """An Automaton from HOA text or from the path of a .hoa file."""
    if not spec.lstrip().startswith('HOA:'):
        if not os.path.exists(spec.strip()):
            raise ValueError(f'Not HOA text and not an existing file: {spec[:60]!r}')
        with open(spec.strip()) as fh:
            spec = fh.read()
    return Automaton(spec)


