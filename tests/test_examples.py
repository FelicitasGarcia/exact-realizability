from conftest import spec_goals

from exactreal import check, minimal_conflicts


def test_mine_pump():
    goals, dom = spec_goals('mine_pump')
    assert minimal_conflicts(goals, dom, 'exact') == [['R1', 'R2']]
    r = check([g for g in goals if g.name in ('R1', 'R2')], dom)
    assert 'highWater' in r.witness and 'methane' in r.witness


def test_mine_pump_fixed_with_extractor():
    goals, dom = spec_goals('mine_pump_fixed')
    for notion in ('exact', 'standard'):
        assert minimal_conflicts(goals, dom, notion) == []


def test_mine_pump_assumption_hides_conflict():
    goals, dom = spec_goals('mine_pump', with_assumptions=True)
    assert minimal_conflicts(goals, dom, 'exact') == []


def test_patient_monitoring_no_conflict():
    goals, dom = spec_goals('patient_monitoring')
    assert minimal_conflicts(goals, dom, 'exact') == []


def test_autopilot():
    goals, dom = spec_goals('autopilot')
    assert minimal_conflicts(goals, dom, 'exact') == [
        ['R02', 'R03'], ['R04', 'R05'], ['R06', 'R07'], ['R08', 'R09']]
    standard = minimal_conflicts(goals, dom, 'standard')
    assert len(standard) == 21 and all(len(c) == 5 for c in standard)


def test_autopilot_r02_r03_standard_but_not_exact():
    goals, dom = spec_goals('autopilot')
    r = check([g for g in goals if g.name in ('R02', 'R03')], dom)
    assert r.standard and not r.exact       # the actor can avoid TRANSITION, but not once it is in it
    assert 'AP_TRANSITION' in r.witness


def test_liquid_mixer_runs():
    goals, dom = spec_goals('liquid_mixer')
    cs = minimal_conflicts(goals, dom, 'exact')
    assert ['R01', 'R08'] in cs          # start and stop pressed together
