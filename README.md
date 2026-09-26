# SQD: Sample-Based Quantum Diagonalization

This repo implements and studies a Sample-based Quantum Diagonalization (SQD)
workflow, run on both a noiseless simulator and real IBM Quantum hardware.

## Repo structure

```
code/
  hamiltonianCode.ipynb / .py   Parses the Hamiltonian file into a Qiskit
                                 SparsePauliOp and extracts its metadata
                                 (qubit count, electron count, spin,
                                 reference energy) directly from the file.
  N2ex.ipynb                    Early exploration, following IBM's N2
                                 tutorial (ref/), before working with the
                                 actual assigned Hamiltonian.
  simVShardware.ipynb           Main workflow: builds the ansatz, runs SQD
                                 on both simulator and hardware, and produces
                                 all analysis/plots.

hamiltonian/
  H2O_CAS4e4o_JW_Pauli_Hamiltonian_HERMITIAN.txt
                                 The given Hamiltonian: one Pauli term per
                                 line, plus header metadata (electron count,
                                 spin, qubit ordering, reference energy).

ref/
  function-template-chemistry-workflow.ipynb
  sample-based-quantum-diagonalization.ipynb
                                 IBM's original tutorial notebooks this
                                 project is based on.
  notes.md                      Working notes.

results/                        Saved plots and run output (see below).

weekly_reports/                 Weekly progress reports (SQD_week1-6.pdf),
                                 documenting the project's development in
                                 detail week by week.
```

## Workflow

The pipeline has four stages, run in `code/simVShardware.ipynb`:

1. **Parse the Hamiltonian** (`hamiltonianCode.py`). Reads the `.txt` file
   into a `SparsePauliOp`, and separately extracts metadata (qubit count,
   `n_alpha`/`n_beta`, reference energy, qubit ordering) from its header
   comments — nothing about the molecule is hardcoded. The Hamiltonian's
   qubit ordering is also remapped from *interleaved* (as given) to
   *blocked* (alpha qubits, then beta qubits), since that's what
   `qiskit-addon-sqd`'s routines assume.

2. **Build and optimize the ansatz.** No integrals/FCIDUMP were supplied
   for this system, so CCSD-amplitude seeding (as IBM's tutorial uses)
   isn't possible. Instead, the state-preparation circuit uses `ffsim`'s
   real LUCJ architecture, with parameters optimized directly against the
   exact Hamiltonian. The number of repeated LUCJ layers (`n_reps`) is
   chosen by sweeping candidates and picking the best accuracy/depth
   trade-off in code, rather than by hand.

3. **Sample the circuit.** The same optimized circuit is run on both a
   noiseless `StatevectorSampler` and real IBM Quantum hardware (via
   `qiskit-ibm-runtime`), each transpiled against its own backend. Job ID,
   physical qubit layout, raw counts, and backend calibration are saved for
   the hardware run.

4. **Run SQD.** Sampled bitstrings go through self-consistent configuration
   recovery, batching, and subspace diagonalization
   (`qiskit_addon_sqd.qubit`/`.configuration_recovery`/`.subsampling`),
   iterating until the energy estimate converges. Additional analysis
   (shot-dependence via resampling existing data, and a `samples_per_batch`
   sweep) is done without spending extra QPU time.

## Results

`results/` contains the key plots and output from the current run:
- `PrePostSQDExact.png` — ansatz-only vs. post-SQD vs. exact energy.
- `simVShardware10kshots.png` — simulator vs. hardware comparison at matched shot counts.
- `simVShardware.txt` — contains the entire output and job metadata for the simulator and hardware wherever it is relevant.
- `SQDErrVSsubspaceSize.png` — SQD error vs. `samples_per_batch`.

See `weekly_reports/` for the full narrative of how this was built,
including bugs found and fixed along the way.

## Setup

Credentials (IBM Quantum API token and instance CRN) are read from
environment variables / prompted at runtime — never hardcoded or committed.
See `.env` (gitignored) and the credentials cell in `simVShardware.ipynb`
for how these are supplied.

## References and acknowledgements
 
- IBM Quantum, ["Sample-based quantum diagonalization of a chemistry
  Hamiltonian"](https://quantum.cloud.ibm.com/docs/en/tutorials/sample-based-quantum-diagonalization)
  — the N2 tutorial this project is based on (`ref/`).
- IBM Quantum, ["Build a Qiskit Function for chemistry
  simulation"](https://quantum.cloud.ibm.com/docs/en/guides/function-template-chemistry-workflow)
  (`ref/`).
- [`qiskit-addon-sqd`](https://github.com/Qiskit/qiskit-addon-sqd) —
  configuration recovery, subsampling, and subspace diagonalization.
- [`ffsim`](https://github.com/qiskit-community/ffsim) — the LUCJ ansatz
  construction and fermionic circuit tools used here.
- [Qiskit](https://www.ibm.com/quantum/qiskit) / `qiskit-ibm-runtime` for
  circuit construction, transpilation, and hardware execution.
- Thanks to Prof. Indrakshi Raychowdhury for supplying the Hamiltonian, hardware access
  through her classroom account, and detailed feedback that shaped several
  of this project's later weeks (see `weekly_reports/`).