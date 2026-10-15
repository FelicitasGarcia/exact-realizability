import pytest

from exactreal import check_hoa, goal, load

R1 = '''HOA: v1
States: 2
Start: 0
AP: 2 "highWater" "PUMP"
Acceptance: 1 Inf(0)
controllable-AP: 1
--BODY--
State: 0 {0}
[!0] 0
[0] 1
State: 1 {0}
[!0&1] 0
[0&1] 1
--END--'''


def test_reads_controllable_ap():
    g = goal('R1', R1)
    assert g.cstr == {'PUMP'}
    assert load(R1).n_states == 2


def test_single_goal_is_exact():
    r = check_hoa(R1)
    assert r.exact and r.standard


def test_rejects_non_deterministic():
    with pytest.raises(ValueError, match='Not deterministic'):
        load(R1.replace('[!0] 0\n[0] 1', '[t] 0\n[0] 1'))


def test_rejects_non_accepting_state():
    with pytest.raises(ValueError, match='not accepting'):
        load(R1.replace('State: 1 {0}', 'State: 1'))


def test_aliases_and_state_labels():
    text = '''HOA: v1
States: 1
Start: 0
AP: 1 "a"
Alias: @a 0
Acceptance: 0 t
--BODY--
State: [@a | !@a] 0
0
--END--'''
    assert load(text).next(0, frozenset()) == 0
