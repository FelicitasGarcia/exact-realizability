# exactreal

Checks whether a set of safety goals is **standardly** or **exactly** realizable within a domain theory, and finds the
**minimal conflicts** between goals. You write a specification as LTL formulas, Spot turns each formula into an
automaton (HOA), and the checker works on those automata.

- **Standard realizability:** some controller satisfies the goals. It may be more restrictive than they are, for
  example by never entering a state.
- **Exact realizability:** some input-enabled controller has exactly the traces of the goals. It cannot avoid anything
  they allow.
- **Conflict:** a set of goals that is not realizable together, while every strict subset is.

## Setup

You need [conda](https://docs.conda.io/en/latest/miniconda.html) (or mamba). Spot is installed from conda-forge,
which has builds for Linux and macOS. On Windows, use WSL.

```bash
git clone <this repo> exact-realizability     # or unzip it
cd exact-realizability
conda env create -f environment.yml           # Python 3.12, Spot, JupyterLab, pytest
conda activate exactreal
pytest                                        # the Spot tests run only when Spot is installed
```

Without conda: `pip install -e ".[dev]"` installs the checker (it has no dependencies). Without Spot, you cannot
translate formulas, but you can check `.hoa` files, including the reference ones in `examples/hoa/`.

## Quick start

```bash
exactreal check specs/mine_pump.toml
exactreal check specs/liquid_mixer.toml --semantics mealy --notion exact
exactreal check specs/liquid_mixer.toml --goals R01,R08        # one set of goals, with the witness
exactreal check specs/liquid_mixer.toml --with-assumptions     # which conflicts the assumptions would hide
exactreal hoa specs/liquid_mixer.toml --out build/liquid_mixer # save the automata Spot produces
```

`exactreal check` translates the formulas with Spot if it is installed. Otherwise it needs `--hoa-dir` with one
`<id>.hoa` file per entry:

```bash
exactreal check specs/autopilot.toml --hoa-dir examples/hoa/autopilot
```

The notebook `notebooks/exact_realizability.ipynb` runs all the examples (`jupyter lab`).

## Writing a specification

A spec is a TOML file with one `[[entry]]` per formula:

```toml
name = "Mine pump"

[[entry]]
id = "R1"
kind = "requirement"
ltl = 'G(highWater -> X PUMP)'
cstr = ["PUMP"]
description = "Pump on after high water"

[[entry]]
id = "D1"
kind = "domain"
ltl = 'G !(highWater & lowWater)'

[[entry]]
id = "A1"
kind = "assumption"
ltl = 'G !methane'
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique name, used in the results and for `<id>.hoa` files. |
| `kind` | yes | `requirement` (or `goal`), `domain` or `assumption`. |
| `ltl` | yes, unless `hoa` | Safety formula in [Spot syntax](https://spot.lre.epita.fr/ioltl.html). Use single quotes. |
| `hoa` | no | Path to a `.hoa` file, relative to the spec, used instead of translating `ltl`. |
| `cstr` | for requirements | Propositions the requirement intends to constrain: the controller's outputs. |
| `description` | no | Free text. |

What each kind does:

- **Requirements** are the goals. The controller controls the union of their `cstr`. Every other proposition is an
  input chosen by the environment.
- **Domain properties** (`domain`) form the domain theory. They restrict which inputs can happen.
- **Domain assumptions** (`assumption`) are *not* part of the domain theory, because they can fail and would hide
  conflicts. Pass `--with-assumptions` to add them anyway and see which conflicts they hide.

Conventions:

- Inputs are written in lower case and outputs in upper case.
- Proposition names must not start with a digit (Spot rejects them).
- If a variable with several values is encoded as several propositions (as with the autopilot modes), list all of
  them in `cstr`.

## Timing semantics

Every check runs under one or both semantics (`--semantics moore|mealy|both`):

| Value | Meaning |
|---|---|
| `moore` | At each step the controller commits its outputs before it sees that step's inputs. |
| `mealy` | The controller sees the step's inputs first, then picks its outputs (GR(1)/Spectra style). |

They give different results. For example, autopilot R02/R03 is an exact conflict only under Moore.

## Examples

| Spec | What it shows |
|---|---|
| `specs/mine_pump.toml` | The classic R1/R2 conflict. The domain property removes R1/R3. The assumption `¬methane` would hide R1/R2. |
| `specs/autopilot.toml` | Standard + Mealy gives Spectra's 8 cores of size 5. Exact + Moore gives the 4 binary conflicts. |
| `specs/liquid_mixer.toml` | Based on the liquid mixer of NASA's FRET report (NASA/TM-2021-20210013008). |
| `specs/patient_monitoring.toml` | No conflict: the controller can always avoid the boundary condition. |

`examples/hoa/` holds reference automata for every entry, so the examples run without Spot. **They were generated
with an earlier reference implementation, not with Spot.** `tests/test_spot.py` checks that Spot's automata give the
same conflicts.

## Project layout

```
src/exactreal/
  hoa.py            read and validate HOA automata
  realizability.py  check, minimal_conflicts, to_hoa
  translate.py      LTL -> HOA with Spot (Python bindings or the ltl2tgba command)
  spec.py           TOML specs
  cli.py            the exactreal command
specs/              example specifications
examples/hoa/       reference automata (not from Spot)
notebooks/          exact_realizability.ipynb
tests/              pytest
docs/api.md         Python interface
```

## Using it from Python

```python
from exactreal import load_spec, build_automata, goals_and_domain, check, minimal_conflicts

spec = load_spec('specs/mine_pump.toml')
automata, where = build_automata(spec)                 # Spot, or hoa_dir=... for files
goals, dom = goals_and_domain(spec, automata)
print(check(goals[:2], dom, 'moore'))
print(minimal_conflicts(goals, dom, 'exact', 'moore'))  # [['R1', 'R2']]
```

The full interface is in [docs/api.md](docs/api.md).

## How it works

1. **Translation.** Spot translates each formula into a deterministic monitor (`ltl2tgba -M -D`): a deterministic
   automaton whose states are all accepting. Only syntactic safety formulas are accepted.
2. **Product.** The checker builds the product of the goal and domain automata. It removes the states from which the
   conjunction has no infinite continuation.
3. **Exact check.** Every reachable state must be input-enabled for the inputs the domain allows.
4. **Standard check.** A safety game: the greatest fixpoint of winning states.
5. **Minimal conflicts.** Every subset of the goals is checked, from smallest to largest. This means 2ⁿ − 1 checks,
   which is fine up to about 12–15 requirements.

## Limitations

- Only safety properties. Liveness is never exactly realizable.
- `minimal_conflicts` is exponential in the number of requirements.
- The translation through Spot's Python bindings has not been run yet. The command-line path was tested with stand-in
  tools.
