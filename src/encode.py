#!/usr/bin/env python3
# encode.py
# FINAL VERSION: Implements an efficient "at-most-J" cardinality
# constraint using a sequential counter to prevent combinatorial explosion.

import sys, json, os
from itertools import combinations

if len(sys.argv) != 2:
    sys.exit(2)

base = sys.argv[1]
dir_name = os.path.dirname(base)
file_name = os.path.basename(base)

# Construct full paths for input/output files
cityfile = os.path.join(dir_name, file_name + ".city")
satfile = os.path.join(dir_name, file_name + ".satinput")
varmapfile = os.path.join(dir_name, file_name + ".varmap.json")

# --- Constants ---
DIRS = {'R': (1,0), 'L':(-1,0), 'U':(0,-1), 'D':(0,1)}
DIRS_LIST = ['R','L','U','D']
REV_DIRS = {'R':'L','L':'R','U':'D','D':'U'}
STRAIGHT_PAIRS = {('R', 'L'), ('L', 'R'), ('U', 'D'), ('D', 'U')}

# --- Input Reading ---
try:
    with open(cityfile) as f:
        lines = [line.strip() for line in f if line.strip()]
except IOError as e:
    sys.exit(1)

# --- Parse Input ---
mode = int(lines[0])
header = lines[1].split()

if mode == 1:
    N = int(header[0])
    M = int(header[1])
    K = int(header[2])
    J = int(header[3])
    P = 0
    cursor = 2
elif mode == 2:
    N = int(header[0])
    M = int(header[1])
    K = int(header[2])
    J = int(header[3])
    P = int(header[4])
    cursor = 2
else:
    raise SystemExit("Invalid mode in input file: First line must be 1 or 2")

lines_spec = []
for k in range(K):
    sx, sy, ex, ey = map(int, lines[cursor+k].split())
    lines_spec.append(((sx,sy),(ex,ey)))
cursor += K

popular = []
if P > 0:
    pop_tokens = []
    for t in lines[cursor:]:
        pop_tokens += t.split()
    for i in range(0, 2*P, 2):
        px = int(pop_tokens[i])
        py = int(pop_tokens[i+1])
        popular.append((px,py))

# --- Variable and Clause Management ---
var_to_id = {}
clauses = []
id_to_var = {}
next_var = 1

def add_clause(lits):
    clauses.append(lits)

def new_var(name):
    global next_var
    if name in var_to_id: return var_to_id[name]
    vid = next_var
    next_var += 1
    var_to_id[name] = vid
    id_to_var[str(vid)] = name
    return vid

def at_most_one(var_list):
    for i in range(len(var_list)):
        for j in range(i + 1, len(var_list)):
            add_clause([-var_list[i], -var_list[j]])

def exactly_k_if_L(l_var, e_vars, k):
    n = len(e_vars)
    if n > k:
        for subset in combinations(e_vars, k + 1):
            add_clause([-l_var] + [-v for v in subset])
    if k > 0:
        for subset in combinations(e_vars, n - k + 1):
            add_clause([-l_var] + list(subset))

# --- OPTIMIZATION START: Efficient At-Most-K Constraint ---
def add_at_most_k_constraint(variables, k, prefix="s"):
    num_vars = len(variables)
    if num_vars <= k:
        # If the number of variables is already small enough, 
        # the constraint is trivially satisfied.
        return

    # Initialize a matrix of auxiliary Boolean variables
    sequential_matrix = []
    for i in range(num_vars):
        row_vars = []
        for j in range(k + 1):
            var_name = f"{prefix}_{i}_{j}"
            row_vars.append(new_var(var_name))
        sequential_matrix.append(row_vars)

    # --- Base Case Setup ---
    _initialize_base_constraints(variables, sequential_matrix, k)

    # --- Recursive / Inductive Step ---
    for i in range(1, num_vars):
        _propagate_constraints(i, variables, sequential_matrix, k)

    # --- Final Restriction ---
    # Prevent the total sum from exceeding k
    add_clause([-sequential_matrix[num_vars - 1][k]])

def _propagate_constraints(i, variables, seq_matrix, k):
    """Handles propagation of constraints for variable index `i`."""
    for j in range(k + 1):
        # If we reached >= j earlier, we continue to satisfy it
        add_clause([-seq_matrix[i - 1][j], seq_matrix[i][j]])

    # Enforce increment logic
    add_clause([-variables[i], seq_matrix[i][0]])

    for j in range(1, k + 1):
        # Classic sequential counter propagation
        add_clause([-variables[i], -seq_matrix[i - 1][j - 1], seq_matrix[i][j]])

def _initialize_base_constraints(variables, seq_matrix, k):
    """Handles constraint setup for the first variable row."""
    first_var = variables[0]

    # If first variable is True, that contributes to the sum
    add_clause([-first_var, seq_matrix[0][0]])

    # For all higher sums, it’s impossible to exceed one variable’s value
    for j in range(1, k + 1):
        add_clause([-seq_matrix[0][j]])

# --- OPTIMIZATION END ---


# --- Variable Definitions ---
L_vars, E_vars, T_vars, S_vars = {}, {}, {}, {}
cells_lines = {}

for k, (start, end) in enumerate(lines_spec):
    for x in range(N):
        for y in range(M):
            lname = f"L_{k}_{x}_{y}"
            L_vars[(k,x,y)] = new_var(lname)
            cells_lines.setdefault((x,y), []).append(L_vars[(k,x,y)])
            
            if (x,y) != start and (x,y) != end:
                tname = f"T_{k}_{x}_{y}"
                T_vars[(k,x,y)] = new_var(tname)
            
            sname = f"S_{k}_{x}_{y}"
            S_vars[(k,x,y)] = new_var(sname)
            
            for D in DIRS_LIST:
                dx, dy = DIRS[D]
                nx, ny = x + dx, y + dy
                if 0 <= nx < N and 0 <= ny < M:
                    ename = f"E_{k}_{x}_{y}_{D}"
                    E_vars[(k,x,y,D)] = new_var(ename)

# --- CONSTRAINTS ---

def enforce_turn_constraints(lines_spec, T_vars, L_vars, E_vars, DIRS_LIST, STRAIGHT_PAIRS, J):
    """
    Restrict and count turns in paths using efficient counters.
    """
    for k, (start, end) in enumerate(lines_spec):
        turn_vars_for_line = []

        for (line_k, x, y), t_var in T_vars.items():
            if line_k != k:
                continue

            turn_vars_for_line.append(t_var)
            l_var = L_vars[(k, x, y)]

            add_clause([-t_var, l_var])

            for d1_index, D1 in enumerate(DIRS_LIST[:-1]):
                for d2_index in range(d1_index + 1, len(DIRS_LIST)):
                    D2 = DIRS_LIST[d2_index]

                    e1 = E_vars.get((k, x, y, D1))
                    e2 = E_vars.get((k, x, y, D2))

                    if e1 and e2:
                        is_straight_move = (D1, D2) in STRAIGHT_PAIRS

                        if not is_straight_move:
                            add_clause([-l_var, -e1, -e2, t_var])
                        else:
                            add_clause([-l_var, -e1, -e2, -t_var])

        if turn_vars_for_line:
            add_at_most_k_constraint(turn_vars_for_line, J, prefix=f"s_k{k}")

def enforce_unique_occupancy(cells_lines):
    """
    Ensure that each cell contains at most one line segment.
    """
    for (x, y), vids in cells_lines.items():
        if len(vids) > 1:
            at_most_one(vids)

def enforce_path_continuity(lines_spec, L_vars, E_vars, N, M, DIRS_LIST):
    """
    Enforce continuity constraints on paths to ensure proper connectivity
    between start and end points and along each path cell.
    """
    for k, (start, end) in enumerate(lines_spec):
        # Starts and ends must be used
        add_clause([L_vars[(k, start[0], start[1])]])
        add_clause([L_vars[(k, end[0], end[1])]])

        for x in range(N):
            for y in range(M):
                lvid = L_vars.get((k, x, y))
                if not lvid:
                    continue

                incident_edges = [E_vars[(k, x, y, d)] for d in DIRS_LIST if (k, x, y, d) in E_vars]

                if (x, y) == start or (x, y) == end:
                    exactly_k_if_L(lvid, incident_edges, 1)
                else:
                    exactly_k_if_L(lvid, incident_edges, 2)
                    for evid in incident_edges:
                        add_clause([lvid, -evid])

def enforce_popular_cell_constraint(mode, popular, cells_lines):
    """
    Handles special constraints related to popular cells only for mode 2.
    """
    if mode != 2 or not popular:
        return

    for (px, py) in popular:
        vids = cells_lines.get((px, py), [])
        if vids:
            add_clause(vids)
        else:
            # Add a clause that is always true and one always false to keep solver happy
            add_clause([1])
            add_clause([-1])

def enforce_edge_location_consistency(E_vars, L_vars, DIRS, REV_DIRS):
    """
    Ensure edges are consistent with presence of endpoints and neighbors.

    If an edge exists, both endpoints must be active.
    Edges must have reciprocal counterparts where applicable.
    """
    for (k, x, y, D), evid in E_vars.items():
        loc_var = L_vars[(k, x, y)]

        dx, dy = DIRS[D]
        nx, ny = x + dx, y + dy

        add_clause([-evid, loc_var])
        add_clause([-evid, L_vars[(k, nx, ny)]])

        revD = REV_DIRS[D]
        rev_evid = E_vars.get((k, nx, ny, revD))

        if rev_evid:
            add_clause([-evid, rev_evid])
            add_clause([-rev_evid, evid])
        else:
            add_clause([-evid])

def enforce_path_connectivity(lines_spec, S_vars, E_vars, L_vars, N, M, DIRS, DIRS_LIST):
    """
    Ensure starting cells are reachable and paths propagate connectivity properly.
    """
    for k, (start, end) in enumerate(lines_spec):
        sx, sy = start
        add_clause([S_vars[(k, sx, sy)]])

        for x in range(N):
            for y in range(M):
                for D in DIRS_LIST:
                    e_var = E_vars.get((k, x, y, D))
                    if e_var:
                        dx, dy = DIRS[D]
                        nx, ny = x + dx, y + dy

                        add_clause([-S_vars[(k, x, y)], -e_var, S_vars[(k, nx, ny)]])

        for x in range(N):
            for y in range(M):
                l_var = L_vars[(k, x, y)]
                s_var = S_vars[(k, x, y)]
                add_clause([-l_var, s_var])

# Main execution flow calling all steps in order

def apply_all_constraints(mode, cells_lines, E_vars, L_vars, T_vars, S_vars, lines_spec,
                          DIRS, REV_DIRS, DIRS_LIST, STRAIGHT_PAIRS, J, popular, N, M):

    enforce_unique_occupancy(cells_lines)
    enforce_edge_location_consistency(E_vars, L_vars, DIRS, REV_DIRS)
    enforce_path_continuity(lines_spec, L_vars, E_vars, N, M, DIRS_LIST)
    enforce_turn_constraints(lines_spec, T_vars, L_vars, E_vars, DIRS_LIST, STRAIGHT_PAIRS, J)
    enforce_path_connectivity(lines_spec, S_vars, E_vars, L_vars, N, M, DIRS, DIRS_LIST)
    enforce_popular_cell_constraint(mode, popular, cells_lines)

apply_all_constraints(
    mode=mode,
    cells_lines=cells_lines,
    E_vars=E_vars,
    L_vars=L_vars,
    T_vars=T_vars,
    S_vars=S_vars,
    lines_spec=lines_spec,
    DIRS=DIRS,
    REV_DIRS=REV_DIRS,
    DIRS_LIST=DIRS_LIST,
    STRAIGHT_PAIRS=STRAIGHT_PAIRS,
    J=J,
    popular=popular,
    N=N,
    M=M
)


# --- Output Generation ---
num_vars = next_var - 1
num_clauses = len(clauses)
with open(satfile,'w') as f:
    f.write(f"p cnf {num_vars} {num_clauses}\n")
    for c in clauses:
        f.write(" ".join(str(l) for l in c) + " 0\n")

metadata = {'var_to_id': var_to_id, 'id_to_var': id_to_var, 'N':N,'M':M,'K':K,'J':J, 'mode':mode,'lines':lines_spec,'popular':popular}
with open(varmapfile,'w') as f:
    json.dump(metadata, f, indent=2)