# SQD: Sample-Based Quantum Diagonalization

This repo implements and studies a Sample-based Quantum Diagonalization (SQD)
workflow for an assigned 8-qubit H2O CAS(4e,4o) Hamiltonian, run on both a
noiseless simulator and real IBM Quantum hardware, and compared against the
exact diagonalization / CASSCF reference energy (-76.11669094458742 Ha).

Two state-preparation routes are included:

1. **Baseline:** a LUCJ ansatz whose parameters are optimized from a random
   start directly against the Hamiltonian (no CCSD information).
2. **CCSD-seeded (current main result):** a LUCJ ansatz initialized from
   supplied CCSD amplitudes and then *variationally minimized* against the
   Hamiltonian, as specified by the course instructions in
   `hamiltonian/H2O_CCSD_seeded_LUCJ_instructions.md` and the follow-up
   guidance from Prof. Raychowdhury.

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
  simVShardware.ipynb           Baseline workflow (random-start LUCJ): builds
                                 the ansatz, runs SQD on simulator and
                                 hardware, and produces the analysis/plots.
  validation.ipynb              Validation of the raw CCSD-seeded LUCJ circuit
                                 (zero-amplitude control, ordering and
                                 particle-number checks, sign/transpose
                                 tests). This is the check that showed the
                                 un-minimized seed is NOT accurate by itself.
  SQD_CCSDseededLUCJ.ipynb      Main CCSD-seeded workflow: seed from the
                                 amplitudes, variationally minimize the LUCJ
                                 parameters, verify ordering/sector, then run
                                 SQD on the simulator and on hardware.

hamiltonian/
  H2O_CAS4e4o_JW_Pauli_Hamiltonian_HERMITIAN.txt
                                 The given Hamiltonian: one Pauli term per
                                 line, plus header metadata (electron count,
                                 spin, qubit ordering, reference energy).
  H2O_CAS4e4o_CCSD_t_amplitudes.npz / .txt
                                 Supplied CCSD t1/t2 amplitudes for the same
                                 system (.npz for code, .txt human-readable).
  H2O_CCSD_seeded_LUCJ_instructions.md
                                 The supplied instructions for CCSD-seeded
                                 LUCJ.

ref/
  function-template-chemistry-workflow.ipynb
  sample-based-quantum-diagonalization.ipynb
                                 IBM's original tutorial notebooks this
                                 project is based on.
  notes.md                      Working notes.

results/                        Saved plots, run output and optimized
                                 parameters (see below).

weekly_reports/                 Weekly progress reports (weeks 1-7, 10),
                                 documenting the project's development in
                                 detail week by week.
```

## Workflow

### Baseline pipeline (`code/simVShardware.ipynb`)

1. **Parse the Hamiltonian** (`hamiltonianCode.py`). Reads the `.txt` file
   into a `SparsePauliOp`, and separately extracts metadata (qubit count,
   `n_alpha`/`n_beta`, reference energy, qubit ordering) from its header
   comments, so nothing about the molecule is hardcoded. The qubit ordering
   is remapped from *interleaved* (as given) to *blocked* (alpha qubits, then
   beta qubits), since that is what `qiskit-addon-sqd` and `ffsim` assume.
2. **Build and optimize the ansatz.** A LUCJ circuit (`ffsim`) with
   parameters optimized from a random start against the Hamiltonian;
   `n_reps` is chosen by sweeping candidates in code.
3. **Sample the circuit** on a noiseless `StatevectorSampler` and on real
   IBM Quantum hardware (`qiskit-ibm-runtime`), each transpiled for its own
   backend. Job ID, physical qubit layout, raw counts and calibration are
   saved for the hardware run.
4. **Run SQD.** Sampled bitstrings go through self-consistent configuration
   recovery, batching and subspace diagonalization
   (`qiskit_addon_sqd.qubit` / `.configuration_recovery` / `.subsampling`).
   Shot dependence and a `samples_per_batch` sweep are analysed by resampling
   existing data, without extra QPU time.

### CCSD-seeded pipeline (`code/SQD_CCSDseededLUCJ.ipynb`)

Steps 1, 3 and 4 are unchanged (same Hamiltonian, same sampling, same SQD
post-processing), so the effect of the new initialization can be measured
cleanly. Step 2 is replaced by:

2a. **Seed** the LUCJ operator from the supplied amplitudes with
    `UCJOpSpinBalanced.from_t_amplitudes(...)`, using the local interaction
    pattern `aa = [(0,1),(1,2),(2,3)]`, `ab = [(0,0),(1,1),(2,2),(3,3)]`.
2b. **Variationally minimize** the energy over all LUCJ parameters. This
    step is essential: `from_t_amplitudes(..., optimize=True)` only improves
    the fit to the amplitudes and does not minimize the energy, and the raw
    seeded state is not expected to keep CCSD accuracy (this was the cause of
    the validation failure documented in `validation.ipynb` and the week 7
    report).
2c. **Check** that the circuit energy equals the energy computed in the
    (n_alpha, n_beta) subspace (confirms qubit ordering) and that all
    probability lies in the correct particle-number sector.
2d. Test `n_reps = 3` and `n_reps = 4`; transpile for the target backend
    (2Q depth and physical layout are recorded), then sample 10,000 shots and
    sweep `samples_per_batch` over 5, 10, 15, 20, 25, 30, 36 with mean and
    spread over repeated subsampling seeds, reporting the valid-shot
    fraction.

Note that for this 4-orbital system 36 determinants is the entire
(2 alpha, 2 beta) space, so SQD at `samples_per_batch = 36` is exact by
construction; the meaningful points of the sweep are the smaller sizes.

Because the long noiseless stage can outlast a Colab session, the hardware
step can be run on its own from the saved parameters
(`results/lucj_local_r*_params.npy`): the job ID is printed and saved right
after submission, and results can be fetched later from the job ID with
`QiskitRuntimeService.job(...)`.

## Results

`results/` contains:

Baseline (random-start LUCJ):
- `PrePostSQDExact.png`: ansatz-only vs. post-SQD vs. exact energy.
- `simVShardware10kshots.png`: simulator vs. hardware at matched shot counts.
- `SQDErrVSsubspaceSize.png`: SQD error vs. `samples_per_batch`.
- `simVShardware.txt`: full output and job metadata for the simulator and
  hardware runs.

CCSD-seeded:
- `validation_results.txt`: output of the raw-seed validation
  (`code/validation.ipynb`).
- `SQD_CCSDseededSimR3.txt`, `SQD_CCSDseededSimR4.txt`: noiseless simulator
  runs for `n_reps = 3` and `4` (variational error and SQD sweep).
- `SQD_CCSDseededQPUR3.txt`, `SQD_CCSDseededQPUR4.txt`: hardware runs for
  `n_reps = 3` and `4` (backend, job ID, 2Q depth, physical layout,
  valid-shot fraction, SQD sweep).
- `lucj_local_r3_params.npy`, `lucj_local_r4_params.npy`: the optimized LUCJ
  parameters, so a hardware run can be repeated without redoing the
  optimization.

See `weekly_reports/` for the full narrative of how this was built,
including bugs found and fixed along the way.

## Setup

Credentials (IBM Quantum API token and instance CRN) are read from
environment variables / prompted at runtime and are never hardcoded or
committed. See `.env` (gitignored) and the credentials cell in the notebooks
for how these are supplied. Required packages: `qiskit`,
`qiskit-ibm-runtime`, `qiskit-addon-sqd`, `ffsim`, `scipy`, `numpy`,
`matplotlib`.

## How to run

1. Clone the repo and install the packages above (a virtual environment is
   recommended).
2. Supply IBM credentials (see Setup).
3. Baseline: run `code/simVShardware.ipynb` top to bottom.
4. CCSD-seeded: run `code/SQD_CCSDseededLUCJ.ipynb`. To use a different
   Hamiltonian, change only the file path; the metadata is read from the
   file header.

## References and acknowledgements

- IBM Quantum, ["Sample-based quantum diagonalization of a chemistry
  Hamiltonian"](https://quantum.cloud.ibm.com/docs/en/tutorials/sample-based-quantum-diagonalization)
  (the N2 tutorial this project is based on, `ref/`).
- IBM Quantum, ["Build a Qiskit Function for chemistry
  simulation"](https://quantum.cloud.ibm.com/docs/en/guides/function-template-chemistry-workflow)
  (`ref/`).
- [`qiskit-addon-sqd`](https://github.com/Qiskit/qiskit-addon-sqd):
  configuration recovery, subsampling and subspace diagonalization.
- [`ffsim`](https://github.com/qiskit-community/ffsim): LUCJ ansatz
  construction (including seeding from CCSD amplitudes) and fermionic
  circuit tools.
- [Qiskit](https://www.ibm.com/quantum/qiskit) / `qiskit-ibm-runtime` for
  circuit construction, transpilation and hardware execution.
- Thanks to Prof. Indrakshi Raychowdhury for supplying the Hamiltonian and
  CCSD amplitudes, hardware access through her classroom account, and
  detailed feedback that shaped several of this project's later weeks (see
  `weekly_reports/`).