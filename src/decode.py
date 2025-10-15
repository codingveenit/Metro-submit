#!/usr/bin/env python3
# decode.py
# CORRECTED: Uses a robust BFS path reconstruction method to trace the
# path from the SAT solver's output.

import sys, json, os
from collections import deque

if len(sys.argv) != 4:
    sys.exit(2)

base = sys.argv[1]
satout = sys.argv[2]
outmap = sys.argv[3]

# Construct paths based on the base name
varmapfile = os.path.splitext(base)[0] + ".varmap.json"

# --- Load Metadata ---
try:
    with open(varmapfile) as f:
        meta = json.load(f)
    lines_spec = meta['lines']
    K = meta['K']
    id_to_var = meta['id_to_var']
except Exception as e:
    sys.exit(1)

# --- Read SAT Solver Output ---
try:
    with open(satout) as f:
        satlines = [l.strip() for l in f if l.strip()]
except Exception as e:
    sys.exit(1)

# Handle UNSAT case
if satlines[0].upper() == 'UNSAT':
    with open(outmap, 'w') as f:
        f.write("0\n")
    sys.exit(0)

DIRS = {'R':(1,0), 'L':(-1,0), 'U':(0,-1), 'D':(0,1)}

# --- Parse SAT Solution ---
# Extract all variables that are assigned to be true
true_vars_ids = set()
for line in satlines[1:]: # Skip the 'SAT' line
    for token in line.split():
        try:
            val = int(token)
            if val > 0:
                true_vars_ids.add(str(val))
        except ValueError:
            pass # Ignore non-integer tokens

# Create a set of true 'E' (edge) variables for efficient lookup
E_true = set()
for vid_str in true_vars_ids:
    if vid_str in id_to_var:
        name = id_to_var[vid_str]
        if name.startswith("E_"):
            _, k, x, y, D = name.split("_")
            E_true.add((int(k), int(x), int(y), D))

# --- Path Reconstruction ---

def perform_bfs_search(adjacency, start, end):
    """
    Perform a BFS from start to end on the adjacency list.
    Returns the path as a list of directions if found, else None.
    """
    sx, sy = start
    ex, ey = end

    queue = deque()
    visited = set()

    # Initialize the BFS queue with starting position and empty path
    queue.append((sx, sy, []))
    visited.add((sx, sy))

    while len(queue) > 0:
        current_x, current_y, path_so_far = queue.popleft()

        # If target reached, return accumulated directions
        if (current_x, current_y) == (ex, ey):
            return path_so_far

        # Explore neighbors of current node
        neighbors = adjacency.get((current_x, current_y), [])
        for (next_pos, direction) in neighbors:
            if next_pos not in visited:
                visited.add(next_pos)
                # Construct new path by appending current direction
                new_path = path_so_far + [direction]
                queue.append((next_pos[0], next_pos[1], new_path))

    # No path found if BFS queue exhausted
    return None

def find_path_bfs(k, sx, sy, ex, ey, E_true, DIRS):
    """
    Coordinates building adjacency and BFS pathfinding steps for metro line k.
    """
    adjacency_list = build_adjacency_list_for_line(k, E_true, DIRS)
    path = perform_bfs_search(adjacency_list, (sx, sy), (ex, ey))
    return path

def build_adjacency_list_for_line(k, E_true, DIRS):
    """
    Build adjacency list for metro line k using edges marked true in SAT solution.
    """
    adjacency = {}  # Key: (x,y), Value: list of tuples ((nx, ny), direction)
    for (kk, x, y, D) in E_true:
        if kk != k:
            continue
        dx, dy = DIRS[D]
        nx = x + dx
        ny = y + dy
        if (x, y) not in adjacency:
            adjacency[(x, y)] = []
        adjacency[(x, y)].append(((nx, ny), D))
    return adjacency

# --- Main Decoding Loop ---
all_paths_found = True
output_lines = []
for k in range(K):
    sx, sy = lines_spec[k][0]
    ex, ey = lines_spec[k][1]
    
    path = find_path_bfs(k, sx, sy, ex, ey, E_true, DIRS)
    
    if path is None:
        all_paths_found = False
        break
    
    output_lines.append(" ".join(path + ["0"]))

# --- Write Final Output ---
with open(outmap, 'w') as f:
    if all_paths_found:
        for line in output_lines:
            f.write(line + "\n")
    else:
        f.write("0\n")