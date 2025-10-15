#!/usr/bin/env python3
"""
format checker for Assignment 3

Usage:
    python3 format_checker.py <basename> [--verbose|-v]

Reads:
    <basename>.city      (required)
    <basename>.metromap  (required)

Behavior:
 - If <basename>.metromap is a single '0' (UNSAT), prints:
       UNSAT
   and exits with code 0.

 - If metromap claims SAT (provides paths), the script evaluates constraints and prints a report.
   Default (non-verbose): prints only one line per constraint (VALID/INVALID and a short summary).
   Verbose mode (--verbose or -v): prints per-metro / per-popular-cell details in addition.

Constraints (checked for SAT case):
 1) At most 1 metro line per grid cell (global).
 2) Every metro line k is a path from sk to ek.
 3) There are at most J turns in any metro line.
 4) (Scenario 2 only) Every popular cell is visited by at least one metro line.

Exit codes:
 - 0 : metromap is UNSAT, or metromap is SAT and all applicable constraints are satisfied.
 - 1 : parse error, or metromap is SAT but one or more applicable constraints are violated.
 
"""
from __future__ import print_function
import sys
import re
from collections import namedtuple

MetroSpec = namedtuple(
    'MetroSpec', ['scenario', 'N', 'M', 'K', 'J', 'P', 'starts', 'ends', 'popular'])


def fail(msg):
    print('ERROR:', msg, file=sys.stderr)
    sys.exit(1)


def parse_city(path):
    try:
        with open(path, 'r') as f:
            raw = [ln.rstrip('\n') for ln in f.readlines()]
    except Exception as e:
        raise ValueError("Failed reading city file %r: %s" % (path, e))
    if not raw:
        raise ValueError("Empty city file: %s" % path)
    i = 0
    while i < len(raw) and raw[i].strip() == '':
        i += 1
    if i >= len(raw):
        raise ValueError("City file contains only whitespace")
    first = raw[i].strip()
    if first not in ('1', '2'):
        raise ValueError(
            "First non-empty line must be '1' or '2' (scenario); got: %r" % first)
    scenario = int(first)
    i += 1
    while i < len(raw) and raw[i].strip() == '':
        i += 1
    if i >= len(raw):
        raise ValueError("Missing second line with grid params (N M K J [P])")
    params = raw[i].split()
    i += 1
    if scenario == 1:
        if len(params) != 4:
            raise ValueError(
                "Scenario 1 expects 4 ints on second line: N M K J")
        N, M, K, J = map(int, params)
        P = 0
    else:
        if len(params) != 5:
            raise ValueError(
                "Scenario 2 expects 5 ints on second line: N M K J P")
        N, M, K, J, P = map(int, params)
    if N <= 0 or M <= 0 or K < 0 or J < 0 or P < 0:
        raise ValueError("Invalid numeric values in header")
    starts = []
    ends = []
    for lineno in range(K):
        while i < len(raw) and raw[i].strip() == '':
            i += 1
        if i >= len(raw):
            raise ValueError(
                "Expected %d metro lines but file ended early" % K)
        toks = raw[i].split()
        i += 1
        if len(toks) != 4:
            raise ValueError(
                "Metro line %d: expected 4 integers (sx sy ex ey)" % lineno)
        sx, sy, ex, ey = map(int, toks)
        if not (0 <= sx < N and 0 <= ex < N and 0 <= sy < M and 0 <= ey < M):
            raise ValueError("Metro %d coordinates out of bounds: %r" %
                             (lineno, (sx, sy, ex, ey)))
        starts.append((sx, sy))
        ends.append((ex, ey))
    popular = []
    if scenario == 2:
        while i < len(raw) and raw[i].strip() == '':
            i += 1
        if i >= len(raw):
            raise ValueError("Scenario 2: missing line with popular cells")
        toks = raw[i].split()
        i += 1
        if len(toks) != 2 * P:
            raise ValueError(
                "Scenario 2: expected %d tokens for %d popular cells, got %d" % (2*P, P, len(toks)))
        coords = list(map(int, toks))
        for pidx in range(P):
            x = coords[2*pidx]
            y = coords[2*pidx+1]
            if not (0 <= x < N and 0 <= y < M):
                raise ValueError(
                    "Popular cell %d out of bounds: (%d,%d)" % (pidx, x, y))
            popular.append((x, y))
    if len(set(starts)) != len(starts):
        raise ValueError("Duplicate start locations in city file")
    if len(set(ends)) != len(ends):
        raise ValueError("Duplicate end locations in city file")
    if set(starts).intersection(set(ends)):
        raise ValueError(
            "Some start equals some end location (all starts & ends must be unique)")
    return MetroSpec(scenario=scenario, N=N, M=M, K=K, J=J, P=P, starts=starts, ends=ends, popular=popular)


def parse_metromap(path):
    try:
        with open(path, 'r') as f:
            raw = [ln.rstrip('\n') for ln in f.readlines()]
    except Exception as e:
        raise ValueError("Failed reading metromap file %r: %s" % (path, e))
    lines = [ln for ln in raw if ln.strip() != '']
    if not lines:
        raise ValueError("Empty metromap file")
    if len(lines) == 1 and lines[0].strip() == '0':
        return 'UNSAT', []
    metros = []
    for idx, line in enumerate(lines):
        tokens = line.strip().split()
        if len(tokens) == 1 and re.fullmatch(r'[LRUDlrud0]+', tokens[0]):
            s = tokens[0]
            if s[-1] != '0':
                raise ValueError(
                    "Line %d: expected trailing '0' token" % (idx+1))
            seq = list(s[:-1])
            metros.append([c.upper() for c in seq])
        else:
            if not tokens:
                raise ValueError("Line %d is empty" % (idx+1))
            if tokens[-1] != '0':
                raise ValueError(
                    "Line %d: expected trailing '0' token" % (idx+1))
            seq = tokens[:-1]
            parsed = []
            for t in seq:
                if len(t) != 1 or t.upper() not in ('L', 'R', 'U', 'D'):
                    raise ValueError(
                        "Invalid token %r on line %d" % (t, idx+1))
                parsed.append(t.upper())
            metros.append(parsed)
    return 'SAT', metros


def analyze_constraints(spec, metro_moves):
    N = spec.N
    M = spec.M
    K = spec.K
    J = spec.J
    report = {}
    if len(metro_moves) != K:
        report['c1'] = {'valid': False, 'details': 'metromap lines (%d) != K (%d)' % (
            len(metro_moves), K)}
        c2_per = []
        for k in range(K):
            if k < len(metro_moves):
                c2_per.append((k, False, "Provided but count mismatch"))
            else:
                c2_per.append((k, False, "Missing line"))
        report['c2'] = {'valid': False, 'per_metro': c2_per}
        report['c3'] = {'valid': False, 'per_metro_turns': []}
        report['c4'] = {'valid': False, 'per_popular': []} if spec.scenario == 2 else {
            'valid': True, 'per_popular': []}
        report['final_valid'] = False
        return report

    dirvec = {'L': (-1, 0), 'R': (1, 0), 'U': (0, -1), 'D': (0, 1)}
    per_metro_cells = []
    per_metro_turns = []
    per_metro_errors = []

    for k in range(K):
        sx, sy = spec.starts[k]
        ex, ey = spec.ends[k]
        moves = metro_moves[k]
        x, y = sx, sy
        cells = [(x, y)]
        prev = None
        turns = 0
        error = None
        for step_idx, mv in enumerate(moves):
            if mv not in dirvec:
                error = "Invalid token %r at step %d" % (mv, step_idx+1)
                break
            dx, dy = dirvec[mv]
            x += dx
            y += dy
            if not (0 <= x < N and 0 <= y < M):
                error = "Out of bounds at step %d -> (%d,%d)" % (
                    step_idx+1, x, y)
                break
            cells.append((x, y))
            if prev is None:
                prev = mv
            elif mv != prev:
                turns += 1
                prev = mv
        if error is None and (x, y) != (ex, ey):
            error = "Final pos %r != end %r" % ((x, y), (ex, ey))
        per_metro_cells.append(cells)
        per_metro_turns.append(turns)
        per_metro_errors.append(error)

    # C1: at-most-one per cell
    cell_owners = {}
    for k, cells in enumerate(per_metro_cells):
        for c in cells:
            cell_owners.setdefault(c, []).append(k)
    overlapping = {c: owners for c,
                   owners in cell_owners.items() if len(owners) > 1}
    if overlapping:
        report['c1'] = {'valid': False, 'details': overlapping}
    else:
        report['c1'] = {'valid': True, 'details': None}

    # C2: each metro ends at endpoint / parse errors
    c2_per = []
    c2_all_ok = True
    for k in range(K):
        err = per_metro_errors[k]
        if err is None:
            c2_per.append((k, True, None))
        else:
            c2_all_ok = False
            c2_per.append((k, False, err))
    report['c2'] = {'valid': c2_all_ok, 'per_metro': c2_per}

    # C3: turns <= J
    c3_per = []
    c3_all_ok = True
    for k in range(K):
        turns = per_metro_turns[k]
        ok = (turns <= J)
        if not ok:
            c3_all_ok = False
        c3_per.append((k, turns, J, ok))
    report['c3'] = {'valid': c3_all_ok, 'per_metro_turns': c3_per}

    # C4: popular cells (scenario 2)
    if spec.scenario == 2:
        per_popular = []
        missed = []
        for pc in spec.popular:
            owners = cell_owners.get(pc, [])
            if owners:
                per_popular.append((pc, True, owners))
            else:
                per_popular.append((pc, False, []))
                missed.append(pc)
        report['c4'] = {'valid': (len(missed) == 0),
                        'per_popular': per_popular}
    else:
        report['c4'] = {'valid': True, 'per_popular': []}

    report['final_valid'] = report['c1']['valid'] and report['c2']['valid'] and report['c3']['valid'] and report['c4']['valid']
    return report


def short_summary(report, spec):
    """Return short one-line summaries per constraint for non-verbose mode."""
    lines = []
    # C1
    if report['c1']['valid']:
        lines.append("C1: VALID (no overlapping cells)")
    else:
        overlapping = report['c1']['details']
        # overlapping is dict cell -> owners
        count = len(overlapping)
        # list up to 3 offending cells for briefness
        sample = sorted(list(overlapping.keys()))[:3]
        lines.append("C1: INVALID (%d overlapping cells; sample: %s)" %
                     (count, sample))
    # C2
    if report['c2']['valid']:
        lines.append("C2: VALID (all metros end correctly)")
    else:
        failures = [k for (k, ok, _) in report['c2']['per_metro'] if not ok]
        lines.append(
            "C2: INVALID (%d metros failed to end correctly)" % len(failures))
    # C3
    if report['c3']['valid']:
        lines.append("C3: VALID (turns <= J for all metros)")
    else:
        failures = [(k, t) for (k, t, _, ok) in report['c3']
                    ['per_metro_turns'] if not ok]
        lines.append("C3: INVALID (%d metros exceed J turns)" % len(failures))
    # C4 (only for scenario 2)
    if spec.scenario == 2:
        if report['c4']['valid']:
            lines.append("C4: VALID (all popular cells visited)")
        else:
            misses = [pc for (pc, visited, _) in report['c4']
                      ['per_popular'] if not visited]
            lines.append(
                "C4: INVALID (%d popular cells not visited)" % len(misses))
    return lines


def verbose_print(report, spec):
    # Print detailed report (per-metro, per-popular)
    print("Constraint 1: At most one metro per grid cell")
    if report['c1']['valid']:
        print("  -> VALID: no overlapping cells")
    else:
        print("  -> INVALID: overlapping cells (cell -> metros):")
        for c, owners in sorted(report['c1']['details'].items()):
            print("     %r -> %s" % (c, ','.join(map(str, owners))))
    print()
    print("Constraint 2: Every metro is a path from sk to ek")
    if report['c2']['valid']:
        print("  -> VALID: all metros end correctly")
    else:
        print("  -> INVALID: per-metro status:")
    for k, ok, info in report['c2']['per_metro']:
        if ok:
            print("    Metro %d: OK" % k)
        else:
            print("    Metro %d: FAIL - %s" % (k, info))
    print()
    print("Constraint 3: Each metro has at most J turns")
    if report['c3']['valid']:
        print("  -> VALID: all metros within turn limit")
    else:
        print("  -> INVALID: per-metro turns:")
    for k, turns, allowed, ok in report['c3']['per_metro_turns']:
        status = "OK" if ok else "FAIL"
        print("    Metro %d: turns=%d (J=%d) -> %s" %
              (k, turns, allowed, status))
    print()
    if spec.scenario == 2:
        print("Constraint 4: Popular cells visited by at least one metro")
        if report['c4']['valid']:
            print("  -> VALID: all popular cells visited")
        else:
            print("  -> INVALID: per-popular-cell status:")
        for pc, visited, owners in report['c4']['per_popular']:
            if visited:
                print("    Popular %r: VISITED by %s" %
                      (pc, ','.join(map(str, owners))))
            else:
                print("    Popular %r: NOT VISITED" % (pc,))
    print()
    print("FINAL VERDICT: %s" %
          ("VALID" if report['final_valid'] else "INVALID"))


def main():
    # Accept: python3 format_checker.py <basename> [--verbose|-v]
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(
            "Usage: python3 format_checker.py <basename> [--verbose|-v]", file=sys.stderr)
        sys.exit(1)
    base = sys.argv[1]
    verbose = False
    if len(sys.argv) == 3:
        flag = sys.argv[2].lower()
        if flag in ('-v', '--verbose', 'verbose'):
            verbose = True
        else:
            print("Unknown flag: %r" % sys.argv[2], file=sys.stderr)
            print(
                "Usage: python3 format_checker.py <basename> [--verbose|-v]", file=sys.stderr)
            sys.exit(1)

    cityf = base + '.city'
    mapf = base + '.metromap'
    try:
        spec = parse_city(cityf)
    except Exception as e:
        fail("City parse error: %s" % e)
    try:
        state, metro_moves = parse_metromap(mapf)
    except Exception as e:
        fail("Metromap parse error: %s" % e)
    if state == 'UNSAT':
        print("UNSAT")
        sys.exit(0)
    report = analyze_constraints(spec, metro_moves)
    if verbose:
        verbose_print(report, spec)
    else:
        # non-verbose: one short line per applicable constraint, then final verdict
        lines = short_summary(report, spec)
        for ln in lines:
            print(ln)
        print("FINAL VERDICT: %s" %
              ("VALID" if report['final_valid'] else "INVALID"))
    sys.exit(0 if report['final_valid'] else 1)


if __name__ == '__main__':
    main()
