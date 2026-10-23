# exactreal

Checks whether a set of safety goals is **standardly** or **exactly** realizable within a domain theory, and finds the
**minimal unrealizable sets** of goals, each with its conflict-inducing condition. You write a specification as LTL
formulas, Spot turns each formula into an automaton (HOA), and the checker works on those automata.

- **Standard realizability:** some controller satisfies the goals. It may be more restrictive than they are, for
  example by never entering a state.
- **Exact realizability:** some input-enabled controller has exactly the traces of the goals. It cannot avoid anything
  they allow.
- **Minimal unrealizable set:** a set of goals that is not realizable together, while every strict subset is. The goals
  are not inconsistent (they can be satisfied together). The environment can create a **conflict-inducing condition**,
  a situation in which no output satisfies all of them. The checker reports it as a witness.

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
exactreal check specs/liquid_mixer.toml --notion exact
exactreal check specs/autopilot.toml --semantics both          # Moore and Mealy steps
exactreal check specs/liquid_mixer.toml --goals R01,R08        # one set of goals, with its condition
exactreal check specs/liquid_mixer.toml --with-assumptions     # which unrealizable sets the assumptions would hide
exactreal hoa specs/liquid_mixer.toml --out build/liquid_mixer # save the automata Spot produces
```

The output is colored when it goes to a terminal. Use `--no-color` (or set `NO_COLOR`) to turn the colors off.

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
  unrealizable sets. Pass `--with-assumptions` to add them anyway and see which ones they hide.

Conventions:

- Inputs are written in lower case and outputs in upper case.
- Proposition names must not start with a digit (Spot rejects them).
- If a variable with several values is encoded as several propositions (as with the autopilot modes), list all of
  them in `cstr`.

## What a step means

There are two ways to read a step. Pick one with `--semantics` (`check(..., semantics=...)`). The default is `moore`.

- **Moore** (`moore`): the controller commits its outputs before it sees that step's inputs.
- **Mealy** (`mealy`): the controller sees that step's inputs and then chooses its outputs.

Each step changes both checks. The conditions apply to every reachable state of the product automaton, and "every
input" means every input the domain allows:

| Check | Moore | Mealy |
|---|---|---|
| Exact (input-enabled) | every output the goals allow for some input is allowed for every input | every input has some output the goals allow |
| Standard (safety game) | some output keeps the run safe for every input | every input has an output that keeps the run safe |

Mealy is the weaker reading: whatever is realizable with Moore steps is also realizable with Mealy steps. For example,
autopilot R02/R03 is an exact conflict with Moore steps, but not with Mealy steps. Both conditions follow the note
*Checking Exact Realizability of LTL Specifications* (Section 2 for Mealy, Section 5 for Moore).

## Examples

| Spec | What it shows |
|---|---|
| `specs/mine_pump.toml` | R1 and R2 are not realizable together (condition: `highWater ∧ methane`). The domain property removes R1/R3. The assumption `¬methane` would hide R1/R2. |
| `specs/mine_pump_fixed.toml` | The mine pump with a methane extractor. R2 lets the pump run when the extractor is on, and R4 turns the extractor on after methane. R1/R2 are now realizable together. |
| `specs/autopilot.toml` | With Moore steps, exact gives the 4 binary conflicts (R02/R03, R04/R05, R06/R07, R08/R09) and standard gives 21 sets of size 5. With Mealy steps, both give 8 sets (exact of size 3, standard of size 5). |
| `specs/liquid_mixer.toml` | Based on the liquid mixer of NASA's FRET report (NASA/TM-2021-20210013008). |
| `specs/patient_monitoring.toml` | No unrealizable set: the controller can always avoid the boundary condition. |

`examples/hoa/` holds reference automata for every entry, so the examples run without Spot. **They were generated
with an earlier reference implementation, not with Spot.** The ones for `mine_pump_fixed` were written by hand. `tests/test_spot.py` checks that Spot's automata give the
same unrealizable sets.

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
print(check(goals[:2], dom))
print(minimal_conflicts(goals, dom, 'exact'))  # [['R1', 'R2']]
```

The full interface is in [docs/api.md](docs/api.md).

## How it works

1. **Translation.** Spot translates each formula into a deterministic monitor (`ltl2tgba -M -D`): a deterministic
   automaton whose states are all accepting. Only syntactic safety formulas are accepted.
2. **Product.** The checker builds the product of the goal and domain automata. It removes the states from which the
   conjunction has no infinite continuation.
3. **Exact check.** Every reachable state must be input-enabled for the inputs the domain allows, with the Moore or
   Mealy condition (see [What a step means](#what-a-step-means)).
4. **Standard check.** A safety game: the greatest fixpoint of winning states, with Moore or Mealy steps.
5. **Minimal unrealizable sets** (`minimal_conflicts`). Every subset of the goals is checked, from smallest to
   largest. This means 2ⁿ − 1 checks,
   which is fine up to about 12–15 requirements.

## Limitations

- Only safety properties. Liveness is never exactly realizable.
- `minimal_conflicts` is exponential in the number of requirements.
- The translation through Spot's Python bindings has not been run yet. The command-line path was tested with stand-in
  tools.
