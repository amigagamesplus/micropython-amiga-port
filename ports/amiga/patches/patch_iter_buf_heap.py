#!/usr/bin/env python3
"""
Patch script for m68k iter_buf stack alignment bug.

On m68k processors, mp_obj_iter_buf_t allocated on the C stack can be
misaligned, causing "object isn't an iterator" crashes. This script
forces heap allocation by passing NULL to mp_getiter() instead of
&iter_buf in all affected files.

Usage (from MicroPython root):
    python3 ports/amiga/patches/patch_iter_buf_heap.py

The script is idempotent — safe to run multiple times.
"""

import os
import sys

# Each patch: (file, original_lines, patched_lines)
# Lines are matched with surrounding context for precision.

PATCHES = [
    # --- py/vm.c: ENTRY(MP_BC_GET_ITER_STACK) ---
    (
        "py/vm.c",
        [
            "                    mp_obj_t obj = TOP();\n",
            "                    mp_obj_iter_buf_t *iter_buf = (mp_obj_iter_buf_t*)sp;\n",
            "                    sp += MP_OBJ_ITER_BUF_NSLOTS - 1;\n",
            "                    obj = mp_getiter(obj, iter_buf);\n",
            "                    if (obj != MP_OBJ_FROM_PTR(iter_buf)) {\n",
            "                        // Iterator didn't use the stack so indicate that with MP_OBJ_NULL.\n",
            "                        *(sp - MP_OBJ_ITER_BUF_NSLOTS + 1) = MP_OBJ_NULL;\n",
            "                        *(sp - MP_OBJ_ITER_BUF_NSLOTS + 2) = obj;\n",
            "                    }\n",
        ],
        [
            "                    mp_obj_t obj = TOP();\n",
            "                    sp += MP_OBJ_ITER_BUF_NSLOTS - 1;\n",
            "                    obj = mp_getiter(obj, NULL);  // AMIGA FIX: force heap alloc (stack iter breaks on m68k)\n",
            "                    *(sp - MP_OBJ_ITER_BUF_NSLOTS + 1) = MP_OBJ_NULL;\n",
            "                    *(sp - MP_OBJ_ITER_BUF_NSLOTS + 2) = obj;\n",
        ],
    ),

    # --- py/runtime.c: CONTAINS operator (line ~661) ---
    (
        "py/runtime.c",
        [
            "        mp_obj_iter_buf_t iter_buf;\n",
            "        mp_obj_t iter = mp_getiter(lhs, &iter_buf);\n",
        ],
        [
            "        // AMIGA FIX: force heap alloc (stack iter_buf breaks on m68k)\n",
            "        mp_obj_t iter = mp_getiter(lhs, NULL);\n",
        ],
    ),

    # --- py/runtime.c: star args unpacking (line ~832) ---
    (
        "py/runtime.c",
        [
            "                    mp_obj_iter_buf_t iter_buf;\n",
            "                    mp_obj_t iterable = mp_getiter(arg, &iter_buf);\n",
        ],
        [
            "                    // AMIGA FIX: force heap alloc (stack iter_buf breaks on m68k)\n",
            "                    mp_obj_t iterable = mp_getiter(arg, NULL);\n",
        ],
    ),

    # --- py/runtime.c: sequence unpacking (line ~959) ---
    (
        "py/runtime.c",
        [
            "        mp_obj_iter_buf_t iter_buf;\n",
            "        mp_obj_t iterable = mp_getiter(seq_in, &iter_buf);\n",
        ],
        [
            "        // AMIGA FIX: force heap alloc (stack iter_buf breaks on m68k)\n",
            "        mp_obj_t iterable = mp_getiter(seq_in, NULL);\n",
        ],
    ),

    # --- py/modbuiltins.c: all() ---
    (
        "py/modbuiltins.c",
        [
            "    mp_obj_iter_buf_t iter_buf;\n",
            "    mp_obj_t iterable = mp_getiter(o_in, &iter_buf);\n",
            "    mp_obj_t item;\n",
            "    while ((item = mp_iternext(iterable)) != MP_OBJ_STOP_ITERATION) {\n",
            "        if (!mp_obj_is_true(item)) {\n",
        ],
        [
            "    // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "    mp_obj_t iterable = mp_getiter(o_in, NULL);\n",
            "    mp_obj_t item;\n",
            "    while ((item = mp_iternext(iterable)) != MP_OBJ_STOP_ITERATION) {\n",
            "        if (!mp_obj_is_true(item)) {\n",
        ],
    ),

    # --- py/modbuiltins.c: any() ---
    (
        "py/modbuiltins.c",
        [
            "    mp_obj_iter_buf_t iter_buf;\n",
            "    mp_obj_t iterable = mp_getiter(o_in, &iter_buf);\n",
            "    mp_obj_t item;\n",
            "    while ((item = mp_iternext(iterable)) != MP_OBJ_STOP_ITERATION) {\n",
            "        if (mp_obj_is_true(item)) {\n",
        ],
        [
            "    // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "    mp_obj_t iterable = mp_getiter(o_in, NULL);\n",
            "    mp_obj_t item;\n",
            "    while ((item = mp_iternext(iterable)) != MP_OBJ_STOP_ITERATION) {\n",
            "        if (mp_obj_is_true(item)) {\n",
        ],
    ),

    # --- py/modbuiltins.c: min/max() ---
    (
        "py/modbuiltins.c",
        [
            "        mp_obj_iter_buf_t iter_buf;\n",
            "        mp_obj_t iterable = mp_getiter(args[0], &iter_buf);\n",
            "        mp_obj_t best_key = MP_OBJ_NULL;\n",
        ],
        [
            "        // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "        mp_obj_t iterable = mp_getiter(args[0], NULL);\n",
            "        mp_obj_t best_key = MP_OBJ_NULL;\n",
        ],
    ),

    # --- py/modbuiltins.c: sum() ---
    (
        "py/modbuiltins.c",
        [
            "    mp_obj_iter_buf_t iter_buf;\n",
            "    mp_obj_t iterable = mp_getiter(args[0], &iter_buf);\n",
            "    mp_obj_t item;\n",
            "    while ((item = mp_iternext(iterable)) != MP_OBJ_STOP_ITERATION) {\n",
            "        value = mp_binary_op(MP_BINARY_OP_ADD, value, item);\n",
        ],
        [
            "    // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "    mp_obj_t iterable = mp_getiter(args[0], NULL);\n",
            "    mp_obj_t item;\n",
            "    while ((item = mp_iternext(iterable)) != MP_OBJ_STOP_ITERATION) {\n",
            "        value = mp_binary_op(MP_BINARY_OP_ADD, value, item);\n",
        ],
    ),

    # --- py/objdeque.c: extend() ---
    (
        "py/objdeque.c",
        [
            "    mp_obj_iter_buf_t iter_buf;\n",
            "    mp_obj_t iter = mp_getiter(arg_in, &iter_buf);\n",
        ],
        [
            "    // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "    mp_obj_t iter = mp_getiter(arg_in, NULL);\n",
        ],
    ),

    # --- py/objdict.c: dict_view_print() ---
    (
        "py/objdict.c",
        [
            "    mp_obj_iter_buf_t iter_buf;\n",
            "    mp_obj_t self_iter = dict_view_getiter(self_in, &iter_buf);\n",
        ],
        [
            "    // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "    mp_obj_t self_iter = mp_getiter(self_in, NULL);\n",
        ],
    ),

    # --- py/objset.c: set_isdisjoint() ---
    (
        "py/objset.c",
        [
            "    mp_obj_iter_buf_t iter_buf;\n",
            "    mp_obj_t iter = mp_getiter(other, &iter_buf);\n",
            "    mp_obj_t next;\n",
        ],
        [
            "    // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "    mp_obj_t iter = mp_getiter(other, NULL);\n",
            "    mp_obj_t next;\n",
        ],
    ),

    # --- py/objset.c: set_issubset_internal() ---
    (
        "py/objset.c",
        [
            "        mp_obj_iter_buf_t iter_buf;\n",
            "        mp_obj_t iter = set_getiter(MP_OBJ_FROM_PTR(self), &iter_buf);\n",
        ],
        [
            "        // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "        mp_obj_t iter = mp_getiter(MP_OBJ_FROM_PTR(self), NULL);\n",
        ],
    ),

    # --- py/objstr.c: bytes_make_new() ---
    (
        "py/objstr.c",
        [
            "    mp_obj_iter_buf_t iter_buf;\n",
            "    mp_obj_t iterable = mp_getiter(args[0], &iter_buf);\n",
        ],
        [
            "    // AMIGA FIX: force heap iter (m68k stack alignment issue)\n",
            "    mp_obj_t iterable = mp_getiter(args[0], NULL);\n",
        ],
    ),
]


def find_block(lines, pattern):
    """Find the starting index of a multi-line pattern in lines."""
    for i in range(len(lines) - len(pattern) + 1):
        if lines[i:i + len(pattern)] == pattern:
            return i
    return -1


def patch_file(filepath, original, patched):
    """Apply one patch to a file. Returns True if modified."""
    if not os.path.exists(filepath):
        print(f"  SKIP {filepath} (not found)")
        return False

    with open(filepath, "r") as f:
        lines = f.readlines()

    # Check if already patched
    if find_block(lines, patched) >= 0:
        print(f"  OK   {filepath} (already patched)")
        return False

    # Find original block
    idx = find_block(lines, original)
    if idx < 0:
        print(f"  WARN {filepath} (pattern not found — manually check)")
        return False

    # Apply patch
    lines[idx:idx + len(original)] = patched
    with open(filepath, "w") as f:
        f.writelines(lines)
    print(f"  PATCH {filepath} line {idx + 1}")
    return True


def main():
    # Determine repo root (script is in ports/amiga/patches/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.normpath(os.path.join(script_dir, "..", "..", ".."))
    os.chdir(root)

    print("Patching m68k iter_buf heap allocation...")
    print(f"Root: {root}")

    modified = 0
    for filepath, original, patched in PATCHES:
        if patch_file(filepath, original, patched):
            modified += 1

    print(f"\nDone: {modified} file(s) modified, "
          f"{len(PATCHES) - modified} already patched or skipped.")


if __name__ == "__main__":
    main()
