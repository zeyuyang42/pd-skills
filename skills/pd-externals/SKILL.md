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

An **external** is a Pd class written in C and compiled to a shared library that Pd loads at runtime.
This skill covers the boilerplate, the conventions, and the few rules that, when broken, crash Pd or
corrupt audio.

- **New external:** copy a template from `assets/` (`control-template.c`, `signal-template.c`, `Makefile`),
  rename the placeholders, and follow the Workflow below.
- **Crash or wrong output:** check the Crash & corruption rules first. Almost every Pd-specific bug is one of them.
- **Exact signature or API question:** check `m_pd.h` (see below), then `references/`.

| Reference | Read it when… |
|-----------|---------------|
| `references/control-objects.md` | Messages, atoms, selectors, creation args, extra inlets/outlets, `class_addmethod`. |
| `references/signal-objects.md` | `~` objects: `CLASS_MAINSIGNALIN`, the `dsp` method, `dsp_add`, `perform`. |
| `references/api-reference.md` | Signatures for classes, atoms, iolets, DSP, memory, console output. |
| `references/building.md` | Makefiles, pd-lib-builder, finding `m_pd.h`, file extensions, double precision, loading. |

## Mental model

- **Class:** one `static t_class *` per class, created in the setup function. Methods (message handlers) are registered on it.
- **Instance:** a struct you define. Its **first member must be `t_object x_obj`** (or `t_pd` for `CLASS_PD`).
  Pd casts your pointer to `t_object *`, so this is an ABI requirement, not style.
- **Messages:** a *selector* symbol (`bang`, `float`, `list`, or a custom word) followed by *atoms*
  (`A_FLOAT`, `A_SYMBOL`, `A_POINTER`). Every Pd number is a `t_float`; there is no integer atom.
  `gensym("foo")` interns a symbol, so compare symbols by pointer. Built-in selectors have fixed addresses: `&s_bang`, `&s_float`, …
- **Audio:** signals are blocks of `t_sample` processed in a `perform` routine. They do not travel as messages.

## The skeleton

```c
#include "m_pd.h"

static t_class *hello_class;                      /* one per class */

typedef struct _hello {
  t_object x_obj;                                 /* MUST be first */
} t_hello;

void hello_bang(t_hello *x) { post("hello"); }          /* method for "bang" */

void *hello_new(void) {                           /* constructor */
  t_hello *x = (t_hello *)pd_new(hello_class);
  /* init state, create extra inlets/outlets */
  return (void *)x;                               /* NULL => "couldn't create" */
}

void hello_setup(void) {                          /* Pd calls <name>_setup on load */
  hello_class = class_new(gensym("hello"), (t_newmethod)hello_new,
        0,                                        /* destructor (0 = none) */
        sizeof(t_hello), CLASS_DEFAULT,
        0);                                       /* creation-arg types, 0-terminated */
  class_addbang(hello_class, hello_bang);
}
```

The object name, the source basename, and the `_setup` prefix must match, or Pd can't load the object.
Don't reuse the name of a vanilla object (`clip~`, `line`, …). The built-in takes priority, so your external never loads.

## Workflow

1. **Control or signal?** Signal (`~`) objects start from `assets/signal-template.c`. Everything else starts from `assets/control-template.c`.
2. **Copy and rename:** `<name>.c`, `t_<name>`, `<name>_new`, `<name>_free`, `<name>_<selector>`,
   `<name>_setup`, `gensym("<name>")`. For `foo~`, the C identifiers use `foo_tilde_*` and the file is `foo~.c`.
3. **Data space:** one member per piece of state, plus stored `t_outlet *` handles for every outlet beyond the first.
4. **Constructor:** parse creation args, initialise state, then create inlets and outlets **left to right**
   (creation order is on-screen order).
5. **Methods:** one handler per message, registered in setup. The C signature must match the registration.
6. **Destructor:** only needed for resources you own. Pass it as `class_new`'s 3rd argument.
7. **Build** from `assets/Makefile` (pd-lib-builder): `make`, or `make PDINCLUDEDIR=/path/to/pd/src`. See `references/building.md`.

## Crash & corruption rules

- **`t_object` first** in the struct. Otherwise Pd's bookkeeping overwrites your fields.
- **`perform` arguments start at `w[1]`.** `w[0]` is the routine's own address.
- **`perform` returns `w + (n + 1)`**, where `n` is `dsp_add`'s count (5 pointers → `w + 6`). Any other
  return walks the DSP chain into garbage and crashes Pd.
- **Register `dsp` with `A_CANT`:** `class_addmethod(c, (t_method)x_dsp, gensym("dsp"), A_CANT, 0);`.
  This stops a user from calling it from a patch.
- **In-place buffers:** an input and an output may share memory. Read every input sample you need before writing outputs.
  This matters whenever `out[i]` is not computed from `in[i]` alone. A delay line, for example, must use
  `t_sample s = in[i]; out[i] = buf[p]; buf[p] = s;`. Writing `out[i]` before reading `in[i]` outputs silence.
- **`t_int` is pointer-sized and belongs only in `perform`'s `w[]`.** Use `int` for counters and indices.
- **No `float` method on a `CLASS_MAINSIGNALIN` inlet.** The macro's dummy `t_float` member already turns floats into a constant signal.
- **Free heap memory in the destructor** (`getbytes` → `freebytes`). Pd frees inlets and outlets itself, so
  `inlet_free`/`outlet_free` are optional.
- **Per-instance state lives in the struct, never in `static` locals.** Statics are shared by every instance.
- **Reentrancy:** an `outlet_*` call can re-enter your object before it returns. Read state into a local, update the struct, then output.
- **Several outlets from one message fire right to left** (the `[trigger]` convention). Message passing is
  depth-first and synchronous, so the leftmost outlet must fire last.
- **Real-time safety:** in `perform`, never allocate, lock, do I/O, or call `post()`.

## Check the real API in `m_pd.h`

This skill describes Pd's stable API. The `m_pd.h` you build against is the authority, so check it whenever a signature,
flag, or version matters.

```sh
# locate it
find / -name m_pd.h 2>/dev/null | head        # or narrow to the paths below
#   macOS:   /Applications/Pd-*.app/Contents/Resources/src/
#   Linux:   /usr/include/pd/  or  /usr/local/include/pd/
#   Windows: <Pd install>/src/
H=/path/to/m_pd.h
grep -n 'PD_M[AI][JN]OR_VERSION' "$H"         # which Pd version
grep -n 'EXTERN.*class_addmethod' "$H"        # exact signature of a function
grep -n 'PD_DEPRECATED' "$H"                  # APIs to avoid (e.g. verbose -> logpost)
grep -n -A12 'typedef struct _signal' "$H"    # struct fields (s_length/s_n, s_nchans, s_sr)
grep -n '#define CLASS_' "$H"                 # class flags (CLASS_MULTICHANNEL is 0.54+)
```

When code depends on a newer API, guard it with a version check: `#if PD_MINOR_VERSION >= 54 … #endif`.
If this skill and the header disagree, follow the header.
