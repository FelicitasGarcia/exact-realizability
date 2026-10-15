from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def root():
    return ROOT


def spec_goals(name, with_assumptions=False):
    from exactreal import build_automata, goals_and_domain, load_spec
    spec = load_spec(ROOT / 'specs' / f'{name}.toml')
    automata, _ = build_automata(spec, ROOT / 'examples' / 'hoa' / name, source='files')
    return goals_and_domain(spec, automata, with_assumptions)
