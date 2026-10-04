# Pd C API reference (m_pd.h)

A lookup sheet of the signatures externals use most, grouped as Types, Atoms, Classes & methods, Inlets & outlets, DSP, Memory
and Console output. When something is missing here or the Pd version matters, grep your `m_pd.h` (see SKILL.md → "Check the real API").

## Types

Prefer the `t_` types over raw C types, because they follow Pd's build precision.

| type | description |
|------|-------------|
| `t_atom` | a message atom (tagged float/symbol/pointer) |
| `t_float` | floating-point value (Pd's number type) |
| `t_floatarg` | float as passed to methods/constructors |
| `t_symbol` | interned symbol; `s->s_name` is the C string |
| `t_gpointer` | pointer to a graphical/data object |
| `t_int` | **pointer-sized integer** — for the `perform` `w[]` array only, *not* ordinary ints |
| `t_signal` | a signal: `s_vec` (samples), `s_length` (= legacy `s_n`), `s_sr` (rate), `s_nchans` (0.54+) |
| `t_sample` | one audio sample (floating point) |
| `t_outlet` / `t_inlet` | an outlet / inlet handle |
| `t_object` | object internals; **first member of a graphical object's data space** |
| `t_pd` | base "pd" type; first member of a non-graphical (`CLASS_PD`) data space |
| `t_class` | a Pd class |
| `t_method` | generic method pointer (cast handlers to this in `class_add*`) |
| `t_newmethod` | constructor pointer |

## Atoms

### Setting atoms (macros)

```c
SETFLOAT(atom, f)     /* set *atom to A_FLOAT f         */
SETSYMBOL(atom, s)    /* set *atom to A_SYMBOL s         */
SETPOINTER(atom, pt)  /* set *atom to A_POINTER pt       */
```

### Reading atoms

```c
t_float   atom_getfloat(t_atom *a);                          /* A_FLOAT value, else 0.0          */
t_float   atom_getfloatarg(int which, int argc, t_atom *av); /* av[which] as float, else 0.0     */
t_int     atom_getint(t_atom *a);                            /* A_FLOAT value as int, else 0     */
t_symbol *atom_getsymbol(t_atom *a);                         /* A_SYMBOL ptr, else 0             */
t_symbol *atom_gensym(t_atom *a);                            /* any atom -> a symbol (stringify) */
void      atom_string(t_atom *a, char *buf, unsigned bufsize); /* atom -> C string (caller-allocd) */
```

`atom_getfloatarg` is bounds-safe: it returns 0 when `which >= argc`. Use these accessors instead of reading the union
(`argv[i].a_w.w_float`). If a non-number should count as an error rather than read as 0, check `argv[i].a_type == A_FLOAT` first.

### Symbols

```c
t_symbol *gensym(const char *s);   /* intern a C string; returns the unique t_symbol* */
```

Symbols are unique by content — compare two `t_symbol *` with `==`, not `strcmp`.

## Classes & methods

### class_new

```c
t_class *class_new(t_symbol *name, t_newmethod newmethod, t_method freemethod,
                   size_t size, int flags, t_atomtype arg1, ...);
```

- `name` — symbolic class name (`gensym("foo")`).
- `newmethod` — constructor; `freemethod` — destructor (`0` if none).
- `size` — `sizeof(t_yourdata)`.
- `flags` — graphical presentation:

| flag | meaning |
|------|---------|
| `CLASS_DEFAULT` (or `0`) | normal object, one inlet |
| `CLASS_PD` | object without graphical presentation (data space starts with `t_pd`) |
| `CLASS_GOBJ` | pure graphical object (arrays, graphs) |
| `CLASS_PATCHABLE` | normal patchable object |
| `CLASS_NOINLET` | suppress the default leftmost inlet |

- `arg1, ...`: creation-argument types, 0-terminated, at most six typed (`A_DEFFLOAT`, `A_DEFSYMBOL`) or a single `A_GIMME`.
- `CLASS_MULTICHANNEL` (0.54+) can be OR-ed into `flags` for multichannel signal objects (see DSP below).

### class_addmethod

```c
void class_addmethod(t_class *c, t_method fn, t_symbol *sel, t_atomtype arg1, ...);
```

The arg-type table and the convenience adders (`class_addbang`, `class_addfloat`, `class_addlist`, …) and their handler
signatures are in `control-objects.md`. Use `A_CANT` for internal selectors like `dsp`.

### Other class functions

```c
void class_addcreator(t_newmethod newmethod, t_symbol *s, t_atomtype type1, ...);
```
Adds an alias name `s` (and its arg types) for the constructor — e.g. so `f` also creates a `float` object.

```c
void class_sethelpsymbol(t_class *c, t_symbol *s);
```
Makes right-click › Help open `<s>-help.pd` instead of `<classname>-help.pd`. Use it to let several classes share one help patch.

```c
t_pd *pd_new(t_class *cls);
```
Allocates and initializes an instance of `cls`; call it first in every constructor and cast the result to
your data-space pointer.

## Inlets & outlets

Every inlet/outlet function takes the object's `t_object` (as `&x->x_obj`) as the `owner`.

### Inlets

```c
t_inlet *inlet_new(t_object *owner, t_pd *dest, t_symbol *s1, t_symbol *s2);
```
Active inlet: a message with selector `s1` arriving here is dispatched as selector `s2` (which must be a
registered method). `dest` is normally `&owner->ob_pd`. Use `&s_signal`/`&s_signal` for an extra signal
inlet. `gensym("")` as `s1`/`s2` makes the inlet unreachable from the left inlet.

```c
t_inlet *floatinlet_new(t_object *owner, t_float *fp);     /* passive: writes float  -> *fp */
t_inlet *symbolinlet_new(t_object *owner, t_symbol **sp);  /* passive: writes symbol -> *sp */
t_inlet *pointerinlet_new(t_object *owner, t_gpointer *gp);/* passive: writes pointer-> *gp */
```
Passive inlets write incoming values straight into your data space — no callback, no validation.

### Outlets

```c
t_outlet *outlet_new(t_object *owner, t_symbol *s);
```
`s` declares the type (readability only): `&s_bang`, `&s_float`, `&s_symbol`, `&s_pointer`, `&s_list`,
`&s_signal`, or `0` for "anything". The first outlet is also saved in `owner->ob_outlet`; store the
returned handle yourself for any additional outlets.

```c
void outlet_bang(t_outlet *x);
void outlet_float(t_outlet *x, t_float f);
void outlet_symbol(t_outlet *x, t_symbol *s);
void outlet_pointer(t_outlet *x, t_gpointer *gp);
void outlet_list(t_outlet *x, t_symbol *s, int argc, t_atom *argv);     /* pass &s_list as s */
void outlet_anything(t_outlet *x, t_symbol *s, int argc, t_atom *argv); /* s = your selector  */
```

```c
void inlet_free(t_inlet *x);
void outlet_free(t_outlet *x);
```

## DSP

See `signal-objects.md` for the full workflow; signatures here.

```c
void my_dsp_method(t_x *x, t_signal **sp);   /* registered for "dsp" with A_CANT */
```
`sp` holds the signals: inputs left→right, then outputs left→right. Each `t_signal` has `s_vec`
(`t_sample *` buffer) and `s_length` (vector length; `s_n` is the pre-0.54 alias and still works).

```c
CLASS_MAINSIGNALIN(<class>, <datatype>, <floatmember>);
```
Makes the leftmost inlet a signal inlet; `<floatmember>` is a dummy `t_float` in the data space used to
turn a float message on that inlet into a constant signal. The main signal inlet then can't have a `float`
method.

```c
void dsp_add(t_perfroutine f, int n, ...);          /* schedule f; n = count of trailing pointer args */
void dsp_addv(t_perfroutine f, int n, t_int *vec);  /* same, but args supplied in vec[] (variable I/O) */
```

```c
t_int *my_perform(t_int *w);
```
`w[1]` is the first pointer passed to `dsp_add` (`w[0]` is the routine's own address). Cast each back to
its type. **Return `w + (n + 1)`.**

```c
t_float sys_getsr(void);      /* system sample rate (inside dsp, prefer sp[0]->s_sr) */
int     sys_getblksize(void); /* top-level block size; NOT necessarily your vector length (block~/switch~) */
```

**Multichannel (Pd 0.54+).** If the class sets `CLASS_MULTICHANNEL`, each `t_signal` carries `s_nchans` channels stored
back-to-back in `s_vec` (`s_nchans * s_length` samples). Outputs must be created in the `dsp` method with
`signal_setmultiout(&sp[k], nchans)`. Without the flag, Pd hands the object single-channel signals. Read the comment block
next to `CLASS_MULTICHANNEL` in `m_pd.h` before using it.

## Memory

Prefer Pd's allocators to bare `malloc`/`free`.

```c
void *getbytes(size_t nbytes);                 /* allocate, zeroed */
void *copybytes(void *src, size_t nbytes);     /* allocate + copy  */
void  freebytes(void *x, size_t nbytes);       /* free (pass the same size) */
void *resizebytes(void *x, size_t old, size_t new); /* realloc with old/new sizes */
```

`getbytes` returns `NULL` on failure, so check the result. Free everything you allocate in the destructor.

## Console output

```c
void post(const char *fmt, ...);                       /* printf-style line to the Pd console */
void pd_error(const void *object, const char *fmt, ...); /* error tied to `object` (NULL ok) — */
                                                         /* the user can click it to find the box */
void logpost(const void *object, int level, const char *fmt, ...); /* leveled message: */
                                                                   /* 0 fatal,1 error,2 normal,3 verbose,4 more */
```

`post` adds the newline itself. `error()` was **removed**, so use `pd_error(x, ...)` (or `NULL`). `verbose()` is
`PD_DEPRECATED`, so use `logpost` instead. None of these are real-time safe, so never call them from `perform`.
