"""Specifications as TOML files: requirements, domain properties and domain assumptions."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .realizability import goal
from .translate import ltl_to_hoa, spot_backend, with_controllable

GOAL_KINDS = {'requirement', 'goal'}
KINDS = GOAL_KINDS | {'domain', 'assumption'}


@dataclass
class Entry:
    id: str
    kind: str                      # requirement | goal | domain | assumption
    ltl: str = ''
    hoa: str = ''                  # path to a .hoa file, relative to the spec file
    cstr: list = field(default_factory=list)
    description: str = ''


@dataclass
class Spec:
    name: str
    path: Path
    entries: list

    def of_kind(self, *kinds):
        return [e for e in self.entries if e.kind in kinds]


def load_spec(path):
    path = Path(path)
    with open(path, 'rb') as fh:
        data = tomllib.load(fh)
    entries = []
    for raw in data.get('entry', []):
        e = Entry(**raw)
        if e.kind not in KINDS:
            raise ValueError(f'{path}: {e.id} has kind {e.kind!r}; expected one of {sorted(KINDS)}')
        if not (e.ltl or e.hoa):
            raise ValueError(f'{path}: {e.id} needs an `ltl` formula or a `hoa` file')
        if e.kind in GOAL_KINDS and not e.cstr:
            raise ValueError(f'{path}: requirement {e.id} needs `cstr`')
        entries.append(e)
    ids = [e.id for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError(f'{path}: duplicate ids')
    return Spec(data.get('name', path.stem), path, entries)


def build_automata(spec, hoa_dir=None, source='auto'):
    """HOA text for every entry.

    source: 'spot'  - translate the LTL formulas with Spot;
            'files' - read <hoa_dir>/<id>.hoa;
            'auto'  - Spot if it is installed, otherwise the files.
    An entry with an explicit `hoa` path always uses that file.
    Returns (dict id -> HOA text, description of where the automata came from).
    """
    if source == 'auto':
        source = 'spot' if spot_backend() else 'files'
    if source == 'files' and hoa_dir is None:
        raise ValueError('Spot is not installed: pass the folder with the .hoa files (hoa_dir)')
    out = {}
    for e in spec.entries:
        if e.hoa:
            text = (spec.path.parent / e.hoa).read_text()
        elif source == 'spot':
            text = ltl_to_hoa(e.ltl)
        else:
            f = Path(hoa_dir) / f'{e.id}.hoa'
            if not f.exists():
                raise FileNotFoundError(f'{f} not found')
            text = f.read_text()
        out[e.id] = with_controllable(text, e.cstr) if e.cstr else text
    where = f'Spot ({spot_backend()})' if source == 'spot' else f'files in {hoa_dir}'
    return out, where


def goals_and_domain(spec, automata, with_assumptions=False):
    """Goals (requirements) and the domain theory. Assumptions are left out of the domain unless
    with_assumptions=True, which is only a diagnostic: it shows which conflicts they would hide."""
    goals = [goal(e.id, automata[e.id], e.cstr) for e in spec.of_kind(*GOAL_KINDS)]
    kinds = ('domain', 'assumption') if with_assumptions else ('domain',)
    dom = [automata[e.id] for e in spec.of_kind(*kinds)]
    return goals, dom
