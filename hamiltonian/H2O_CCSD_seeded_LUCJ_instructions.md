# H2O CAS(4e,4o): CCSD-seeded LUCJ before the QPU run

Use the **same H2O CAS(4e,4o) Hamiltonian as before**. The only change is the preparation of the sampling state: initialize LUCJ from the supplied CCSD amplitudes instead of random LUCJ parameters.

## Files
- `H2O_CAS4e4o_CCSD_t_amplitudes.txt` — human-readable amplitudes/check values.
- **Preferred for code:** `H2O_CAS4e4o_CCSD_t_amplitudes.npz` — contains `t1` and `t2` directly.

The amplitudes correspond to the supplied FCIDUMP and give
`E_CCSD = -76.11659704909 Ha`, only about `0.094 mHa` above the exact CAS energy.

## Before the QPU run

```python
import numpy as np
import ffsim

norb = 4
nelec = (2, 2)

# Do NOT randomly initialize t1/t2.
data = np.load("H2O_CAS4e4o_CCSD_t_amplitudes.npz")
t1 = data["t1"]       # shape (2,2)
t2 = data["t2"]       # shape (2,2,2,2)

# Use the same local interaction pattern chosen for the LUCJ circuit.
pairs_aa = [(p, p + 1) for p in range(norb - 1)]
pairs_ab = [(p, p) for p in range(norb)]

lucj_op = ffsim.UCJOpSpinBalanced.from_t_amplitudes(
    t2=t2,
    t1=t1,
    n_reps=1,                    # start here; later test larger n_reps if useful
    interaction_pairs=(pairs_aa, pairs_ab),
    optimize=True,
    options={"maxiter": 1000},
)
```

Then prepare the circuit as

```python
circuit.append(ffsim.qiskit.PrepareHartreeFockJW(norb, nelec), qubits)
circuit.append(ffsim.qiskit.UCJOpSpinBalancedJW(lucj_op), qubits)
```

### Important qubit-ordering check
`UCJOpSpinBalancedJW` uses **spin-blocked ordering**
`[0α,1α,2α,3α,0β,1β,2β,3β]`.

The supplied Pauli Hamiltonian was originally in **interleaved ordering**
`[0α,0β,1α,1β,2α,2β,3α,3β]`.

Therefore keep the existing interleaved↔spin-blocked permutation in your code and verify the ordering on the noiseless simulator before submitting to hardware.

## Validation before hardware
1. Compute the noiseless variational energy of the CCSD-seeded LUCJ state.
2. Confirm `Nα=Nβ=2`.
3. Confirm the energy is improved relative to the previous randomly initialized LUCJ state.
4. Only then transpile and run the same sampling/SQD workflow on the QPU.
5. Keep the same shot and `samples_per_batch` convergence analysis used previously.

Do **not** change the chemistry Hamiltonian or the SQD post-processing in this comparison; change only the state-preparation initialization so that the benefit of CCSD seeding can be measured cleanly.
