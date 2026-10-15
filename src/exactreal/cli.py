"""Command line: generate the automata of a spec and check it.

    exactreal hoa   SPEC [--out DIR]
    exactreal check SPEC [--hoa-dir DIR] [--source auto|spot|files]
                         [--semantics moore|mealy|both] [--notion exact|standard|both]
                         [--with-assumptions] [--goals R01,R08]
"""
import argparse
import sys
from pathlib import Path

from .realizability import check, minimal_conflicts
from .spec import GOAL_KINDS, build_automata, goals_and_domain, load_spec
from .translate import SpotNotFound, ltl_to_hoa, spot_backend, with_controllable


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
            print(f'{e.id}: uses {e.hoa}, skipped')
            continue
        text = with_controllable(ltl_to_hoa(e.ltl), e.cstr) if e.cstr else ltl_to_hoa(e.ltl)
        (out / f'{e.id}.hoa').write_text(text)
        print(f'{e.id}: {out / (e.id + ".hoa")}')


def cmd_check(args):
    spec = load_spec(args.spec)
    automata, where = build_automata(spec, args.hoa_dir, args.source)
    goals, dom = goals_and_domain(spec, automata, args.with_assumptions)
    dom_ids = [e.id for e in spec.of_kind('domain', *(('assumption',) if args.with_assumptions else ()))]
    print(f'# {spec.name}')
    print(f'automata: {where}')
    print(f'goals   : {", ".join(g.name for g in goals)}')
    print(f'domain  : {", ".join(dom_ids) or "(none)"}')
    left_out = [e.id for e in spec.of_kind('assumption')] if not args.with_assumptions else []
    if left_out:
        print(f'assumptions left out of the domain: {", ".join(left_out)}')
    if args.with_assumptions:
        print('NOTE: assumptions are treated as domain properties (diagnostic only)')
    sems = _both(args.semantics, ('mealy', 'moore'))
    notions = _both(args.notion, ('standard', 'exact'))

    if args.goals:
        names = [n.strip() for n in args.goals.split(',')]
        chosen = [g for g in goals if g.name in names]
        missing = set(names) - {g.name for g in chosen}
        if missing:
            sys.exit(f'unknown goals: {", ".join(sorted(missing))}')
        for sem in sems:
            print()
            print(check(chosen, dom, sem))
        return

    print('\n## Each goal alone')
    for g in goals:
        cells = [f'{n} {s}: {"yes" if getattr(check([g], dom, s), n) else "NO"}'
                 for n in notions for s in sems]
        print(f'  {g.name:6} ' + '   '.join(cells))

    for notion in notions:
        for sem in sems:
            cs = minimal_conflicts(goals, dom, notion, sem)
            print(f'\n## Minimal conflicts: {notion}, {sem}  ({len(cs)})')
            by_name = {g.name: g for g in goals}
            for c in cs:
                print('  - ' + ', '.join(c))
                if args.witness:
                    r = check([by_name[n] for n in c], dom, sem)
                    if notion == 'exact' and r.witness:
                        print('\n'.join('  ' + line for line in r.witness.splitlines()))


def main(argv=None):
    p = argparse.ArgumentParser(prog='exactreal', description='Exact and standard realizability of safety goals.')
    sub = p.add_subparsers(dest='cmd', required=True)

    h = sub.add_parser('hoa', help='translate the LTL formulas of a spec into .hoa files with Spot')
    h.add_argument('spec')
    h.add_argument('--out', help='output folder (default: build/<spec name>)')
    h.set_defaults(func=cmd_hoa)

    c = sub.add_parser('check', help='check realizability and find minimal conflicts')
    c.add_argument('spec')
    c.add_argument('--hoa-dir', help='folder with <id>.hoa files (used when Spot is not installed)')
    c.add_argument('--source', choices=['auto', 'spot', 'files'], default='auto')
    c.add_argument('--semantics', choices=['moore', 'mealy', 'both'], default='both')
    c.add_argument('--notion', choices=['exact', 'standard', 'both'], default='both')
    c.add_argument('--with-assumptions', action='store_true',
                   help='treat assumptions as domain properties (diagnostic)')
    c.add_argument('--goals', help='check only these goals together, e.g. R01,R08 (prints the witness)')
    c.add_argument('--no-witness', dest='witness', action='store_false',
                   help='do not print why each exact conflict is not realizable')
    c.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, SyntaxError, FileNotFoundError, SpotNotFound) as e:
        hint = ''
        if 'Spot is not installed' in str(e) and args.cmd == 'check':
            hint = '\nhint: use --hoa-dir, e.g. --hoa-dir examples/hoa/' + Path(args.spec).stem
        sys.exit(f'error: {e}{hint}')


if __name__ == '__main__':
    main()
