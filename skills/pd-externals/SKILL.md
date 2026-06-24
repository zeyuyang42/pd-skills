---
name: pd-externals
description: >-
  Write, compile, and debug C externals (plugins) for Pure Data (Pd / libpd).
  Use this whenever the user is creating or modifying a Pd external in C: working with
  `m_pd.h`, writing a control object or a signal/tilde (`~`) object, dealing with
  `class_new` / `class_addmethod` / inlets / outlets, writing a DSP `perform` routine or
  `dsp_add` / `CLASS_MAINSIGNALIN`, freeing object resources, or building a
  `.pd_linux` / `.pd_darwin` / `.dll` with a Makefile or pd-lib-builder. Trigger this
  even when the user does not say "external" explicitly — e.g. "make a Pure Data object
  in C", "write a Pd audio plugin", "my Pd object crashes when I turn on DSP", "add an
  inlet to my pd~ object", "why does my perform routine read garbage". Also use it for
  conceptual questions about how Pd classes, atoms, selectors, or the DSP graph work.
---

# Writing Pure Data externals in C

An **external** is a Pd object class written in C, compiled to a shared library, and loaded
at runtime. Once loaded it is indistinguishable from a built-in object. This skill gives you
the boilerplate, the conventions, the API, and — most importantly — the small set of rules
that, if broken, silently corrupt audio or crash Pd.

## How to use this skill

- **Creating an external?** Start from a template in `assets/` (copy it, don't retype boilerplate), rename the placeholders, then follow the Workflow below. Use `assets/Makefile` for the build.
- **Debugging a crash or wrong output?** Read the "Crash & corruption rules" section first —
  almost every Pd-specific bug is one of those. Then consult `references/`.
- **Conceptual / API question?** The mental model below plus `references/api-reference.md` cover it.

Read the reference files only when you need them (they exist so this file stays scannable):

| File | Read it when… |
|------|---------------|
| `references/control-objects.md` | Building a message (non-audio) object: atoms, selectors, multiple inlets/outlets, creation arguments, `class_addmethod`. |
| `references/signal-objects.md` | Building a `~` (audio/DSP) object: `CLASS_MAINSIGNALIN`, the `dsp` method, `dsp_add`, the `perform` routine, multi-channel/variable I/O. |
| `references/api-reference.md` | You need an exact signature, type, macro, or the list of `outlet_*` / `atom_get*` / printing functions. |
| `references/building.md` | Compiling, Makefiles, pd-lib-builder, platform file extensions, double-precision builds, where `m_pd.h` lives, help patches. |

## Mental model

Pd is object-oriented C. Two kinds of memory matter:

- **Class space** — one shared `t_class *` per class, created once in the setup function. Methods
  (message handlers) are registered onto the class here.
- **Data space** — a per-instance `struct` you define. Its **first member must be `t_object x_obj`**
  (or `t_pd`, for non-graphical objects). Pd stores the object's inlets/outlets and internals there,
  and casts your struct pointer to `t_object *` — so the first-member rule is not style, it's an ABI
  requirement. Violating it corrupts every object.

Communication happens through **messages**: a *selector* (a symbol like `bang`, `float`, `list`, or any
custom word) plus a list of *atoms* (each an `A_FLOAT`, `A_SYMBOL`, or `A_POINTER`). You register a method
per selector; Pd dispatches to it. Numbers in Pd are always `t_float` — there is no integer atom.
Audio is separate: it flows as **signals** (blocks of `t_sample`) through signal inlets/outlets and is
processed in a `perform` routine, not via messages.

Symbols are interned: `gensym("foo")` returns a unique `t_symbol *` for `"foo"`; compare symbols by
pointer. Common ones have direct addresses (`&s_bang`, `&s_float`, `&s_list`, `&s_signal`, …).

## The six pieces of every external

Every external is the same skeleton. Here is the minimal control object, annotated — internalize this
shape and the rest is variation:

```c
#include "m_pd.h"                              /* 1. the Pd API */

static t_class *helloworld_class;              /* 2. the class pointer (one per class) */

typedef struct _helloworld {                   /* 3. the data space (per instance) */
  t_object x_obj;                              /*    MUST be first */
} t_helloworld;

void helloworld_bang(t_helloworld *x) {        /* 4. a method: handles the "bang" message */
  post("Hello world !!");                      /*    post() = printf to the Pd console */
}

void *helloworld_new(void) {                   /* 5. the constructor (new method) */
  t_helloworld *x = (t_helloworld *)pd_new(helloworld_class);
  /* initialise variables, create inlets/outlets here */
  return (void *)x;                            /*    return NULL => Pd reports "couldn't create" */
}

void helloworld_setup(void) {                  /* 6. setup: runs once when the library loads */
  helloworld_class = class_new(gensym("helloworld"),
        (t_newmethod)helloworld_new,           /*    constructor */
        0,                                     /*    destructor (0 = none needed) */
        sizeof(t_helloworld),                  /*    data-space size, for Pd to allocate */
        CLASS_DEFAULT,                         /*    graphical flags */
        0);                                    /*    creation-arg types, 0-terminated (none here) */
  class_addbang(helloworld_class, helloworld_bang);  /* register the bang handler */
}
```

The setup function's name is load-bearing: Pd calls `<libname>_setup()` when it loads `<libname>`. For a
single-object library, the object name, the source file basename, and the setup-function prefix all match.

## Workflow for creating an external

1. **Control or signal?** If it processes audio (a `~` object), use `assets/signal-template.c` and read
   `references/signal-objects.md`. Otherwise use `assets/control-template.c` and, if it needs more than a
   bang, `references/control-objects.md`.
2. **Copy the template** to `<name>.c` (signal objects keep the `~` in the filename, e.g. `gain~.c`).
   Replace the placeholder name everywhere — struct `t_<name>`, the `<name>_*` functions, the `gensym("<name>")`,
   and the setup function `<name>_setup`. Consistency here is what lets Pd find and load the object.
3. **Define the data space**: add one struct member per piece of state, plus stored `t_outlet *` /
   `t_inlet *` handles for any iolet beyond the leftmost one.
4. **Constructor**: parse creation args, initialise state, create inlets/outlets *in left-to-right order*
   (that order is the on-screen order), return the instance.
5. **Methods**: write one handler per message and register each in `setup` (`class_addbang`, `class_addfloat`,
   `class_addmethod`, …). The method signature must match the registration — see `references/control-objects.md`.
6. **Destructor** (only if you allocated anything — heap memory, or extra iolets you want to free): register it
   as the 3rd arg of `class_new` and free there.
7. **Build** with a Makefile based on `assets/Makefile` (see `references/building.md`), then load the binary in
   Pd and exercise it from a patch.

## Naming conventions (follow them — Pd and other devs rely on them)

| Thing | Pattern | Example |
|-------|---------|---------|
| data-space struct | `t_<name>` / `struct _<name>` | `t_counter` |
| class pointer | `static t_class *<name>_class;` | `counter_class` |
| constructor | `<name>_new` | `counter_new` |
| destructor | `<name>_free` | `xfade_tilde_free` |
| setup (required name) | `<name>_setup` | `counter_setup` |
| method | `<name>_<selector>` | `counter_bang`, `counter_set` |
| signal object name | ends in `~`; in C, `~`→`_tilde` | object `gain~`, fns `gain_tilde_*` |

## Crash & corruption rules (the Pd-specific bugs)

These cause the overwhelming majority of "works then crashes" / "audio is garbage" reports. Each has a reason —
understand the reason and you'll spot the bug.

- **`t_object` (or `t_pd`) must be the first struct member.** Pd casts your pointer to `t_object *`; if it isn't
  first, inlet/outlet bookkeeping writes over your fields. Non-negotiable.
- **In the `perform` routine, your pointers start at `w[1]`, not `w[0]`.** `w[0]` holds the address of the perform
  routine itself (Pd's DSP graph uses it internally). `w[1]` is the first pointer you passed to `dsp_add`.
- **A `perform` routine must return `w + (n + 1)`**, where `n` is the count you gave as `dsp_add`'s 2nd argument.
  It points just past your slots so Pd can find the next object. Return `w + n` (or anything else) and the DSP
  chain walks off into garbage → crash. (5 pointers → `return (w + 6);`.)
- **Register the `dsp` method with `A_CANT`:**
  `class_addmethod(c, (t_method)x_dsp, gensym("dsp"), A_CANT, 0);` — this prevents a user from typing a `dsp`
  message into a box and crashing Pd by invoking it with the wrong arguments.
- **In-place signals: read input before writing output.** Pd optimizes the DSP graph and may give an in signal
  and an out signal the *same* memory address. If you write `out[i]` before reading the `in[i]` you still need,
  you corrupt your own input. Compute from inputs first.
- **`t_int` is a pointer-sized integer for the `perform` `w[]` array only — never use it for ordinary integers.**
  For counters, sizes, loop indices use plain `int`. (Pd numbers are `t_float` / `t_sample`.)
- **A signal inlet made via `CLASS_MAINSIGNALIN` cannot also have a `float` method.** The dummy float member you
  pass to the macro is how a float sent to that inlet becomes a constant signal; adding a `float` handler conflicts.
- **Free what you allocate.** Pd frees its own automatic resources, but heap memory (`getbytes`/`malloc`) and any
  extra inlets/outlets you created must be released in the destructor (`freebytes`, `inlet_free`, `outlet_free`),
  or you leak. Register the destructor as `class_new`'s 3rd argument.
- **Reentrancy: read state into a local, mutate, then output.** `outlet_*` can synchronously re-enter your object
  (e.g. its outlet is patched back to its inlet). The counter idiom — `t_float f = x->count; x->count++; outlet_float(out, f);`
  — sends the value captured *before* mutation, so a feedback patch stays well-defined.
- **When several outlets fire from one message, output right-to-left.** Pd's message passing is depth-first and
  synchronous: emitting on an outlet fully runs everything downstream of it before the next `outlet_*` line executes.
  So if a left outlet fires first, downstream logic may act before the value you were about to send from a right
  outlet exists. Emit on the **rightmost** outlet first, then leftward — the `[trigger]` convention. (Create the
  outlets left-to-right as usual; only the firing order is reversed.) See `references/control-objects.md`.

## Quick build reference

With `assets/Makefile` (pd-lib-builder) and Pd installed, building is just `make`. If Pd's headers aren't on the
default search path, point at them: `make PDDIR=/path/to/Pd` (or `PDINCLUDEDIR=/path/to/pd/src`). On this machine
the headers ship inside `/Applications/Pd-*.app/Contents/Resources` (use that as `PDDIR`). Output extensions are
platform-specific: `.pd_linux`, `.pd_darwin` (macOS), `.dll` (Windows). Full details and a from-scratch
single-file compile command are in `references/building.md`.
