# Python interface

Checks whether a set of safety goals, given as automata in HOA format, is **standardly** or **exactly** realizable
within a domain theory, and finds the **minimal unrealizable sets** of goals. Pure Python (3.9+), no dependencies.
Everything below is importable from `exactreal`. For specs, Spot and the command line, see the [README](../README.md).

- **Standard realizability:** some controller satisfies the goals. It may be more restrictive than they are, for
  example by never entering a state.
- **Exact realizability:** some input-enabled controller has exactly the traces of the goals. It cannot avoid anything
  they allow.
- **Minimal unrealizable set:** a set of goals that is not realizable together, while every strict subset is. The goals
  are not inconsistent (they can be satisfied together). The environment can create a **conflict-inducing condition**,
  a situation in which no output satisfies all of them. The checker reports it as a witness.

## Input

Each goal is an automaton in HOA format, given as text or as the path of a `.hoa` file. It must be:

- a **Büchi** or generalized Büchi automaton (`Acceptance: 0 t`, `1 Inf(0)`, `Inf(0)&Inf(1)`, …);
- **deterministic**, with a single initial state;
- with **only accepting states**, which is what Spot produces for a safety formula.

Explicit edge labels, state labels and aliases (`@name`) are supported. Implicit labels, alternating automata and
other acceptance conditions are not.

To produce the input with Spot:

```bash
ltl2tgba -B -D -S -f 'G(highWater -> X pump)' > R1.hoa
```

```python
hoa = spot.translate('G(highWater -> X pump)', 'Buchi', 'deterministic', 'state-based').to_str('hoa')
```

Domain properties are automata too. Only domain properties belong in the domain theory, never assumptions:
assumptions can fail, and including them would hide unrealizable sets.

## Inputs and outputs

The **actor** controls the propositions in the union of the goals' `cstr` (constrained propositions). Every other
proposition that appears in the goals or the domain is an **input**, chosen by the environment.

If a variable with several values is encoded as several propositions (for example `ap_state` as `ap_TRANSITION`,
`ap_NOMINAL`, …), list **all** of them in `cstr`, even the ones a single goal does not mention. Otherwise the missing
ones become inputs.

## What a step means

There are two ways to read a step. Pick one with the `semantics` parameter (`--semantics` on the command line). The default is `moore`.

- **Moore** (`moore`): the actor commits its outputs before it sees that step's inputs.
- **Mealy** (`mealy`): the actor sees that step's inputs and then chooses its outputs.

Each step changes both checks. The conditions apply to every reachable state of the product automaton, and "every
input" means every input the domain allows:

| Check | Moore | Mealy |
|---|---|---|
| Exact (input-enabled) | every output the goals allow for some input is allowed for every input | every input has some output the goals allow |
| Standard (safety game) | some output keeps the run safe for every input | every input has an output that keeps the run safe |

Mealy is the weaker reading: whatever is realizable with Moore steps is also realizable with Mealy steps. For example,
autopilot R02/R03 is an exact conflict with Moore steps, but not with Mealy steps. Both conditions follow the note
*Checking Exact Realizability of LTL Specifications* (Section 2 for Mealy, Section 5 for Moore).

## Interface

### `goal(name, hoa, cstr=None) -> Goal`

Creates a goal.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Name shown in the results. |
| `hoa` | `str` | HOA text, or the path of a `.hoa` file. |
| `cstr` | `str` or iterable of `str` | Propositions the goal constrains. A string may be space- or comma-separated. If omitted, it is read from the HOA's `controllable-AP:` header; if there is no header, an error is raised. |

```python
R1 = goal('R1', 'R1.hoa', 'pump')
R02 = goal('R02', hoa_text, ['ap_TRANSITION', 'ap_NOMINAL', 'ap_STANDBY', 'ap_MANEUVER'])
```

`Goal` is a frozen dataclass with fields `name`, `hoa` and `cstr` (a `frozenset`). Printing a goal shows its number of
states, its propositions and its `cstr`.

### `check(goals, dom=(), semantics='moore') -> Result`

Checks standard and exact realizability of a set of goals.

| Parameter | Type | Description |
|---|---|---|
| `goals` | list of `Goal` | The goals to check together. |
| `dom` | list of `str` | Domain properties, as HOA texts or `.hoa` paths. |
| `semantics` | `'moore'` or `'mealy'` | When the actor chooses its outputs. See [What a step means](#what-a-step-means). `SEMANTICS` lists both. |

```python
r = check([R1, R2], ['dom.hoa'])
r.exact      # False
print(r)     # full report, with the conflict-inducing condition
```

### `Result`

What `check` returns.

| Field | Type | Description |
|---|---|---|
| `goals` | list of `Goal` | The goals that were checked. |
| `inputs` | list of `str` | Propositions treated as inputs. |
| `outputs` | list of `str` | Propositions controlled by the actor. |
| `standard` | `bool` | Standardly realizable. |
| `exact` | `bool` | Exactly realizable. |
| `witness` | `str` | Empty if exactly realizable. Otherwise the **conflict-inducing condition**: the steps that lead to a state that is not input-enabled, then, with Moore steps, the output the actor may choose and the input that would then violate the goals, or, with Mealy steps, the input that no output can answer. |
| `semantics` | `str` | `'moore'` or `'mealy'`. |

Example witness for the mine pump:

```
at the initial step
then the actor may output {!PUMP}, but env {highWater, !lowWater, methane} would violate the goals
```

### `check_hoa(hoa, outputs=None, dom=(), name='automaton', semantics='moore') -> Result`

Shortcut for checking a single automaton: `check([goal(name, hoa, outputs)], dom, semantics)`.

```python
print(check_hoa('pump.hoa', outputs='pump'))
```

### `minimal_conflicts(goals, dom=(), notion='exact', semantics='moore') -> list[list[str]]`

Finds all minimal unrealizable sets: sets of goals that are not realizable together, while every strict subset is. (The function keeps the name `minimal_conflicts`.)

| Parameter | Type | Description |
|---|---|---|
| `goals` | list of `Goal` | The specification. |
| `dom` | list of `str` | Domain properties, as HOA texts or paths. |
| `notion` | `'exact'` or `'standard'` | Which realizability defines "unrealizable". |
| `semantics` | `'moore'` or `'mealy'` | When the actor chooses its outputs. |

Returns the sets as lists of goal names, smallest first. It checks every subset, so with *n* goals it runs
2ⁿ − 1 checks. This is fine up to about 12–15 goals.

```python
minimal_conflicts(MINE_PUMP, DOM, 'exact')
# [['R1', 'R2']]
```

### `to_hoa(goals, dom=(), name=None) -> str`

Returns the automaton of the conjunction of the goals within the domain, as HOA text. The automaton is deterministic,
all its states are accepting, its labels are simplified, and it has a `controllable-AP:` header with the actor's
outputs. You can use it to save a conjunction or to look at it in Spot.

### Lower-level functions

| Function | Description |
|---|---|
| `load(spec) -> Automaton` | Reads HOA text or a `.hoa` path and validates it. Results are cached. |
| `Automaton` | `init` (initial state), `next(q, letter)` (successor, or `None`), `aps`, `ap_names`, `controllable`, `n_states`, `name`. A `letter` is the `frozenset` of true propositions. |
| `parse_hoa(text) -> dict` | Raw parse: `name`, `aps`, `starts`, `edges`, `acc`, `controllable`. It does not validate. |
| `valuations(names) -> list[frozenset]` | All valuations of a set of propositions. |

## How it works

1. **Product.** The checker builds the product of the goal and domain automata over every valuation of the inputs
   and outputs. It then removes the states from which the conjunction has no infinite continuation: each automaton on
   its own always has one, but two automata may not share any.
2. **Exact check.** Every reachable state of the product must be input-enabled. With Moore steps: for every output
   the actor may choose, every input the domain allows must be accepted. With Mealy steps: every input the domain
   allows must have some output that is accepted.
3. **Standard check.** A safety game: the greatest fixpoint of states from which the actor can always stay inside the
   product. With Moore steps a state is winning if some output is safe for every input; with Mealy steps, if every
   input has a safe output. The goals are realizable if the initial state is winning.

Inputs that the domain rules out are never required. That is how domain properties make goals realizable, for example
`¬(highWater ∧ lowWater)` for R1 and R3 in the mine pump.

## Errors

`load` and `goal` raise `ValueError` or `SyntaxError` when an automaton:

- has more than one initial state, or a universal initial state;
- has two edges for the same letter (not deterministic). This is checked for automata with up to 16 propositions;
- has a non-accepting state or edge;
- uses implicit labels, alternation, or an unsupported acceptance condition;
- is a goal without `cstr` and without a `controllable-AP:` header.

## Limitations

- Only safety properties. Liveness is never exactly realizable.
- The cost grows with 2^(number of propositions) per state, and with 2^(number of goals) in `minimal_conflicts`.
- The translation through Spot's Python bindings has not been run yet. Run `pytest` on a machine with Spot.

### Specs and Spot

| Function | Description |
|---|---|
| `load_spec(path) -> Spec` | Reads a TOML spec. `Spec` has `name`, `path`, `entries` and `of_kind(*kinds)`. |
| `Entry` | `id`, `kind`, `ltl`, `hoa`, `cstr`, `description`. |
| `build_automata(spec, hoa_dir=None, source='auto') -> (dict, str)` | HOA text for every entry, plus where it came from. `source='spot'` translates with Spot, `'files'` reads `<hoa_dir>/<id>.hoa`, `'auto'` uses Spot if it is installed. |
| `goals_and_domain(spec, automata, with_assumptions=False) -> (goals, dom)` | The requirements as `Goal`s and the domain theory. Assumptions are added to the domain only with `with_assumptions=True`, as a diagnostic. |
| `ltl_to_hoa(formula) -> str` | Spot translation into a deterministic monitor. Raises `SpotNotFound` if Spot is missing and `ValueError` for non-safety formulas. |
| `spot_backend() -> 'python' \| 'cli' \| None` | Which Spot is available. |
| `with_controllable(hoa_text, cstr) -> str` | Adds a `controllable-AP:` header. |
