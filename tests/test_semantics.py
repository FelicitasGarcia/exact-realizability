from itertools import combinations

from conftest import spec_goals

from exactreal import check, check_hoa, minimal_conflicts

# G(O <-> i): the output must copy the input of the same step.
COPY = '''HOA: v1
States: 1
Start: 0
AP: 2 "i" "O"
Acceptance: 0 t
controllable-AP: 1
--BODY--
State: 0
[0&1 | !0&!1] 0
--END--'''

# G O | G(i & !O): realizable (always output O), but not exactly (the note's example).
EITHER = '''HOA: v1
States: 3
Start: 0
AP: 2 "i" "O"
Acceptance: 0 t
controllable-AP: 1
--BODY--
State: 0
[1] 1
[0&!1] 2
State: 1
[1] 1
State: 2
[0&!1] 2
--END--'''


def test_copy_needs_mealy():
    moore, mealy = check_hoa(COPY, semantics='moore'), check_hoa(COPY, semantics='mealy')
    assert not moore.standard and not moore.exact
    assert mealy.standard and mealy.exact


def test_realizable_but_not_exact_in_both():
    for semantics in ('moore', 'mealy'):
        r = check_hoa(EITHER, semantics=semantics)
        assert r.standard and not r.exact
        assert 'env {!i}' in r.witness
    # Mealy fails after the prefix (i, !O), as in the note; Moore already fails at the start,
    # where the output !O is allowed for input i but not for !i.
    mealy = check_hoa(EITHER, semantics='mealy').witness
    assert 'env {i}  actor {!O}' in mealy and 'no output of the actor' in mealy
    assert 'at the initial step' in check_hoa(EITHER, semantics='moore').witness


def test_mealy_is_weaker_than_moore():
    goals, dom = spec_goals('autopilot')
    for k in (1, 2, 3):
        for combo in combinations(goals, k):
            moore, mealy = check(list(combo), dom, 'moore'), check(list(combo), dom, 'mealy')
            assert moore.exact <= mealy.exact and moore.standard <= mealy.standard
            assert mealy.exact <= mealy.standard


def test_mealy_examples():
    goals, dom = spec_goals('mine_pump')
    assert minimal_conflicts(goals, dom, 'exact', 'mealy') == [['R1', 'R2']]
    goals, dom = spec_goals('liquid_mixer')
    exact = minimal_conflicts(goals, dom, 'exact', 'mealy')
    assert ['R04'] not in exact and ['R01', 'R08'] in exact   # R04 only fails with moore steps
