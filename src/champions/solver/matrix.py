"""Zero-sum matrix games in pure Python (no scipy). The row player maximizes."""
from __future__ import annotations

EPS = 1e-9


def solve_matrix(A):
    """Exact solution of the game with payoff matrix A (rows maximize). Returns (value, x, y):
    x = the row player's optimal mix, y = the column player's.

    Shifts A positive, then solves  max sum(w) s.t. A'w <= 1, w >= 0  by simplex (Bland's rule, so no
    cycling). The dual values of the final tableau give x.
    """
    n, m = len(A), len(A[0])
    shift = 1.0 - min(min(r) for r in A)
    T = [[A[i][j] + shift for j in range(m)] + [1.0 if k == i else 0.0 for k in range(n)] + [1.0]
         for i in range(n)]
    z = [-1.0] * m + [0.0] * n + [0.0]
    basis = [m + i for i in range(n)]
    while True:
        col = next((j for j in range(m + n) if z[j] < -EPS), None)        # Bland: lowest improving column
        if col is None:
            break
        best, row = None, None
        for i in range(n):
            if T[i][col] > EPS:
                ratio = T[i][-1] / T[i][col]
                if best is None or ratio < best - EPS or (abs(ratio - best) <= EPS and basis[i] < basis[row]):
                    best, row = ratio, i
        if row is None:
            raise ValueError("unbounded game matrix")
        piv = T[row][col]
        T[row] = [v / piv for v in T[row]]
        for i in range(n):
            if i != row and abs(T[i][col]) > EPS:
                f = T[i][col]
                T[i] = [a - f * b for a, b in zip(T[i], T[row])]
        f = z[col]
        z = [a - f * b for a, b in zip(z, T[row])]
        basis[row] = col
    w = [0.0] * m
    for i, b in enumerate(basis):
        if b < m:
            w[b] = T[i][-1]
    total = sum(w)
    v_shifted = 1.0 / total
    y = [v * v_shifted for v in w]
    x = [z[m + i] * v_shifted for i in range(n)]
    return v_shifted - shift, x, y


def prune_dominated(A, eps=1e-9):
    """Iteratively drop rows and columns strictly dominated by another pure choice.
    Returns (kept_rows, kept_cols) as index lists into A."""
    rows, cols = list(range(len(A))), list(range(len(A[0])))
    changed = True
    while changed and len(rows) > 1 or changed and len(cols) > 1:
        changed = False
        for i in list(rows):                       # row i is dominated if another row is better in every column
            if len(rows) > 1 and any(k != i and all(A[k][j] > A[i][j] + eps for j in cols) for k in rows):
                rows.remove(i)
                changed = True
        for j in list(cols):                       # column j is dominated if another is lower in every row
            if len(cols) > 1 and any(k != j and all(A[i][k] < A[i][j] - eps for i in rows) for k in cols):
                cols.remove(j)
                changed = True
    return rows, cols


def prune_top_k(A, k):
    """Keep the promising actions of a payoff matrix: for each side, its k best by average payoff plus
    every action that is a best reply to some opposing action. Returns (kept_rows, kept_cols).

    A heuristic. Actions that only pay off later (setup, switching) can be dropped if they look weak
    after one turn, so use a k wide enough to keep them, and measure the error against an unpruned solve.
    """
    n, m = len(A), len(A[0])
    row_avg = [sum(r) / m for r in A]
    col_avg = [sum(A[i][j] for i in range(n)) / n for j in range(m)]
    rows = set(sorted(range(n), key=lambda i: -row_avg[i])[:k])
    cols = set(sorted(range(m), key=lambda j: col_avg[j])[:k])
    for j in range(m):                                       # best reply of the row player to each column
        rows.add(max(range(n), key=lambda i: A[i][j]))
    for i in range(n):                                       # best reply of the column player to each row
        cols.add(min(range(m), key=lambda j: A[i][j]))
    return sorted(rows), sorted(cols)


def lp_max(c, A, b):
    """Maximize c.z subject to A z <= b, z >= 0, for b >= 0 (so z = 0 is a feasible start). Simplex with Bland's
    rule, so degenerate problems terminate. Returns (z, objective)."""
    m, n = len(A), len(c)
    T = [list(A[i]) + [1.0 if k == i else 0.0 for k in range(m)] + [b[i]] for i in range(m)]
    z = [-x for x in c] + [0.0] * m + [0.0]
    basis = [n + i for i in range(m)]
    while True:
        col = next((j for j in range(n + m) if z[j] < -EPS), None)
        if col is None:
            break
        best, row = None, None
        for i in range(m):
            if T[i][col] > EPS:
                ratio = T[i][-1] / T[i][col]
                if best is None or ratio < best - EPS or (abs(ratio - best) <= EPS and basis[i] < basis[row]):
                    best, row = ratio, i
        if row is None:
            raise ValueError("unbounded linear program")
        piv = T[row][col]
        T[row] = [v / piv for v in T[row]]
        for i in range(m):
            if i != row and abs(T[i][col]) > EPS:
                f = T[i][col]
                T[i] = [a - f * v for a, v in zip(T[i], T[row])]
        f = z[col]
        z = [a - f * v for a, v in zip(z, T[row])]
        basis[row] = col
    sol = [0.0] * n
    for i, bi in enumerate(basis):
        if bi < n:
            sol[bi] = T[i][-1]
    return sol, z[-1]


def solve_bayes(matrices, weights):
    """Best single strategy for the row player against several possible games.

    matrices[s] is the payoff matrix (rows = our actions, the same rows in every matrix) of the game we are in if
    the opponent has hidden type s; weights[s] is the probability of that type. The opponent knows its type and best
    replies within it, but we do not, so our mix x must be the same in every game:
        maximize  sum_s weights[s] * min_j (x . matrices[s])_j
    Returns (value, x, per_type_values) where per_type_values[s] = min_j (x . matrices[s])_j."""
    R, S = len(matrices[0]), len(matrices)
    if any(len(m) != R for m in matrices):
        raise ValueError("every matrix must have the same rows")
    total = float(sum(weights))
    w = [x / total for x in weights]
    shift = 1.0 - min(min(min(r) for r in m) for m in matrices)
    A, b = [], []
    for s, mat in enumerate(matrices):
        for j in range(len(mat[0])):
            row = [-(mat[i][j] + shift) for i in range(R)] + [0.0] * S
            row[R + s] = 1.0
            A.append(row)
            b.append(0.0)
    A.append([1.0] * R + [0.0] * S)
    b.append(1.0)
    sol, _ = lp_max([0.0] * R + w, A, b)
    x = sol[:R]
    t = sum(x)
    x = [v / t for v in x]
    per = [min(sum(x[i] * mat[i][j] for i in range(R)) for j in range(len(mat[0]))) for mat in matrices]
    return sum(wi * v for wi, v in zip(w, per)), x, per
