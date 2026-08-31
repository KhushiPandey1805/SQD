# Understanding Sample-Based Quantum Diagonalization: A Complete Walkthrough

This guide covers the following notebooks:

1. **`sample-based-quantum-diagonalization.ipynb`** — the N2 tutorial, where SQD is run "by hand" in a notebook.
2. **`function-template-chemistry-workflow.ipynb`** — the same workflow, but packaged as a deployable service (a "Qiskit Function") that you'd call remotely instead of running cell-by-cell.

---

## Part 0 — Quantum Computing Foundations

### 0.1 Qubits and statevectors

In QM you're used to a wavefunction $|\psi\rangle$ living in a Hilbert space. A **qubit** is just the smallest possible quantum system: a 2-dimensional Hilbert space with basis states $|0\rangle$ and $|1\rangle$ (analogous to spin-up/spin-down of a spin-1/2 particle). A general qubit state is $\alpha|0\rangle + \beta|1\rangle$ with $|\alpha|^2+|\beta|^2=1$, exactly like any two-level quantum system you've seen before.

$n$ qubits together live in a $2^n$-dimensional Hilbert space, spanned by basis states like $|01011\rangle$ (a tensor product of individual qubit states). This exponential growth is exactly the "exponentially large Hilbert space" problem chemists run into — an $n$-orbital fermionic system needs $2^n$ basis states too, which is why quantum computers and quantum chemistry are naturally suited to each other.

### 0.2 Quantum circuits = sequences of unitary gates

A **quantum circuit** is a sequence of unitary operators $U_1, U_2, \dots$ applied to an initial state, exactly like time-evolving a wavefunction with $|\psi(t)\rangle = U(t)|\psi(0)\rangle$ where $U$ is built from a product of small unitary "gates" instead of $e^{-iHt}$ directly. Each **gate** is a small unitary matrix (1- or 2-qubit, usually) — think of them as your Pauli matrices, rotation operators $e^{-i\theta\sigma/2}$, and entangling operations, all familiar from spin physics.

A circuit is drawn as horizontal wires (one per qubit) with boxes (gates) applied left to right in time order — visually similar to a Feynman-diagram-style timeline, not a physical wire.

### 0.3 Measurement, shots, and bitstrings

Just like in QM, measuring a qubit in the computational basis ($|0\rangle$/$|1\rangle$) collapses it and returns a classical bit, with probability given by the Born rule ($|\langle 0|\psi\rangle|^2$, etc). Measuring all $n$ qubits at once gives you an $n$-bit string, e.g. `01011`, sampled with probability $|\langle 01011|\psi\rangle|^2$.

Because measurement is probabilistic, you don't run the circuit once — you run it many times (each repetition is called a **shot**) and collect a histogram of bitstring outcomes. This is precisely what "sampling" means in this context, and it's the entire output you get from a quantum computer: a big list of bitstrings, not a clean wavefunction.

### 0.4 Primitives: Sampler and Estimator

Qiskit provides two "primitive" interfaces for running circuits:
- **`Sampler`**: runs a circuit and returns raw measurement bitstrings (what we use throughout these notebooks).
- **`Estimator`** (not used here): runs circuits and directly returns expectation values of an observable, handling the measurement/averaging internally.

SQD deliberately uses `Sampler`, not `Estimator`, because the whole point is to get raw bitstrings that get post-processed classically, rather than a single noisy expectation value.

### 0.5 Backends, coupling maps, and transpilation

A **backend** represents a specific piece of quantum hardware (or a simulator standing in for one). Real hardware qubits are physically wired to only some of their neighbors — this connectivity graph is the **coupling map**. IBM's chips use a "heavy-hex" lattice (hexagons with extra qubits on the edges).

A quantum circuit written abstractly (e.g., "apply a 2-qubit gate between logical orbital 3 and orbital 9") usually assumes qubits can interact with any other qubit. Real hardware can't do that directly — two far-apart qubits need a chain of SWAP operations to become adjacent, which adds noise. **Transpilation** is the process of rewriting your abstract circuit into an equivalent circuit that only uses gates and connections the hardware actually supports. The tool that does this is called a **pass manager**. The result is called an **ISA circuit** (Instruction Set Architecture circuit) — literally "the circuit as the hardware will actually execute it."

### 0.6 Why hardware is noisy (NISQ)

Current quantum computers are "NISQ" devices (Noisy Intermediate-Scale Quantum): every gate has a small error probability, and qubits lose coherence over time. This means the bitstrings you sample aren't a perfect reflection of the ideal circuit's output — some fraction will be corrupted. This is precisely the problem SQD's "configuration recovery" step is designed to mitigate (more in Part 1).

### 0.7 Ansatz / variational circuits

An **ansatz** is a parameterized circuit family $U(\theta)$ whose parameters $\theta$ you tune so that $U(\theta)|\text{reference}\rangle$ approximates some target state (here, the molecular ground state). This is directly analogous to a variational trial wavefunction in QM — you're choosing a flexible functional form and optimizing parameters, except here the "trial wavefunction" is literally implemented as a quantum circuit.

### 0.8 Second quantization crash course (for chemistry)

You've likely seen creation/annihilation operators $\hat a^\dagger_p, \hat a_p$ for bosons; fermionic ones work similarly but anticommute: $\{\hat a_p, \hat a_q^\dagger\} = \delta_{pq}$. In quantum chemistry, $\hat a^\dagger_p$ creates an electron in spin-orbital $p$. A many-electron wavefunction is written in the **occupation number representation**: a bitstring like `01011` where each bit says whether that spin-orbital is occupied (1) or empty (0) — the Pauli exclusion principle is automatically built in, since each orbital can only be occupied once.

This is the crucial link between chemistry and quantum computing: **a computational basis state of $n$ qubits (a bitstring) can represent an electron configuration** if you assign one qubit per spin-orbital. This mapping (fermionic operators → qubit operators) is called a **Jordan-Wigner (JW) transformation**, and you'll see `JW` in class names throughout the code (e.g., `PrepareHartreeFockJW`).

### 0.9 The molecular Hamiltonian

The electronic Hamiltonian of a molecule, in second quantization, is:

$$
\hat{H} = \sum_{pr\sigma} h_{pr}\, \hat a^\dagger_{p\sigma}\hat a_{r\sigma} + \frac12\sum_{prqs\sigma\tau} h_{prqs}\, \hat a^\dagger_{p\sigma}\hat a^\dagger_{q\tau}\hat a_{s\tau}\hat a_{r\sigma}
$$

$h_{pr}$ (one-electron integrals) and $h_{prqs}$ (two-electron integrals) are just numbers computed from the molecule's geometry and basis set — this is standard quantum chemistry, done by a classical package (here, **PySCF**), not anything quantum-computing specific. $\sigma,\tau$ are spin labels (up/down).

### 0.10 Hartree-Fock, active space, and CCSD (classical chemistry prerequisites)

- **Hartree-Fock (HF)**: the simplest mean-field approximation — each electron moves in the *average* field of the others. It gives you a starting set of molecular orbitals and a single reference electron configuration (fill the lowest-energy orbitals). This is *not* the true ground state (it's missing electron correlation), but it's a good, cheap starting point.
- **Active space**: instead of treating every orbital quantum-mechanically at full accuracy, you freeze the chemically inert "core" orbitals (assume always doubly occupied) and only actively simulate a handful of orbitals near the frontier. This is what makes the problem tractable at all — a real molecule can have hundreds of orbitals, and neither classical nor quantum diagonalization can handle that directly.
- **CCSD (Coupled Cluster Singles and Doubles)**: a classical, more accurate method that captures electron correlation beyond Hartree-Fock, producing "amplitudes" ($t_1$, $t_2$) describing how much each excited configuration mixes into the wavefunction. In this workflow, CCSD is *not* used to get the final answer — it's used only to get good initial parameters for the quantum circuit (see 0.11).

### 0.11 The LUCJ ansatz

**LUCJ (Local Unitary Cluster Jastrow)** is the specific ansatz circuit used here. It's inspired by coupled-cluster theory (hence reusing $t_2$ amplitudes as initial parameters) but built entirely from hardware-native gates, and — importantly — designed so that its two-qubit gates only connect *physically adjacent* qubits on the actual chip. That's why building this ansatz requires knowing the hardware's connectivity *before* constructing the circuit, unlike a generic ansatz you'd design in the abstract.

### 0.12 SQD in one paragraph (mechanics — you already got the concept)

Sample the LUCJ circuit → get bitstrings (electron configurations) → some are corrupted by noise → probabilistically "fix" corrupted ones based on your current best guess of orbital occupancies (this loop is **self-consistent configuration recovery**, sometimes called **S-CORE**) → randomly split the good configurations into batches → for each batch, build the Hamiltonian matrix restricted to just that batch's configurations (a tiny subspace compared to the full Hilbert space) and diagonalize it classically → the lowest-energy batch is your answer, and its resulting occupancies feed back into the next round of recovery.

With that vocabulary in hand, let's go through the actual code.

---

## Part 1 — Notebook: `sample-based-quantum-diagonalization.ipynb` (the N2 tutorial)

This notebook runs the SQD workflow twice: once on a small, noiseless simulator, and once on real IBM hardware with a bigger basis set. The code is nearly identical between the two, so we explain it once, in full, using the small-scale version, then note what changes for the hardware version.

### 1.1 Imports

```python
import math

import ffsim
import matplotlib.pyplot as plt
import numpy as np
import pyscf
import pyscf.cc
import pyscf.mcscf
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.primitives import StatevectorSampler
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime import SamplerV2 as Sampler
```

- `math` — used later for a combinatorics calculation (`math.comb`).
- `ffsim` — the fermionic-simulation library that builds the LUCJ ansatz circuit and knows how to prepare Hartree-Fock states as quantum circuits.
- `matplotlib.pyplot as plt` — for the result plots at the end.
- `numpy as np` — array math, and its random-number generator.
- `pyscf`, `pyscf.cc`, `pyscf.mcscf` — the classical quantum-chemistry package: `pyscf` for the base molecule/Hartree-Fock, `pyscf.cc` for CCSD, `pyscf.mcscf` for the active-space (CASCI) machinery.
- `QuantumCircuit, QuantumRegister` — Qiskit's core objects: a `QuantumRegister` is a named group of qubits, and a `QuantumCircuit` is the circuit built on top of them (Part 0.2).
- `StatevectorSampler` — a **noiseless, exact simulator** version of the Sampler primitive (Part 0.4); it computes the true probabilities via the actual statevector rather than approximating them with a noise model, then samples from them.
- `GenericBackendV2` — a synthetic backend object used purely to specify a coupling map/gate set, standing in for real hardware in the small-scale example.
- `QiskitRuntimeService`, `SamplerV2 as Sampler` — the real IBM Quantum Runtime service and its hardware Sampler, used later in the large-scale hardware example.

### 1.2 Step 1 (small-scale): Define the molecule and active space

```python
# Specify molecule properties
spin_sq = 0

# Build N2 molecule
mol = pyscf.gto.Mole()
mol.build(
    atom=[["N", (0, 0, 0)], ["N", (1.0, 0, 0)]],
    basis="sto-6g",
    symmetry="Dooh",
)
```
- `spin_sq = 0` — the value of total spin-squared $\langle S^2\rangle$ we expect for the ground state (0 = closed-shell singlet, i.e. all electrons paired). Used later as a constraint in the classical eigensolver.
- `pyscf.gto.Mole()` creates an empty "molecule" object; `.build(...)` fills it in:
  - `atom=[["N", (0,0,0)], ["N", (1.0,0,0)]]` — two nitrogen atoms, at $(0,0,0)$ and $(1.0,0,0)$ Å apart (roughly N2's equilibrium bond length).
  - `basis="sto-6g"` — a small, minimal Gaussian **basis set** (each atomic orbital approximated by 6 Gaussian functions). Small = fast but less accurate; used here just to get things running quickly.
  - `symmetry="Dooh"` — tells PySCF to exploit N2's actual molecular symmetry (linear, with a center of inversion) to simplify/speed up the calculation.

```python
# Define active space
n_frozen = 2
active_space = range(n_frozen, mol.nao_nr())
```
- `n_frozen = 2` — freeze the 2 lowest (core, 1s-like) orbitals; they stay always-doubly-occupied and aren't touched by the quantum circuit.
- `mol.nao_nr()` — total number of atomic orbitals in this basis (a PySCF method, "number of atomic orbitals, non-relativistic").
- `active_space = range(2, mol.nao_nr())` — the indices of orbitals 2 through the end are "active" (explicitly simulated).

```python
# Get molecular integrals
scf = pyscf.scf.RHF(mol).run()
```
- `pyscf.scf.RHF(mol)` sets up a **Restricted Hartree-Fock** calculation (Part 0.10) — "restricted" means each spatial orbital holds one spin-up and one spin-down electron (appropriate for a closed-shell singlet). `.run()` actually solves it, giving you the orbitals and orbital energies.

```python
norb = len(active_space)
n_electrons = int(sum(scf.mo_occ[active_space]))
n_alpha = (n_electrons + mol.spin) // 2
n_beta = (n_electrons - mol.spin) // 2
nelec = (n_alpha, n_beta)
```
- `norb` — number of active *spatial* orbitals (each holds up to 2 electrons, one of each spin).
- `scf.mo_occ` — the HF occupation number (0, 1, or 2) of each molecular orbital; summing over just the active-space indices gives the number of electrons living in the active space.
- `n_alpha`, `n_beta` — split the electron count into spin-up ("alpha") and spin-down ("beta") counts, using `mol.spin` (the $2S$ value, 0 here since N2's ground state is a singlet).
- `nelec = (n_alpha, n_beta)` — packaged as a tuple, the standard way PySCF and the SQD addon expect electron counts.

```python
cas = pyscf.mcscf.CASCI(scf, norb, nelec)
mo = cas.sort_mo(active_space, base=0)
hcore, nuclear_repulsion_energy = cas.get_h1cas(mo)
eri = pyscf.ao2mo.restore(1, cas.get_h2cas(mo), norb)
```
- `pyscf.mcscf.CASCI(scf, norb, nelec)` — sets up a **CASCI** (Complete Active Space Configuration Interaction) calculation: exact diagonalization but restricted to your chosen active space, built on top of the HF orbitals. We're using its machinery to extract the active-space integrals, not necessarily to run the full exact solve (though we do that too, next).
- `cas.sort_mo(active_space, base=0)` — reorders/selects the molecular orbitals so the active ones are grouped as expected by CASCI.
- `cas.get_h1cas(mo)` — returns the one-electron integrals $h_{pr}$ restricted to the active space (this is `hcore`, "core Hamiltonian"), plus the **nuclear repulsion energy** (the classical Coulomb repulsion between the fixed nuclei — a constant offset added to the electronic energy at the end, not part of the quantum problem itself).
- `pyscf.ao2mo.restore(1, cas.get_h2cas(mo), norb)` — gets the two-electron integrals $h_{prqs}$ (`eri`, "electron repulsion integrals") in the active space, and reshapes them into the full 4-index tensor form (`restore(1, ...)` un-compresses PySCF's internal symmetric storage format).

These `hcore` and `eri` arrays are literally the numbers $h_{pr}$ and $h_{prqs}$ from the Hamiltonian formula in section 0.9 — this is "the Hamiltonian" in the classical-chemistry sense, before anything quantum happens.

```python
# Compute exact energy using FCI
reference_energy = cas.run().e_tot
```
- `cas.run()` actually performs the exact diagonalization (**Full CI**, "Full Configuration Interaction," exact within the active space) so we have a ground-truth answer to compare SQD against later. `.e_tot` is the total energy (electronic + nuclear repulsion).

### 1.3 CCSD for ansatz initialization

```python
ccsd = pyscf.cc.CCSD(
    scf, frozen=[i for i in range(mol.nao_nr()) if i not in active_space]
).run()
t1 = ccsd.t1
t2 = ccsd.t2
```
- Runs classical CCSD (Part 0.10) with the core orbitals frozen (everything *not* in `active_space`).
- `t1`, `t2` — the singles and doubles amplitudes, which describe how much single- and double-excited configurations mix into the correlated wavefunction. These numbers will directly become the initial rotation angles/parameters of the LUCJ quantum circuit — a much better starting guess than random parameters.

### 1.4 Building the backend and the LUCJ ansatz circuit

```python
import warnings
from qiskit.transpiler import CouplingMap

warnings.formatwarning = lambda msg, *args, **kwargs: f"Warning: {msg}\n"

# Set ansatz properties
n_reps = 1
pairs_aa = [(p, p + 1) for p in range(norb - 1)]
pairs_ab = None
```
- `warnings.formatwarning = ...` just makes any warning print more cleanly (cosmetic).
- `n_reps = 1` — the LUCJ ansatz is built from repeated "layers"; this sets how many layers to use (more layers = more expressive but deeper circuit).
- `pairs_aa` — the pairs of same-spin orbitals that will be coupled by two-qubit gates: here, a simple line/chain `(0,1), (1,2), (2,3), ...` (matches the "line topology" for same-spin orbitals from Part 0.11/the LUCJ background).
- `pairs_ab = None` — the opposite-spin (alpha-beta) coupling pairs; leaving this `None` tells the pass manager (next) to figure out the best pairing automatically based on hardware connectivity.

```python
coupling_map = CouplingMap.from_heavy_hex(3)
backend = GenericBackendV2(
    coupling_map.size(),
    coupling_map=coupling_map,
    basis_gates=["cp", "xx_plus_yy", "p", "x", "swap"],
)
```
- `CouplingMap.from_heavy_hex(3)` — programmatically generates a heavy-hex connectivity graph (Part 0.5) of a given size (`3` controls how large the hex lattice is), mimicking real IBM hardware's layout without actually needing a real device.
- `GenericBackendV2(...)` — builds a fake/generic backend object with that coupling map and a chosen native **gate set**: `cp` (controlled-phase), `xx_plus_yy` (a two-qubit entangling gate that conserves particle number — important, since it respects the fermionic symmetry), `p` (phase gate), `x` (bit flip / Pauli-X), `swap` (swaps two qubits' states, used to move information across non-adjacent qubits).

```python
pass_manager, pairs_ab = ffsim.qiskit.generate_lucj_pass_manager(
    backend=backend,
    norb=norb,
    connectivity="heavy-hex",
    interaction_pairs=(pairs_aa, pairs_ab),
    optimization_level=3,
)
```
- This single call does two things at once: (1) builds a **pass manager** (Part 0.5) specialized for compiling LUCJ circuits onto this specific backend's heavy-hex layout, and (2) figures out and returns the actual `pairs_ab` (which alpha/beta orbital pairs *can* be connected given the hardware's "zig-zag" layout — see Part 0.11 and the LUCJ background). `optimization_level=3` requests the most aggressive circuit optimization the transpiler offers.

```python
ucj_op = ffsim.UCJOpSpinBalanced.from_t_amplitudes(
    t2=t2,
    t1=t1,
    n_reps=n_reps,
    interaction_pairs=(pairs_aa, pairs_ab),
    optimize=True,
    options=dict(maxiter=1000),
)
```
- `ffsim.UCJOpSpinBalanced` — the "spin-balanced" variant of the Unitary Cluster Jastrow operator, appropriate since our molecule is closed-shell (equal alpha/beta treatment).
- `.from_t_amplitudes(...)` builds this operator directly from the classical CCSD amplitudes (Part 1.3), rather than starting from random parameters.
- `optimize=True` — turns on the "compressed" double-factorization mentioned in the notebook: a numerical optimization that finds a more compact (shallower) circuit representation of the same amplitudes, at the cost of some approximation.
- `options=dict(maxiter=1000)` — caps that optimization at 1000 iterations, purely so the tutorial doesn't run indefinitely.

Note: `ucj_op` here is still an abstract mathematical operator object (not yet a `QuantumCircuit`) — the actual circuit gets built in the next cell.

```python
qubits = QuantumRegister(2 * norb, name="q")
circuit = QuantumCircuit(qubits)

circuit.append(ffsim.qiskit.PrepareHartreeFockJW(norb, nelec), qubits)

circuit.append(ffsim.qiskit.UCJOpSpinBalancedJW(ucj_op), qubits)
circuit.measure_all()
```
- `QuantumRegister(2 * norb, ...)` — allocates $2\times\text{norb}$ qubits: one qubit per spin-orbital (recall each spatial orbital has an alpha and a beta spin-orbital — Part 0.8).
- `QuantumCircuit(qubits)` — creates an empty circuit on those qubits.
- `PrepareHartreeFockJW(norb, nelec)` — a sub-circuit that prepares the **Hartree-Fock reference state** directly as a quantum state (i.e., flips the qubits corresponding to occupied HF orbitals to $|1\rangle$), using the Jordan-Wigner mapping (Part 0.8). This is our "reference state" from Part 0.7.
- `UCJOpSpinBalancedJW(ucj_op)` — converts the abstract `ucj_op` operator into an actual sequence of quantum gates (again via Jordan-Wigner) and appends it — this is the ansatz $U(\theta)$ applied to the reference state.
- `circuit.measure_all()` — adds measurement operations on every qubit at the end (Part 0.3), so running this circuit will yield bitstrings.

At this point, `circuit` is the full abstract LUCJ circuit: prepare HF state → apply the (CCSD-initialized) LUCJ unitary → measure everything.

### 1.5 Step 2: Transpile to an ISA circuit

```python
isa_circuit = pass_manager.run(circuit)
print(f"Gate counts: {isa_circuit.count_ops()}")
```
- `pass_manager.run(circuit)` — runs the specialized pass manager built earlier (1.4) on our abstract circuit, producing the **ISA circuit** (Part 0.5): equivalent, but using only the target backend's native gates and only connecting qubits that are actually adjacent.
- `isa_circuit.count_ops()` — a dictionary of how many of each gate type the final circuit contains, printed as a sanity check / resource estimate (more gates ≈ more opportunities for hardware noise).

### 1.6 Step 3: Execute (sample the circuit)

```python
rng = np.random.default_rng()
sampler = StatevectorSampler(seed=rng)
job = sampler.run([isa_circuit], shots=100_000)
```
- `np.random.default_rng()` — a NumPy random number generator instance, used both for sampling and later for SQD's internal randomness (so results are reproducible if you fix a seed).
- `StatevectorSampler(seed=rng)` — the exact, noiseless simulator Sampler (Part 1.1) — it computes exact probabilities from the true statevector, then samples from that distribution using `rng`.
- `sampler.run([isa_circuit], shots=100_000)` — submits a **job**: run this one circuit and take 100,000 shots (Part 0.3). Note the list `[isa_circuit]` — primitives accept a list of circuits ("PUBs," Primitive Unified Blocs) even when running just one.

```python
primitive_result = job.result()
pub_result = primitive_result[0]
```
- `.result()` blocks until the job finishes and returns results for every circuit submitted.
- `primitive_result[0]` — since we only submitted one circuit, grab its result specifically (`pub_result`), which contains the measured bitstring data.

### 1.7 Step 4: Post-process — checking sample validity

```python
def is_valid_bitstring(
    bitstring: str, norb: int, nelec: tuple[int, int]
) -> bool:
    n_alpha, n_beta = nelec
    return (
        len(bitstring) == 2 * norb
        and bitstring[norb:].count("1") == n_alpha
        and bitstring[:norb].count("1") == n_beta
    )
```
- Defines a helper function. Since qubits 0..norb-1 represent one spin sector and norb..2*norb-1 the other, this function checks: (a) the bitstring is the right length, and (b) each half has exactly the right number of 1s (i.e. the right **Hamming weight** — Part 0.12 background) to match the expected alpha/beta electron counts. This encodes the physical fact that the true Hamiltonian conserves particle number in each spin sector — any sampled bitstring violating this is a sign of hardware/sampling noise.

```python
bit_array = pub_result.data.meas
num_valid = sum(
    is_valid_bitstring(b, norb, nelec) for b in bit_array.get_bitstrings()
)
valid_fraction = num_valid / bit_array.num_shots
print(f"Fraction of sampled configurations that are valid: {valid_fraction}")
```
- `pub_result.data.meas` — the measured bitstring data object (named `meas` because that was the default register name from `measure_all()`).
- `bit_array.get_bitstrings()` — returns the list of all sampled bitstrings (one per shot).
- Counts how many are valid per the function above, divides by total shots, and prints the fraction. On the noiseless simulator, this should be 1.0 (100% valid) since there's no noise to corrupt anything.

```python
expected_fraction_random = (
    math.comb(norb, n_alpha) * math.comb(norb, n_beta) / 2 ** (2 * norb)
)
print(
    f"Expected fraction of valid configurations from uniformly random bitstrings: "
    f"{expected_fraction_random}"
)
```
- A baseline comparison: `math.comb(norb, n_alpha)` is "n choose k" — the number of ways to place `n_alpha` electrons among `norb` orbitals — same for beta. Multiplying gives the total number of *valid* configurations, and dividing by $2^{2\cdot\text{norb}}$ (total possible bitstrings) gives the fraction you'd expect to be valid if you were just guessing bitstrings completely at random. This is the number the guide/report referenced as ~0.0001% for the hardware run — comparing your circuit's actual valid fraction against this tells you whether the quantum circuit is doing anything useful at all.

### 1.8 The SQD diagonalization call itself

```python
from functools import partial
from qiskit_addon_sqd.fermion import (
    SCIResult,
    diagonalize_fermionic_hamiltonian,
    solve_sci_batch,
)

energy_tol = 1e-3
occupancies_tol = 1e-3
max_iterations = 5

num_batches = 3
samples_per_batch = 300
symmetrize_spin = True
carryover_threshold = 1e-4
max_cycle = 200
```
- Imports the actual SQD algorithm from the `qiskit-addon-sqd` package: `diagonalize_fermionic_hamiltonian` (the main driver function, implementing the whole loop from Part 0.12), `solve_sci_batch` (the classical eigensolver used inside each batch), and `SCIResult` (a data class describing one batch's result — used for type hinting the callback).
- `energy_tol`, `occupancies_tol` — convergence thresholds: if the energy or occupancies change by less than these amounts between iterations, the algorithm can stop early.
- `max_iterations = 5` — hard cap on configuration-recovery rounds.
- `num_batches = 3` — how many random subsets of configurations to diagonalize per iteration.
- `samples_per_batch = 300` — how many bitstrings go into each subset/subspace.
- `symmetrize_spin = True` — enforce that the resulting wavefunction has the correct spin symmetry.
- `carryover_threshold = 1e-4` — configurations with amplitude below this are dropped when moving results between iterations (keeps the subspace manageable).
- `max_cycle = 200` — max number of iterations for the classical eigensolver (Davidson algorithm) used inside each batch's diagonalization.

```python
initial_occupancies = (
    np.array([1] * n_alpha + [0] * (norb - n_alpha)),
    np.array([1] * n_beta + [0] * (norb - n_beta)),
)
```
- Builds the starting guess for average orbital occupancies: the Hartree-Fock configuration itself (lowest `n_alpha`/`n_beta` orbitals fully occupied, rest empty), as a reasonable first guess for the configuration-recovery loop (Part 0.12).

```python
sci_solver = partial(solve_sci_batch, spin_sq=0.0, max_cycle=max_cycle)
```
- `functools.partial` pre-fills some arguments of `solve_sci_batch` (the per-batch classical eigensolver) — here fixing `spin_sq=0.0` (require the correct total spin, matching `spin_sq` from way back in 1.2) and the iteration cap — so it can be passed as a ready-to-call function into the main SQD driver.

```python
result_history = []

def callback(results: list[SCIResult]):
    result_history.append(results)
    iteration = len(result_history)
    print(f"Iteration {iteration}")
    for i, result in enumerate(results):
        print(f"\tSubsample {i}")
        print(f"\t\tEnergy: {result.energy + nuclear_repulsion_energy}")
        print(
            f"\t\tSubspace dimension: {np.prod(result.sci_state.amplitudes.shape)}"
        )
```
- `result_history = []` — a list to accumulate every iteration's results, for later plotting.
- `callback(results)` — a function you hand to `diagonalize_fermionic_hamiltonian`; it gets called automatically after each configuration-recovery iteration with that iteration's list of per-batch results. It appends to `result_history` and prints diagnostics: each batch's energy (electronic energy + the nuclear repulsion constant from 1.2) and the subspace dimension (how many basis states that batch's diagonalization actually spanned — `np.prod(result.sci_state.amplitudes.shape)` multiplies the alpha and beta dimensions, since the full subspace dimension is their product).

```python
result = diagonalize_fermionic_hamiltonian(
    hcore,
    eri,
    bit_array,
    samples_per_batch=samples_per_batch,
    norb=norb,
    nelec=nelec,
    num_batches=num_batches,
    energy_tol=energy_tol,
    occupancies_tol=occupancies_tol,
    max_iterations=max_iterations,
    sci_solver=sci_solver,
    symmetrize_spin=symmetrize_spin,
    initial_occupancies=initial_occupancies,
    carryover_threshold=carryover_threshold,
    callback=callback,
    seed=rng,
)
```
This is the actual SQD algorithm call (Part 0.12), tying everything together:
- `hcore, eri` — the classical Hamiltonian integrals from Section 1.2 (this is literally where "the Hamiltonian" enters the SQD math — everything before this was either building the sampling circuit, or building the Hamiltonian data itself).
- `bit_array` — the raw sampled bitstrings from Section 1.6/1.7.
- All the SQD/eigensolver options defined above.
- `seed=rng` — reuses the same random generator for reproducibility.

Internally, this call runs the whole loop from Part 0.12: correct invalid bitstrings using the current occupancy estimate → batch the valid configurations → diagonalize each batch's projected Hamiltonian with `sci_solver` → call `callback` → update occupancies from the lowest-energy batch → repeat, up to `max_iterations` times or until the tolerances are satisfied.

```python
final_energy = result.energy + nuclear_repulsion_energy
energy_error = final_energy - reference_energy
print(f"Final energy: {final_energy}")
print(f"Final energy error: {energy_error}")
```
- `result.energy` — the best (lowest) electronic energy found across all iterations/batches.
- Adding `nuclear_repulsion_energy` gives the total molecular energy (Part 1.2 explained why this constant is added separately).
- `energy_error` compares this to the exact `reference_energy` computed via FCI back in Section 1.2 — the whole point of running this on the small system first is to have a trustworthy number to check SQD against.

### 1.9 Visualizing results

```python
x1 = range(len(result_history))
min_e = [
    min(result, key=lambda res: res.energy).energy + nuclear_repulsion_energy
    for result in result_history
]
e_diff = [abs(e - reference_energy) for e in min_e]
yt1 = [1.0, 1e-1, 1e-2, 1e-3, 1e-4]
chem_accuracy = 0.001
```
- `x1` — one x-axis point per iteration.
- `min_e` — for each iteration's list of batch results, take the batch with the lowest energy (`min(..., key=lambda res: res.energy)`), and record its total energy.
- `e_diff` — absolute error against the FCI reference at each iteration — this is what gets plotted to show convergence.
- `yt1` — the tick values for a log-scale y-axis.
- `chem_accuracy = 0.001` — 1 milli-Hartree, the conventional threshold (~1.6 mHa is "1 kcal/mol," often rounded to ~1 mHa) below which a result is considered "chemically accurate."

```python
y2 = np.sum(result.orbital_occupancies, axis=0)
x2 = range(len(y2))
```
- `result.orbital_occupancies` — from the *final* iteration's winning batch, the average occupation of each spin-orbital; summing over the spin axis (`axis=0`, combining alpha and beta) gives the average occupancy of each *spatial* orbital, which ranges from 0 (empty) to 2 (fully occupied by both spins).

```python
fig, axs = plt.subplots(1, 2, figsize=(12, 6))

axs[0].plot(x1, e_diff, label="energy error", marker="o")
axs[0].set_xticks(x1)
axs[0].set_xticklabels(x1)
axs[0].set_yticks(yt1)
axs[0].set_yticklabels(yt1)
axs[0].set_yscale("log")
axs[0].set_ylim(1e-4)
axs[0].axhline(
    y=chem_accuracy, color="#BF5700", linestyle="--", label="chemical accuracy",
)
axs[0].set_title("Approximated Ground State Energy Error vs SQD Iterations")
axs[0].set_xlabel("Iteration Index", fontdict={"fontsize": 12})
axs[0].set_ylabel("Energy Error (Ha)", fontdict={"fontsize": 12})
axs[0].legend()

axs[1].bar(x2, y2, width=0.8)
axs[1].set_xticks(x2)
axs[1].set_xticklabels(x2)
axs[1].set_title("Avg Occupancy per Spatial Orbital")
axs[1].set_xlabel("Orbital Index", fontdict={"fontsize": 12})
axs[1].set_ylabel("Avg Occupancy", fontdict={"fontsize": 12})

plt.tight_layout()
plt.show()
```
Standard matplotlib plotting, nothing quantum-specific:
- `plt.subplots(1, 2, ...)` creates one figure with two side-by-side panels (`axs[0]`, `axs[1]`).
- Left panel: energy error vs. iteration, log-scale y-axis, with a dashed horizontal line marking the chemical-accuracy threshold — visually, does the SQD curve dip below the dashed line?
- Right panel: a bar chart of average occupancy per spatial orbital — you'd expect it to look step-like (orbitals below the Fermi level near 2, above it near 0), with any fractional values indicating correlation effects captured beyond plain Hartree-Fock.
- `plt.tight_layout(); plt.show()` — cosmetic layout cleanup and rendering.

### 1.10 The large-scale hardware run — what's different

Section "Large-scale hardware example" (cells 25-27) repeats *exactly* the same four-step structure, with these changes:

1. **Basis set**: `basis="cc-pvdz"` instead of `"sto-6g"` — a much larger, more accurate basis, giving `norb` around 26 active orbitals instead of 8. This is why the notebook can no longer run exact FCI for a reference energy — it's too large — so `reference_energy = -109.22802921665716` is simply hard-coded (computed separately, offline, using a more scalable classical method).
2. **Backend**: instead of the synthetic `GenericBackendV2`, it uses real hardware:
   ```python
   service = QiskitRuntimeService()
   backend = service.least_busy(operational=True, simulator=False, min_num_qubits=133)
   ```
   `QiskitRuntimeService()` connects to your real IBM Quantum account; `.least_busy(...)` automatically picks whichever available real QPU (non-simulator, ≥133 qubits) currently has the shortest queue.
3. **Sampler**: uses the real hardware Sampler,
   ```python
   sampler = Sampler(mode=backend)
   sampler.options.environment.job_tags = ["TUT_SQD"]
   job = sampler.run([isa_circuit], shots=100_000)
   ```
   instead of `StatevectorSampler`. `job_tags` is just a label to help you find this job later in your account's job history. Because this runs on noisy real hardware, the "fraction of valid bitstrings" here is meaningfully less than 1.0 (as discussed in your earlier report — around 2%), which is exactly the regime where configuration recovery earns its keep.
4. Everything else — the SQD call, plotting — is identical code, just operating on noisier input data, so convergence is slower and the final error is larger (as you already summarized: ~40 mHa vs. the ~1.6 mHa chemical-accuracy target).

---

## Part 2 — Notebook: `function-template-chemistry-workflow.ipynb`

This notebook doesn't run SQD directly in the notebook — it shows you how to **deploy** the *entire* pipeline above (Hartree-Fock → CCSD → LUCJ → transpile → sample → SQD, plus an added implicit-solvent step) as a remote, reusable service using **Qiskit Serverless**, then call it with a methanol example instead of N2. Conceptually this is "the same four steps as Part 1, wrapped up so you don't have to write the notebook code yourself every time."

### 2.1 What's new here conceptually: implicit solvent (IEF-PCM)

Real molecules are often dissolved in a solvent (here, methanol in water). Explicitly simulating hundreds of solvent molecules quantum-mechanically is infeasible, so **IEF-PCM (Integral Equation Formalism Polarizable Continuum Model)** instead treats the solvent as a smooth, continuous dielectric medium surrounding the solute. The solvent polarizes in response to the solute's electron distribution, which adds a correction term to the solute's effective Hamiltonian, and the workflow reports a **solvation free energy** as an extra output alongside the SQD ground-state energy.

### 2.2 Authentication

```python
from qiskit_ibm_catalog import QiskitServerless

serverless = QiskitServerless()
```
- `qiskit_ibm_catalog` is the client library for **Qiskit Serverless**, IBM's remote-execution platform for these packaged "Functions."
- `QiskitServerless()` with no arguments relies on previously saved credentials (via `QiskitServerless.save_account(...)`, shown in the markdown but not run here) to authenticate; this object (`serverless`) is your handle for uploading and running functions remotely.

### 2.3 Packaging and uploading the function template

```python
from qiskit_ibm_catalog import QiskitFunction

template = QiskitFunction(
    title="sqd_pcm_template",
    entrypoint="sqd_pcm_entrypoint.py",
    working_dir="./source_files/",
    dependencies=[
        "ffsim==0.0.54",
        "pyscf==2.9.0",
        "qiskit_addon_sqd==0.10.0",
    ],
)
print(template)
```
- `title` — the name you'll use to refer to this function later.
- `entrypoint="sqd_pcm_entrypoint.py"` — the actual Python script (not shown in this notebook, but implied to exist in `working_dir`) containing the real Steps 1-4 code (essentially a script version of everything in Part 1, plus the PCM solvent step), structured with a `if __name__ == "__main__":` block that reads inputs and produces outputs.
- `working_dir="./source_files/"` — a local folder whose entire contents (the entrypoint script plus any helper modules it imports) get uploaded together.
- `dependencies=[...]` — exact package versions to install in the remote execution environment, so the job runs with a known, reproducible software stack.
- This `QiskitFunction` object is purely local/descriptive at this point — nothing has been sent anywhere yet.

```python
serverless.upload(template)
```
- Actually ships the entrypoint script, working directory, and dependency list to IBM's remote cluster.

```python
serverless.list()
```
- Queries your account for all currently-uploaded functions, letting you confirm the upload succeeded (and see what else you have deployed).

### 2.4 Loading and running the deployed template

```python
template = serverless.load("sqd_pcm_template")
print(template)
```
- Fetches a fresh handle to the function by name — note this doesn't need the source code again; the platform already has it from the upload step. This is the normal way you'd use the function in a *separate* session later on, without re-uploading.

### 2.5 Specifying the chemistry problem — the `molecule` dictionary

```python
molecule = {
    "atom": """
    O -0.04559 -0.75076 -0.00000;
    C -0.04844 0.65398 -0.00000;
    H 0.85330 -1.05128 -0.00000;
    H -1.08779 0.98076 -0.00000;
    H 0.44171 1.06337 0.88811;
    H 0.44171 1.06337 -0.88811
    """,
    "basis": "cc-pvdz",
    "spin": 0,
    "charge": 0,
    "verbosity": 0,
    "number_of_active_orb": 12,
    "number_of_active_alpha_elec": 7,
    "number_of_active_beta_elec": 7,
    "avas_selection": [
        "%d O %s" % (k, x) for k in [0] for x in ["2s", "2px", "2py", "2pz"]
    ]
    + ["%d C %s" % (k, x) for k in [1] for x in ["2s", "2px", "2py", "2pz"]]
    + ["%d H 1s" % k for k in [2, 3, 4, 5]],
}
```
- `"atom"` — a PySCF-style geometry string: one atom per line, `element x y z` (in Å), semicolon-separated — this is methanol (CH₃OH): one O, one C, four H atoms, each with 3D coordinates.
- `"basis": "cc-pvdz"` — same style of basis set as the hardware N2 example in Part 1.
- `"spin": 0`, `"charge": 0` — closed-shell, neutral molecule.
- `"verbosity": 0` — controls how much PySCF logs internally (0 = quiet).
- `"number_of_active_orb": 12`, `"number_of_active_alpha_elec": 7`, `"number_of_active_beta_elec": 7` — directly specifies the active space: 12 orbitals, 7 alpha + 7 beta electrons (14 electrons total) — this is the "(14e, 12o)" active space mentioned in your earlier report.
- `"avas_selection"` — a list of atomic-orbital labels used by the **AVAS** (Atomic Valence Active Space) method (Part 0.10-adjacent — a more automated/principled way of choosing *which* orbitals go into the active space, rather than hand-picking by energy ordering as in Part 1). The list comprehension programmatically builds strings like `"0 O 2s"`, `"0 O 2px"`, etc., meaning "the 2s and three 2p orbitals of atom index 0 (oxygen)," similarly for carbon (index 1), plus the 1s orbitals of all four hydrogens (indices 2-5). This tells AVAS: "build the active space out of the valence orbitals of O, C, and the H 1s orbitals" — chemically, this captures the $\sigma/\sigma^*$ bonding framework and lone pairs, as mentioned in the notebook's introduction.

### 2.6 Solvent, LUCJ, and SQD option dictionaries

```python
solvent_options = {
    "method": "IEF-PCM",
    "eps": 78.3553,
}
```
- `"method": "IEF-PCM"` — selects the specific implicit-solvent model (Section 2.1); other options exist (COSMO, C-PCM, SS(V)PE) but aren't used here.
- `"eps": 78.3553` — the solvent's **dielectric constant** — this specific value is water's, at room temperature. This single number is what tells the model "the solute is surrounded by water," as opposed to some other solvent.

```python
lucj_options = {
    "initial_layout": [0, 14, 18, 19, 20, 33, 39, 40, 41, 53, 60, 61,
                        2, 3, 4, 15, 22, 23, 24, 34, 43, 44, 45, 54],
    "dynamical_decoupling_choice": True,
    "twirling_choice": True,
    "number_of_shots": 200000,
    "optimization_level": 2,
}
```
- `"initial_layout"` — an explicit list of **physical qubit indices** on the target chip, in order, telling the transpiler exactly which qubit each logical spin-orbital should map to. Per the notebook: the first 12 entries are the alpha-spin orbitals, the last 12 are beta-spin — chosen (as explained in the guide) to trace the "main diagonal" of the specific hardware chip (Eagle R3), matching the zig-zag pattern from Part 0.11/1.4. Unlike Part 1, where the pass manager figured this out automatically via `generate_lucj_pass_manager`, here it's supplied explicitly — a more manual, hand-tuned alternative.
- `"dynamical_decoupling_choice": True` — enables **dynamical decoupling**, a hardware-level error-suppression technique that inserts extra pulses on idle qubits to average out certain noise sources (this is a standard Qiskit Runtime option, not something built by hand in this notebook).
- `"twirling_choice": True` — enables **Pauli twirling**, another standard error-suppression technique that randomizes certain gate errors so they average toward a more predictable, easier-to-mitigate form.
- `"number_of_shots": 200000` — number of circuit measurements (Part 0.3), chosen per the guidelines discussed in your earlier report (200k shots for a 16-18 orbital system).
- `"optimization_level": 2` — the transpiler aggressiveness (Part 0.5), a middle setting between speed and compiled-circuit quality.

```python
sqd_options = {
    "sqd_iterations": 3,
    "number_of_batches": 10,
    "samples_per_batch": 1000,
    "max_davidson_cycles": 200,
}
```
- `"sqd_iterations": 3` — number of self-consistent configuration-recovery rounds (compare to `max_iterations=5` in Part 1 — same concept, different name/value here).
- `"number_of_batches": 10` — more batches than the N2 tutorial's `num_batches=3`, giving better statistics on the lowest-energy result, at added classical computational cost.
- `"samples_per_batch": 1000` — larger than the N2 example's 300, appropriate for methanol's bigger active space (12 orbitals vs. 8).
- `"max_davidson_cycles": 200` — same role as `max_cycle` in Part 1: cap on the classical eigensolver's (Davidson algorithm) internal iterations per batch.

```python
backend_name = "ibm_sherbrooke"
```
- Explicitly names a specific IBM QPU to run on (rather than `least_busy()` auto-selection as in Part 1's hardware example).

### 2.7 Submitting and monitoring the job

```python
job = template.run(
    backend_name=backend_name,
    molecule=molecule,
    solvent_options=solvent_options,
    lucj_options=lucj_options,
    sqd_options=sqd_options,
)
print(job.job_id)
```
- `template.run(...)` submits an asynchronous job to the remote cluster with all the option dictionaries as keyword arguments — internally, this is exactly what feeds `arguments["molecule"]`, `arguments["lucj_options"]`, etc. inside the (unseen) `sqd_pcm_entrypoint.py` script, which then executes the Part-1-style four-step pipeline itself, remotely.
- `job.job_id` — a unique identifier you can use to check on or retrieve this specific job later, even from a different session.

```python
import time

t0 = time.time()
status = job.status()
if status == "QUEUED":
    print(f"time = {time.time()-t0:.2f}, status = QUEUED")
while True:
    status = job.status()
    if status == "QUEUED":
        continue
    print(f"time = {time.time()-t0:.2f}, status = {status}")
    if status == "DONE" or status == "ERROR":
        break
```
- A simple polling loop: repeatedly checks `job.status()` (which might return `"QUEUED"`, `"RUNNING"`, `"DONE"`, `"ERROR"`, etc.) and prints an update once the status changes away from `"QUEUED"`, breaking out once the job is finished (successfully or with an error). `time.time()-t0` just tracks elapsed wall-clock time for display.

```python
print(job.logs())
```
- Streams whatever the remote script has logged so far via Python's `logging` module (`logger.info(...)` calls inside `sqd_pcm_entrypoint.py`) — useful for watching progress (e.g., seeing per-iteration SQD energies) even before the job fully completes.

### 2.8 Retrieving results

```python
result = job.result()
result
```
- `job.result()` blocks until the job is `"DONE"`, then returns the structured output dictionary from the remote script — this would include things like the lowest-energy batch's total energy, the solvation free energy, and metadata (including a resource-usage summary: how much QPU time and classical CPU time the job consumed).

```python
print(job.logs())
```
- After completion, fetches the *entire* accumulated log output (as opposed to the partial logs seen mid-run in Section 2.7).

---

## Part 3 — Quick-Reference Glossary

| Term | Meaning |
|---|---|
| Qubit | 2-level quantum system, the basic unit of quantum information |
| Shot | One repetition of running-and-measuring a circuit |
| Bitstring | The classical outcome of measuring all qubits once |
| Sampler | Qiskit primitive that returns raw measured bitstrings |
| Backend | A specific (real or simulated) quantum device |
| Coupling map | Which physical qubits are wired to which others |
| Transpilation / pass manager | Rewriting a circuit to match hardware constraints |
| ISA circuit | The transpiled, hardware-executable version of a circuit |
| Ansatz | A parameterized circuit meant to approximate a target state |
| Active space | The subset of orbitals explicitly, quantum-mechanically simulated |
| Hartree-Fock (HF) | Mean-field reference calculation; starting point for everything else |
| CCSD / $t_1,t_2$ amplitudes | Classical correlated method, used here only to initialize the ansatz |
| LUCJ | The specific hardware-efficient ansatz circuit used for SQD |
| Jordan-Wigner (JW) | The mapping from fermionic operators to qubit operators |
| SQD | The overall hybrid quantum/classical ground-state-finding algorithm |
| Self-consistent configuration recovery (S-CORE) | SQD's iterative noise-correction loop |
| Davidson algorithm | The classical eigensolver used inside each SQD batch |
| IEF-PCM | Implicit-solvent model used in the function-template workflow |
| Qiskit Serverless / Qiskit Function | IBM's platform for deploying reusable remote quantum workflows |

---

