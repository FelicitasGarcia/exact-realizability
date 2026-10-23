"""Command line: generate the automata of a spec and check it.

    exactreal hoa   SPEC [--out DIR]
    exactreal check SPEC [--hoa-dir DIR] [--source auto|spot|files] [--notion exact|standard|both]
                         [--semantics moore|mealy|both] [--with-assumptions] [--goals R01,R08] [--no-witness] [--no-color]
"""
import argparse
import os
import re
import sys
from pathlib import Path

from .realizability import SEMANTICS, check, minimal_conflicts
from .spec import build_automata, goals_and_domain, load_spec
from .translate import SpotNotFound, ltl_to_hoa, spot_backend, with_controllable

# ----------------------------------------------------------------------------
# Colors (plain ANSI, no dependencies). Off when piped, with NO_COLOR, or --no-color.
# ----------------------------------------------------------------------------
_CODES = {'bold': '1', 'dim': '2', 'red': '31', 'green': '32', 'yellow': '33',
          'blue': '34', 'magenta': '35', 'cyan': '36'}
_color = False


def _use_color(stream, disabled=False):
    return not disabled and 'NO_COLOR' not in os.environ and hasattr(stream, 'isatty') and stream.isatty()


def paint(text, *styles):
    if not _color or not styles:
        return str(text)
    return '\033[' + ';'.join(_CODES[s] for s in styles) + 'm' + str(text) + '\033[0m'


def yes_no(value, width=0):
    if value:
        return paint('✔ yes'.ljust(width), 'green', 'bold')
    return paint('✘ NO'.ljust(width), 'red', 'bold')


def heading(text):
    return paint(f'\n▌ {text}', 'bold', 'blue')


def field(label, value):
    return f'  {paint(f"{label:<10}", "dim")} {value}'


def witness_lines(text):
    """Color a witness (conflict-inducing condition): steps dim, env cyan, actor yellow, reason red."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith('then '):
            line = paint(line, 'red')
        else:
            line = re.sub(r'step \d+:', lambda m: paint(m.group(), 'dim'), line)
            line = re.sub(r'env \{[^}]*\}', lambda m: paint(m.group(), 'cyan'), line)
            line = re.sub(r'actor \{[^}]*\}', lambda m: paint(m.group(), 'yellow'), line)
        out.append('  ' + line)
    return '\n'.join(out)


def show_result(r):
    print(paint(f'Goals {", ".join(g.name for g in r.goals) or "(no goals)"}', 'bold')
          + paint(f'   ({r.semantics} steps)', 'dim'))
    print(field('inputs', paint(', '.join(r.inputs) or '-', 'cyan')) + paint('   (environment)', 'dim'))
    print(field('outputs', paint(', '.join(r.outputs) or '-', 'yellow')) + paint('   (actor)', 'dim'))
    print(field('standard', yes_no(r.standard)))
    print(field('exact', yes_no(r.exact)))
    if r.witness:
        print(paint('\n  conflict-inducing condition:', 'bold'))
        print(witness_lines(r.witness))


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
def _both(value, options):
    return list(options) if value == 'both' else [value]


def cmd_hoa(args):
    spec = load_spec(args.spec)
    if spot_backend() is None:
        raise SpotNotFound('Spot is not installed. Install it with `conda install -c conda-forge spot`.')
    out = Path(args.out or Path('build') / Path(args.spec).stem)
    out.mkdir(parents=True, exist_ok=True)
    for e in spec.entries:
        if e.hoa:
            print(f'{paint(e.id, "bold")}: uses {e.hoa}, {paint("skipped", "yellow")}')
            continue
        text = with_controllable(ltl_to_hoa(e.ltl), e.cstr) if e.cstr else ltl_to_hoa(e.ltl)
        (out / f'{e.id}.hoa').write_text(text)
        print(f'{paint(e.id, "bold", "green")}: {paint(out / (e.id + ".hoa"), "dim")}')


def cmd_check(args):
    spec = load_spec(args.spec)
    automata, where = build_automata(spec, args.hoa_dir, args.source)
    goals, dom = goals_and_domain(spec, automata, args.with_assumptions)
    dom_ids = [e.id for e in spec.of_kind('domain', *(('assumption',) if args.with_assumptions else ()))]
    print(paint(f'═══ {spec.name} ═══', 'bold', 'magenta'))
    print(field('automata', where))
    print(field('goals', paint(', '.join(g.name for g in goals), 'bold')))
    print(field('domain', ', '.join(dom_ids) or paint('(none)', 'dim')))
    left_out = [e.id for e in spec.of_kind('assumption')] if not args.with_assumptions else []
    if left_out:
        print(field('left out', paint(f'assumptions {", ".join(left_out)} are not in the domain', 'dim')))
    if args.with_assumptions:
        print(paint('  NOTE: assumptions are treated as domain properties (diagnostic only)', 'yellow'))
    notions = _both(args.notion, ('standard', 'exact'))
    semantics = _both(args.semantics, SEMANTICS)
    print(field('steps', ', '.join(semantics)) + paint('   (moore: outputs before inputs, mealy: inputs first)', 'dim'))

    if args.goals:
        names = [n.strip() for n in args.goals.split(',')]
        chosen = [g for g in goals if g.name in names]
        missing = set(names) - {g.name for g in chosen}
        if missing:
            sys.exit(f'unknown goals: {", ".join(sorted(missing))}')
        for sem in semantics:
            print()
            show_result(check(chosen, dom, sem))
        return

    columns = [(n, sem) for sem in semantics for n in notions]
    label = (lambda n, sem: f'{n}/{sem}') if len(semantics) > 1 else (lambda n, sem: n)
    cw = max(8, *(len(label(n, sem)) for n, sem in columns))
    print(heading('Realizable on its own?'))
    width = max(len(g.name) for g in goals)
    print('  ' + ' ' * width + '   ' + '   '.join(paint(f'{label(n, sem):<{cw}}', 'dim') for n, sem in columns))
    for g in goals:
        rs = {sem: check([g], dom, sem) for sem in semantics}
        cells = [yes_no(getattr(rs[sem], n), cw) for n, sem in columns]
        print(f'  {paint(f"{g.name:<{width}}", "bold")}   ' + '   '.join(cells))

    by_name = {g.name: g for g in goals}
    for sem in semantics:
        for notion in notions:
            cs = minimal_conflicts(goals, dom, notion, sem)
            count = paint(len(cs), 'red' if cs else 'green', 'bold')
            print(heading(f'Minimal unrealizable sets: {notion}, {sem} steps') + f'  ({count})')
            if not cs:
                print(paint('  ✔ none', 'green'))
            for c in cs:
                print('  ' + paint('✘ ' + ' ∧ '.join(c), 'red', 'bold') + paint('   not realizable' + ('' if len(c) == 1 else ' together'), 'dim'))
                if args.witness and notion == 'exact':
                    r = check([by_name[n] for n in c], dom, sem)
                    if r.witness:
                        print(paint('    conflict-inducing condition:', 'dim'))
                        print(witness_lines(r.witness))


def main(argv=None):
    global _color
    p = argparse.ArgumentParser(prog='exactreal',
                                description='Exact and standard realizability of safety goals.')
    p.add_argument('--no-color', action='store_true', help='turn colors off')
    sub = p.add_subparsers(dest='cmd', required=True)

    h = sub.add_parser('hoa', help='translate the LTL formulas of a spec into .hoa files with Spot')
    h.add_argument('spec')
    h.add_argument('--out', help='output folder (default: build/<spec name>)')
    h.set_defaults(func=cmd_hoa)

    c = sub.add_parser('check', help='check realizability and find minimal sets of goals that are not realizable together')
    c.add_argument('spec')
    c.add_argument('--hoa-dir', help='folder with <id>.hoa files (used when Spot is not installed)')
    c.add_argument('--source', choices=['auto', 'spot', 'files'], default='auto')
    c.add_argument('--notion', choices=['exact', 'standard', 'both'], default='both')
    c.add_argument('--semantics', choices=['moore', 'mealy', 'both'], default='moore',
                   help='moore: the actor commits its outputs before it sees the inputs (default); '
                        'mealy: it sees the inputs first')
    c.add_argument('--with-assumptions', action='store_true',
                   help='treat assumptions as domain properties (diagnostic)')
    c.add_argument('--goals', help='check only these goals together, e.g. R01,R08 (prints the conflict-inducing condition)')
    c.add_argument('--no-witness', dest='witness', action='store_false',
                   help='do not print the conflict-inducing condition of each exact set')
    for sp in (h, c):      # also accepted after the command; SUPPRESS keeps the global value
        sp.add_argument('--no-color', action='store_true', default=argparse.SUPPRESS, help='turn colors off')
    c.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    _color = _use_color(sys.stdout, args.no_color)
    try:
        args.func(args)
    except (ValueError, SyntaxError, FileNotFoundError, SpotNotFound) as e:
        hint = ''
        if 'Spot is not installed' in str(e) and args.cmd == 'check':
            hint = '\nhint: use --hoa-dir, e.g. --hoa-dir examples/hoa/' + Path(args.spec).stem
        sys.exit(f'{paint("error:", "red", "bold")} {e}{hint}')


if __name__ == '__main__':
    main()
