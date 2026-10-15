"""LTL -> HOA with Spot.

Uses Spot's Python bindings if they can be imported, otherwise Spot's command-line tools
(`ltl2tgba`, `ltlfilt`). Each formula is translated into a deterministic monitor: a deterministic
automaton whose states are all accepting, which is the input the checker expects. This only
makes sense for safety formulas, so non-safety formulas are rejected.
"""
import shutil
import subprocess


class SpotNotFound(RuntimeError):
    pass


def spot_backend():
    """'python', 'cli', or None if Spot is not installed."""
    try:
        import spot  # noqa: F401
        return 'python'
    except ImportError:
        pass
    if shutil.which('ltl2tgba') and shutil.which('ltlfilt'):
        return 'cli'
    return None


def ltl_to_hoa(formula):
    """Translate an LTL safety formula (Spot syntax) into HOA text."""
    backend = spot_backend()
    if backend == 'python':
        import spot
        f = spot.formula(formula)
        if not f.is_syntactic_safety():
            raise ValueError(f'Not a (syntactic) safety formula: {formula}')
        return spot.translate(f, 'monitor', 'deterministic').to_str('hoa')
    if backend == 'cli':
        safe = subprocess.run(['ltlfilt', '--syntactic-safety', '-f', formula],
                              capture_output=True, text=True)
        if not safe.stdout.strip():
            raise ValueError(f'Not a (syntactic) safety formula: {formula}')
        out = subprocess.run(['ltl2tgba', '-M', '-D', '-f', formula],
                             capture_output=True, text=True, check=True)
        return out.stdout
    raise SpotNotFound('Spot is not installed. Install it with `conda install -c conda-forge spot`, '
                       'or give the automata as .hoa files.')


def with_controllable(hoa_text, cstr):
    """Add a controllable-AP header listing the propositions of `cstr` that the automaton uses."""
    if 'controllable-AP:' in hoa_text:
        return hoa_text
    from .hoa import parse_hoa
    aps = parse_hoa(hoa_text)['aps']
    idx = [str(i) for i, a in enumerate(aps) if a in set(cstr)]
    if not idx:
        return hoa_text
    return hoa_text.replace('--BODY--', 'controllable-AP: ' + ' '.join(idx) + '\n--BODY--', 1)
