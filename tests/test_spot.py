"""Compare Spot's automata with the reference ones in examples/hoa. Skipped without Spot."""
import pytest

from conftest import ROOT, spec_goals
from exactreal import build_automata, goals_and_domain, load_spec, minimal_conflicts, spot_backend

pytestmark = pytest.mark.skipif(spot_backend() is None, reason='Spot is not installed')


@pytest.mark.parametrize('name', ['mine_pump', 'patient_monitoring', 'autopilot', 'liquid_mixer'])
def test_spot_matches_reference(name):
    spec = load_spec(ROOT / 'specs' / f'{name}.toml')
    automata, _ = build_automata(spec, source='spot')
    goals, dom = goals_and_domain(spec, automata)
    ref_goals, ref_dom = spec_goals(name)
    for notion in ('exact', 'standard'):
        assert (minimal_conflicts(goals, dom, notion)
                == minimal_conflicts(ref_goals, ref_dom, notion))
