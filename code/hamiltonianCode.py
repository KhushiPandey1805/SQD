"""
Parse a Jordan-Wigner Pauli-list Hamiltonian file (as produced by classical
quantum chemistry + JW transform) into a Qiskit SparsePauliOp, and extract
its metadata (qubit count, electron count, spin, reference energy) directly
from the file itself.

File format expected:

Header (comment lines, starting with '#') containing, somewhere, lines like:
    # Basis: cc-pVQZ; 4 active electrons in 4 spatial orbitals = 8 qubits; MS2=0.
    # Qubit ordering: 0=(orb0,alpha), 1=(orb0,beta), 2=(orb1,alpha), ...
    # CASSCF reference energy: -76.11669094458742 Ha

Body: one Pauli term per line, formatted as
    <Pauli term>: <coefficient>
where <Pauli term> is either the literal "I" (identity, i.e. a constant
energy offset), or a space-separated list of tokens like "Z0", "Y2", "X4",
each meaning "apply this Pauli operator to this qubit index". Any qubit not
mentioned in a given line is implicitly Identity on that qubit.

This module makes NO assumptions specific to any one molecule -- num_qubits,
electron counts, spin, and reference energy are all read from the file, so
the SAME code works for any Hamiltonian file following this format. Only the
FILEPATH needs to change between different systems.
"""

import re

import numpy as np
from qiskit.quantum_info import SparsePauliOp


def parse_hamiltonian_file(filepath: str) -> SparsePauliOp:
    """Read a Pauli-list Hamiltonian text file and return a SparsePauliOp.

    The number of qubits is inferred automatically from the highest qubit
    index that appears anywhere in the file -- no need to specify it.
    """
    raw_terms = []  # list of (term_str, coeff) before we know num_qubits
    max_qubit_index = -1

    with open(filepath, "r") as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            term_str, coeff_str = line.rsplit(":", 1)
            coeff = float(coeff_str.strip())
            term_str = term_str.strip()

            if term_str != "I":
                for token in term_str.split():
                    qubit_index = int(token[1:])
                    max_qubit_index = max(max_qubit_index, qubit_index)

            raw_terms.append((term_str, coeff))

    num_qubits = max_qubit_index + 1

    pauli_list = []
    for term_str, coeff in raw_terms:
        paulis = ["I"] * num_qubits
        if term_str != "I":
            for token in term_str.split():
                letter = token[0]
                qubit_index = int(token[1:])
                paulis[qubit_index] = letter
        # Qiskit's Pauli-label convention reads left-to-right as qubit
        # (num_qubits-1) ... qubit 0 (qubit 0 is the *rightmost* character).
        label = "".join(reversed(paulis))
        pauli_list.append((label, coeff))

    hamiltonian = SparsePauliOp.from_list(pauli_list)
    hamiltonian = hamiltonian.simplify()
    return hamiltonian


def parse_metadata(filepath: str) -> dict:
    """
    Extract header metadata from a Hamiltonian file:
      - n_electrons, n_spatial_orbitals, ms2 (from a line like
        "4 active electrons in 4 spatial orbitals = 8 qubits; MS2=0")
      - n_alpha, n_beta (derived from n_electrons and ms2, same formula
        used when originally building the active space in PySCF)
      - reference_energy (from a line containing "reference energy")
      - qubit_ordering: "interleaved" if the header's example ordering
        looks like "0=(orb0,alpha), 1=(orb0,beta), 2=(orb1,alpha), ...",
        otherwise "unknown" (caller should double check manually)

    Raises ValueError if a required piece of metadata can't be found --
    better to fail loudly than silently guess wrong physics.
    """
    header_lines = []
    with open(filepath, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if line.startswith("#"):
                header_lines.append(line)
            elif line:
                break  # reached the Pauli-term body, header is done
    header_text = "\n".join(header_lines)

    metadata = {}

    electrons_match = re.search(
        r"(\d+)\s+active electrons in\s+(\d+)\s+spatial orbitals", header_text
    )
    if not electrons_match:
        raise ValueError(
            "Could not find an '<N> active electrons in <M> spatial orbitals' "
            "line in the file header -- check the file format."
        )
    n_electrons = int(electrons_match.group(1))
    n_spatial_orbitals = int(electrons_match.group(2))

    ms2_match = re.search(r"MS2\s*=\s*(-?\d+)", header_text)
    if not ms2_match:
        raise ValueError("Could not find an 'MS2=<value>' line in the file header.")
    ms2 = int(ms2_match.group(1))

    n_alpha = (n_electrons + ms2) // 2
    n_beta = (n_electrons - ms2) // 2

    energy_match = re.search(
        r"reference energy\s*:\s*(-?\d+\.?\d*)", header_text, re.IGNORECASE
    )
    if not energy_match:
        raise ValueError("Could not find a 'reference energy: <value>' line in the file header.")
    reference_energy = float(energy_match.group(1))

    qubit_ordering = "unknown"
    if re.search(r"0=\(orb0,alpha\)\s*,\s*1=\(orb0,beta\)", header_text):
        qubit_ordering = "interleaved"
    elif re.search(r"0=\(orb0,alpha\)\s*,.*\(orb1,alpha\)", header_text):
        qubit_ordering = "blocked"

    metadata.update(
        n_electrons=n_electrons,
        n_spatial_orbitals=n_spatial_orbitals,
        ms2=ms2,
        n_alpha=n_alpha,
        n_beta=n_beta,
        reference_energy=reference_energy,
        qubit_ordering=qubit_ordering,
    )
    return metadata


def interleaved_to_blocked_layout(n_spatial_orbitals: int) -> list[int]:
    """
    Build the qubit permutation for "interleaved -> blocked" ordering, for
    ANY number of spatial orbitals (generalizes the specific 8-qubit
    permutation used for the H2O CAS(4e,4o) case).

    Interleaved: qubit 2k = orbital k alpha, qubit 2k+1 = orbital k beta.
    Blocked:     qubit k = orbital k alpha, qubit k+N = orbital k beta.

    Returns `layout` such that layout[old_interleaved_index] = new_blocked_index.
    """
    norb = n_spatial_orbitals
    layout = [0] * (2 * norb)
    for k in range(norb):
        layout[2 * k] = k              # alpha of orbital k -> blocked position k
        layout[2 * k + 1] = k + norb   # beta of orbital k -> blocked position k+norb
    return layout


def check_hermitian(hamiltonian: SparsePauliOp) -> bool:
    """Verify H = H^dagger (a physical requirement for any Hamiltonian)."""
    matrix = hamiltonian.to_matrix()
    return np.allclose(matrix, matrix.conj().T)


def exact_ground_state_energy(hamiltonian: SparsePauliOp) -> float:
    """
    Brute-force exact diagonalization. Only reasonable for small qubit
    counts (a 2^N x 2^N matrix) -- this is NOT what you'd do for a real
    SQD-scale problem, it's purely a sanity check on the parsing.
    """
    matrix = hamiltonian.to_matrix()
    eigenvalues = np.linalg.eigvalsh(matrix)
    return eigenvalues[0]


if __name__ == "__main__":
    FILEPATH = "../hamiltonian/H2O_CAS4e4o_JW_Pauli_Hamiltonian_HERMITIAN.txt"

    hamiltonian = parse_hamiltonian_file(FILEPATH)
    metadata = parse_metadata(FILEPATH)

    print(f"Number of qubits: {hamiltonian.num_qubits}")
    print(f"Number of Pauli terms after simplify(): {len(hamiltonian.paulis)}")
    print(f"Is Hermitian: {check_hermitian(hamiltonian)}")
    print(f"Metadata parsed from file: {metadata}")

    ground_energy = exact_ground_state_energy(hamiltonian)
    print(f"Exact diagonalization ground-state energy: {ground_energy}")
    print(f"Reference energy (from file header):        {metadata['reference_energy']}")
    print(f"Difference: {abs(ground_energy - metadata['reference_energy']):.10f} Ha")