#!/usr/bin/env python3
import html
import math
import random
from pathlib import Path

import streamlit as st
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector


PASSWORD_FILE = "10k-common-passwords.txt"
PASSWORD_FILE_PATH = Path(__file__).resolve().parent / PASSWORD_FILE
MAX_QUBITS = 10


def grover_iterations(n_qubits: int) -> int:
    """Optimal Grover iterations for one marked state."""
    return max(1, int(math.floor((math.pi / 4.0) * math.sqrt(2**n_qubits))))


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


def target_probability_trace(n_qubits: int, target_bitstring: str, iterations: int) -> list[float]:
    """Return p(target) from iteration 0..iterations."""
    q = list(range(n_qubits))
    qc = QuantumCircuit(n_qubits)
    qc.h(q)
    target_index = int(target_bitstring[::-1], 2)

    probs = []
    sv = Statevector.from_instruction(qc)
    probs.append(float(sv.probabilities()[target_index]))
    for _ in range(iterations):
        apply_oracle(qc, q, target_bitstring)
        apply_diffuser(qc, q)
        sv = Statevector.from_instruction(qc)
        probs.append(float(sv.probabilities()[target_index]))
    return probs


@st.cache_data(show_spinner=False)
def load_passwords(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def init_state() -> None:
    if "reroll_nonce" not in st.session_state:
        st.session_state.reroll_nonce = 0


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-blue: #16324f;
            --app-cyan: #2ab7ca;
            --app-light: #f3f8fb;
        }
        .stApp {
            background:
                radial-gradient(circle at 15% 15%, #dff2ff 0%, transparent 40%),
                radial-gradient(circle at 90% 5%, #e3f7f0 0%, transparent 35%),
                #f8fbff;
        }
        .panel-card {
            background: linear-gradient(130deg, #153751 0%, #1d4d73 100%);
            border-radius: 12px;
            padding: 1rem 1.1rem;
            color: #f7fbff;
            border: 1px solid rgba(255,255,255,0.14);
            margin-bottom: 1rem;
        }
        .panel-card h3 {
            margin: 0 0 .5rem 0;
            font-size: 1.15rem;
        }
        .panel-card p {
            margin: .2rem 0;
            color: rgba(255,255,255,0.92);
        }
        .mini-note {
            background: var(--app-light);
            border-radius: 10px;
            border-left: 4px solid var(--app-cyan);
            padding: .75rem .9rem;
            margin: .5rem 0 1rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="Application of Grover's Algorythm in Brute Force Attacks", layout="wide")
    init_state()
    inject_styles()

    st.title("Application of Grover's Algorythm in Brute Force Attacks")
    st.caption(
        "Comparing classical brute force with Grover brute force"
        "by searching target password through a list of unordered passwords."
    )

    try:
        all_passwords = load_passwords(str(PASSWORD_FILE_PATH))
    except FileNotFoundError:
        st.error(
            f"Could not find `{PASSWORD_FILE}` next to this app file. "
            f"Expected at: `{PASSWORD_FILE_PATH}`"
        )
        return

    if len(all_passwords) < 4:
        st.error("Password file is too small. Add at least 4 passwords to continue.")
        return

    max_qubits_from_file = int(math.floor(math.log2(len(all_passwords))))
    max_qubits = min(MAX_QUBITS, max_qubits_from_file)
    if max_qubits < 2:
        st.error("Need enough passwords for at least 2 qubits (4 states).")
        return

    with st.sidebar:
        st.header("Experiment Controls")
        n_qubits = st.slider(
            "Number of qubits",
            min_value=2,
            max_value=max_qubits,
            value=min(8, max_qubits),
            help="Search space size N = 2^n.",
        )

        st.markdown("---")
        randomize_seed = st.checkbox("Random seed each rerun", value=False)
        seed_value = st.number_input("Base seed", min_value=0, value=7, step=1)
        base_seed = (
            random.SystemRandom().randrange(0, 2**32) if randomize_seed else int(seed_value)
        )

        if st.button("Reroll Random Target", use_container_width=True):
            st.session_state.reroll_nonce += 1

    n_states = 2**n_qubits
    passwords = all_passwords[:n_states]
    grover_k = grover_iterations(n_qubits)
    nonce = st.session_state.reroll_nonce
    target_idx = random.Random(base_seed + 101 + nonce).randrange(0, len(passwords))

    with st.sidebar:
        trace_iters = st.slider(
            "Iterations to visualize (after k calls)",
            min_value=1,
            max_value=max(grover_k, min(45, 2 * grover_k)),
            value=grover_k,
        )

    target_password = passwords[target_idx]
    target_bits = format(target_idx, f"0{n_qubits}b")
    classical_checks = target_idx + 1
    classical_success_after_k = min(1.0, grover_k / n_states)
    expected_speedup = ((n_states + 1) / 2) / grover_k
    concrete_speedup = classical_checks / grover_k
    trace = target_probability_trace(n_qubits, target_bits, trace_iters)
    prob_at_k = trace[min(grover_k, len(trace) - 1)]
    peak_iter = max(range(len(trace)), key=lambda i: trace[i])
    peak_prob = trace[peak_iter]

    tab_dashboard, tab_scaling, tab_security = st.tabs(
        ["Experiment Dashboard", "Scaling Explorer", "Security Notes"]
    )

    with tab_dashboard:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Qubits", n_qubits)
        m2.metric("Quantum States", f"{n_states:,}")
        m3.metric("Grover k", grover_k)
        m4.metric("Expected Speedup", f"{expected_speedup:.2f}x")
        m5.metric("Seed Used", base_seed)

        left, right = st.columns([1.05, 1])
        with left:
            st.markdown(
                f"""
                <div class="panel-card">
                    <h3>Current Marked Password</h3>
                    <p><b>Password:</b> <code>{html.escape(target_password)}</code></p>
                    <p><b>Index:</b> {target_idx}</p>
                    <p><b>Bitstring:</b> <code>{target_bits}</code></p>
                    <p><b>Fixed-order classical checks:</b> {classical_checks}</p>
                    <p><b>Concrete speedup for this target:</b> {concrete_speedup:.2f}x</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="mini-note"><b>Interpretation:</b> for this exact target position, '
                "classical brute force needs index+1 checks; Grover uses about sqrt(N) oracle calls."
                "</div>",
                unsafe_allow_html=True,
            )

            st.subheader("Classical Baseline (Theory)")
            st.write(f"- Expected checks for random target: **{(n_states + 1) / 2:.2f}**")
            st.write(f"- Min / Max checks: **1 / {n_states}**")
            st.write(f"- Classical success after `k` checks: **{classical_success_after_k:.6f}**")

        with right:
            st.subheader("Grover Target-Amplitude Trace")
            st.line_chart({"p(target)": trace}, use_container_width=True)
            st.caption("Iteration 0 starts from uniform superposition.")
            st.progress(min(max(prob_at_k, 0.0), 1.0))
            st.caption(f"p(target) at k={grover_k}: {prob_at_k:.4f}")

            st.subheader("Step Comparison")
            st.dataframe(
                [
                    {"Method": "Classical checks for this target", "Steps": classical_checks},
                    {"Method": "Grover oracle calls (k)", "Steps": grover_k},
                ],
                hide_index=True,
                use_container_width=True,
            )

        with st.expander("Show measured Grover circuit"):
            qc = build_grover_circuit(n_qubits, target_bits, grover_k)
            st.code(str(qc.draw(output="text")), language="text")

    with tab_scaling:
        st.subheader("How the Workload Grows with Problem Size")
        qubit_points = list(range(2, n_qubits + 1))
        classical_curve = [((2**q) + 1) / 2 for q in qubit_points]
        grover_curve = [grover_iterations(q) for q in qubit_points]
        speedup_curve = [classical_curve[i] / grover_curve[i] for i in range(len(qubit_points))]

        st.line_chart(
            {"Classical expected checks": classical_curve, "Grover oracle calls": grover_curve},
            use_container_width=True,
        )
        st.caption("Raw workload trend from 2 qubits up to the selected qubit count.")

        st.dataframe(
            [
                {
                    "Qubits": q,
                    "Quantum states": 2**q,
                    "Classical expected checks": round(classical_curve[i], 2),
                    "Grover's algorythm calls (k)": grover_curve[i],
                    "Expected speedup": f"{speedup_curve[i]:.2f}x",
                }
                for i, q in enumerate(qubit_points)
            ],
            hide_index=True,
            use_container_width=True,
        )

    with tab_security:
        st.subheader("Comparison Metrics and Additional Information")
        st.warning(
                "All comparison metrics are evaluated based on oracle calls and iterative checks because the quantum algorythm is being executed in a classical computer simulating quantum processes."
        )

        st.markdown(
            """
1. Classical brute-force search grows like **O(N)** checks.
2. Grover search lowers this to about **O($\sqrt{N}$)** oracle calls.
3. This is why symmetric keys are often discussed as needing effectively doubled sizes in a post-quantum setting.
4. Password cracking is still dominated by practical controls: hashing cost, salts, MFA, lockouts and rate limiting.
            """
        )
        st.dataframe(
            [
                {
                    "Classical key size (bits)": 64,
                    "Approx Grover security (bits)": 32,
                    "Level of Security": "Legacy level",
                },
                {
                    "Classical key size (bits)": 128,
                    "Approx Grover security (bits)": 64,
                    "Level of Security": "Current baseline",
                },
                {
                    "Classical key size (bits)": 256,
                    "Approx Grover security (bits)": 128,
                    "Level of Security": "High-security target",
                },
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.markdown(
            """
            **Quick key-size rule of thumb**
            - 128-bit symmetric key -> ~64-bit security against Grover search.
            - 256-bit symmetric key -> ~128-bit security against Grover search.
            """
        )


if __name__ == "__main__":
    main()
