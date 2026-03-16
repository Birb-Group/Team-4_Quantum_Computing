#!/usr/bin/env python3
import argparse
import math
import random
from statistics import mean
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector


def grover_iterations(n_qubits: int) -> int:
    """ Optimal number of iterations for grover when searching ONE marked state """
    return max(1, int(math.floor((math.pi / 4.0) * math.sqrt(2**n_qubits))))


def run_classical_trials(n_qubits: int, trials: int, seed: int) -> tuple[float, int, int]:
    rng = random.Random(seed)
    n_states = 2**n_qubits

    # Assume brute force tries candidates in fixed order 0..N-1.
    # If secret is uniformly random, checks = secret_index + 1.
    checks = [rng.randrange(0, n_states) + 1 for _ in range(trials)]
    avg_checks = mean(checks)
    return avg_checks, min(checks), max(checks)

def apply_z(circuit: QuantumCircuit, qubits: list[int]) -> None:
    if len(qubits) == 1:
        circuit.z(qubits[0])
        return
    circuit.h(qubits[-1])
    circuit.mcx(qubits[:-1], qubits[-1])
    circuit.h(qubits[-1])


def apply_oracle(circuit: QuantumCircuit, qubits: list[int], target_bitstring: str) -> None:
    for i, bit in enumerate(target_bitstring):
        if bit == "0":
            circuit.x(qubits[i])
    apply_z(circuit, qubits)
    for i, bit in enumerate(target_bitstring):
        if bit == "0":
            circuit.x(qubits[i])


def apply_diffuser(circuit: QuantumCircuit, qubits: list[int]) -> None:
    circuit.h(qubits)
    circuit.x(qubits)
    apply_z(circuit, qubits)
    circuit.x(qubits)
    circuit.h(qubits)


def build_grover_circuit(n_qubits: int, target: str, iterations: int) -> QuantumCircuit:
    qc = QuantumCircuit(n_qubits, n_qubits)
    q = list(range(n_qubits))
    qc.h(q)
    for _ in range(iterations):
        apply_oracle(qc, q, target)
        apply_diffuser(qc, q)
    qc.measure(q, q)
    return qc


def trace_grover_iterations(n_qubits: int, target_bitstring: str, iterations: int) -> None:
    """Print how Grover amplifies the target state at each iteration."""
    q = list(range(n_qubits))
    qc = QuantumCircuit(n_qubits)
    qc.h(q)
    # Statevector indexing uses |q_{n-1}...q_0>, so reverse logical q0..q_{n-1} bits.
    target_index = int(target_bitstring[::-1], 2)

    sv = Statevector.from_instruction(qc)
    initial_probs = sv.probabilities()
    print("\nQiskit iteration trace")
    print("----------------------")
    print(f"target (logical q0..q{n_qubits-1}): {target_bitstring}")
    print(
        f"iter  0: p(target={target_bitstring})={initial_probs[target_index]:.6f}"
    )

    for k in range(1, iterations + 1):
        apply_oracle(qc, q, target_bitstring)
        apply_diffuser(qc, q)
        sv = Statevector.from_instruction(qc)
        probs = sv.probabilities()
        best_index = int(probs.argmax())
        best_bits = format(best_index, f"0{n_qubits}b")[::-1]
        print(
            f"iter {k:2d}: p(target)={probs[target_index]:.6f} "
            f"top={best_bits} p(top)={probs[best_index]:.6f}"
        )


def bruteforce_password(passwords: list[str], target_password: str) -> tuple[int, int]:
    checks = 0
    for i, pwd in enumerate(passwords):
        checks += 1
        if pwd == target_password:
            return i, checks

def main():
    parser = argparse.ArgumentParser(description="Brute-force vs Grover sandbox demo")
    parser.add_argument("--num-qubits", type=int, default=12, help="Search size N = 2^n")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument(
        "--randomize-seed",
        action="store_true",
        help="Use a fresh random seed every run (overrides --seed)",
    )
    parser.add_argument(
        "--experiments",
        type=int,
        default=1000,
        help="Number of simulated Grover measurements (default: 1000)",
    )
    args = parser.parse_args()
    base_seed = random.SystemRandom().randrange(0, 2**32) if args.randomize_seed else args.seed

    if args.num_qubits < 1:
        raise ValueError("--num-qubits must be >= 1")

    n_states = 2**args.num_qubits
    grover_k = grover_iterations(args.num_qubits)

    print("Brute Force vs Grover (Sandbox)")
    print("===============================")
    print(f"n qubits:                 {args.num_qubits}")
    print(f"Search space N:           {n_states}")
    print(f"Seed used:                {base_seed}")
    print(f"Grover iterations (k):    {grover_k}")

    # Concrete password-list demo:
    # Choose only a password value then search by value.
    rng = random.Random(base_seed + 101)

    # Get passwords
    with open("10k-common-passwords.txt", "r") as file:
        password_list = file.read().splitlines()

    passwords = password_list[:n_states]
    target_password = rng.choice(passwords)
    found_idx, classical_checks = bruteforce_password(passwords, target_password)
    target_bits = format(found_idx, f"0{args.num_qubits}b")
    concrete_speedup = classical_checks / grover_k
    classical_success_after_k = min(1.0, grover_k / n_states)
    print("\nConcrete password-list demo")
    print("---------------------------")
    print(f"Password list size:       {len(passwords)}")
    print(f"Target password:          {target_password}")
    print(f"Classical found index:    {found_idx} (binary {target_bits})")
    print(f"Classical checks used:    {classical_checks}")
    print(f"Grover oracle calls (k):  {grover_k}")
    print(f"Observed speedup:         {concrete_speedup:.2f}x fewer oracle calls")
    print(f"Classical success after k checks: {classical_success_after_k:.6f}")
    trace_grover_iterations(args.num_qubits, target_bits, grover_k)

if __name__ == "__main__":
    main()
