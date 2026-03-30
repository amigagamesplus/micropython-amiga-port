# Patches for upstream MicroPython files

These patches modify files outside `ports/amiga/` and must be reapplied
after any rebase on upstream MicroPython.

## mpstate_alignment.patch

Adds a `uint16_t _gc_lock_pad` field after `gc_lock_depth` in
`mp_state_thread_t` (file `py/mpstate.h`).

### Why this patch is needed

On m68k (and any architecture using `MICROPY_OBJ_REPR_A` without
`MICROPY_STACK_CHECK`), the struct layout of `mp_state_thread_t` is:

    char *stack_top;        // offset 0, 4 bytes
    uint16_t gc_lock_depth; // offset 4, 2 bytes
    // ROOT POINTER SECTION starts here at offset 6

Offset 6 is not aligned to 4 bytes. This causes two critical bugs:

1. **GC root scan corruption**: `gc_collect_start()` scans root pointers
   as an array of `void *` (4-byte aligned). Starting at offset 6 means
   every pointer is read from a 2-byte-shifted position, producing
   garbage values that mark random heap blocks as live or miss real
   pointers. This triggers the `gc.c:952` assertion in `gc_free()` and
   can silently corrupt the heap.

2. **sys.argv misidentified as qstr**: `mp_sys_argv_obj` (an inline
   `mp_obj_list_t` in `MP_STATE_VM`) ends up at an address where
   bits 1:0 != 0. In `MICROPY_OBJ_REPR_A`, the tag bits classify it
   as a qstr instead of an object pointer, so `sys.argv` returns
   `True`, `None`, or crashes.

The 2-byte pad after `gc_lock_depth` pushes the root pointer section
to offset 8 (aligned to 4), fixing both issues.

### How to apply

```sh
cd ../..   # from ports/amiga/ to repo root
git apply ports/amiga/patches/mpstate_alignment.patch
```

### When to reapply

After any `git rebase`, `git merge`, or `git pull` that updates
upstream MicroPython, check if `py/mpstate.h` was modified and
reapply if the patch was lost.

## patch_iter_buf_heap.py

Python script that patches 7 files in `py/` to force heap allocation for
iterator buffers instead of using the C stack.

### Why this patch is needed

On m68k, `mp_obj_iter_buf_t` allocated on the C stack can be misaligned,
causing the VM to fail to recognize the iterator object. This manifests as
`TypeError: 'X' object isn't an iterator` on `for` loops, `in` operator,
`all()`, `any()`, `sum()`, `min()`, `max()`, sequence unpacking, and
`str.join()`.

The fix passes `NULL` instead of `&iter_buf` to `mp_getiter()`, which
forces MicroPython to allocate the iterator on the GC heap (always
properly aligned) instead of the C stack.

### Files patched

- `py/vm.c` — `MP_BC_GET_ITER_STACK` opcode
- `py/runtime.c` — `in` operator, star args unpacking, sequence unpacking
- `py/modbuiltins.c` — `all()`, `any()`, `min()`/`max()`, `sum()`
- `py/objdeque.c` — `deque.extend()`
- `py/objdict.c` — dict view printing
- `py/objset.c` — `set.isdisjoint()`, `set.issubset()`
- `py/objstr.c` — `bytes()` constructor

### How to apply

```sh
cd ../..   # from ports/amiga/ to repo root
python3 ports/amiga/patches/patch_iter_buf_heap.py
```

### When to reapply

After any `git rebase`, `git merge`, or `git pull` that updates upstream
MicroPython. The script is idempotent — safe to run multiple times.
