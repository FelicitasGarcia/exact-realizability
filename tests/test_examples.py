from conftest import spec_goals

from exactreal import check, minimal_conflicts


def test_mine_pump():
    goals, dom = spec_goals('mine_pump')
    for sem in ('moore', 'mealy'):
        assert minimal_conflicts(goals, dom, 'exact', sem) == [['R1', 'R2']]
    r = check([g for g in goals if g.name in ('R1', 'R2')], dom)
    assert 'highWater' in r.witness and 'methane' in r.witness


def test_mine_pump_assumption_hides_conflict():
    goals, dom = spec_goals('mine_pump', with_assumptions=True)
    assert minimal_conflicts(goals, dom, 'exact', 'moore') == []


def test_patient_monitoring_no_conflict():
    goals, dom = spec_goals('patient_monitoring')
    assert minimal_conflicts(goals, dom, 'exact', 'moore') == []


def test_autopilot():
    goals, dom = spec_goals('autopilot')
    assert minimal_conflicts(goals, dom, 'exact', 'moore') == [
        ['R02', 'R03'], ['R04', 'R05'], ['R06', 'R07'], ['R08', 'R09']]
    spectra = minimal_conflicts(goals, dom, 'standard', 'mealy')
    assert len(spectra) == 8 and all(len(c) == 5 for c in spectra)
    assert ['R03', 'R05', 'R07', 'R08', 'R09'] in spectra
    assert ['R02', 'R05', 'R06', 'R07', 'R09'] in spectra


def test_liquid_mixer_runs():
    goals, dom = spec_goals('liquid_mixer')
    cs = minimal_conflicts(goals, dom, 'exact', 'mealy')
    assert ['R01', 'R08'] in cs          # start and stop pressed together
