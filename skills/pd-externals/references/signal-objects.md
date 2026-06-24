# Signal (`~`) objects — audio/DSP

A signal class is an ordinary Pd class plus audio processing. Everything in `control-objects.md` still
applies (you can mix messages and audio in one object); this file adds the DSP machinery.

By convention the object's symbolic name ends in `~` (e.g. `gain~`). In C the `~` becomes `_tilde`:
struct `t_gain_tilde`, functions `gain_tilde_new` / `gain_tilde_dsp` / `gain_tilde_perform`, setup
`gain_tilde_setup`. The **source filename keeps the literal tilde**: `gain~.c`.

## What makes a class a signal class

A class becomes a signal class simply by having a method for the `dsp` selector. When Pd's audio engine
starts, it sends `dsp` to every object; those that respond are wired into the DSP graph.

```c
void gain_tilde_setup(void) {
  gain_tilde_class = class_new(gensym("gain~"),
        (t_newmethod)gain_tilde_new,
        (t_method)gain_tilde_free,         /* destructor: free extra iolets / buffers */
        sizeof(t_gain_tilde),
        CLASS_DEFAULT,
        A_DEFFLOAT, 0);                    /* optional creation arg(s) */

  class_addmethod(gain_tilde_class, (t_method)gain_tilde_dsp, gensym("dsp"), A_CANT, 0);
  CLASS_MAINSIGNALIN(gain_tilde_class, t_gain_tilde, f);
}
```

Two signal-specific lines:

- **`class_addmethod(..., gensym("dsp"), A_CANT, 0)`** registers the DSP setup method. Mark its args
  `A_CANT` so a user can't type a `dsp` message into a box and crash Pd by calling it with wrong arguments.
- **`CLASS_MAINSIGNALIN(class, datatype, f)`** turns the leftmost inlet into a signal inlet. The third
  argument is a **dummy `t_float` member of your struct** (named `f` here). When no signal is patched to
  that inlet, a float message sent there is written into `f` and used as a constant signal. Because of
  this mechanism, **the main signal inlet cannot also have a `float` method.**

## The data space of a signal object

```c
typedef struct _gain_tilde {
  t_object  x_obj;
  t_sample  x_gain;    /* a control parameter */
  t_float   f;         /* dummy for CLASS_MAINSIGNALIN (float-as-signal on inlet 0) */
  t_inlet  *x_in2;     /* handles for extra inlets you create … */
  t_outlet *x_out;     /* … and outlets, so you can free them */
} t_gain_tilde;
```

The dummy `f` is only needed if you use `CLASS_MAINSIGNALIN`. Store `t_inlet *` / `t_outlet *` handles for
every iolet you create beyond the default, so the destructor can release them.

## Creating signal inlets and outlets

In the constructor, an **extra signal inlet** uses `inlet_new` with `&s_signal` as both selectors; a
**signal outlet** uses `outlet_new(&x->x_obj, &s_signal)`:

```c
void *gain_tilde_new(t_floatarg f) {
  t_gain_tilde *x = (t_gain_tilde *)pd_new(gain_tilde_class);
  x->x_gain = f;
  /* extra SIGNAL inlet: */         x->x_in2 = inlet_new(&x->x_obj, &x->x_obj.ob_pd, &s_signal, &s_signal);
  /* or a control (float) inlet: */ /* x->x_in2 = floatinlet_new(&x->x_obj, &x->x_gain); */
  x->x_out = outlet_new(&x->x_obj, &s_signal);
  return (void *)x;
}
```

(The leftmost signal inlet itself is provided by `CLASS_MAINSIGNALIN` — don't create it again.)

## The `dsp` method — wiring perform into the graph

```c
void gain_tilde_dsp(t_gain_tilde *x, t_signal **sp) {
  dsp_add(gain_tilde_perform, 4, x, sp[0]->s_vec, sp[1]->s_vec, sp[0]->s_n);
}
```

`sp` is an array of `t_signal *`, ordered **inputs left→right, then outputs left→right**. With two ins and
two outs: `sp[0]`,`sp[1]` are the in signals, `sp[2]`,`sp[3]` the out signals. Each `t_signal` gives you:

- `sp[i]->s_vec` — the sample buffer (`t_sample *`).
- `sp[i]->s_n` — the block length (number of samples). All vectors in a patch share the same length, so
  reading one (`sp[0]->s_n`) is enough.
- `sp[i]->s_sr` — the sample rate. Use this **exact** field name (`s_sr`, not `sr`) when you need the rate
  inside the dsp method (e.g. ms→samples); it's the per-signal rate and is preferable to `sys_getsr()` here.

`dsp_add(perform, n, ...)` schedules your perform routine; `n` is **the count of pointer args that follow**
(here 4: the object, two vectors, the length). Pass whatever the perform routine needs — typically the
object pointer, the signal vectors, and the block length.

The `dsp` method is the right place to **allocate per-block buffers** (you only learn the block length here):
use `getbytes`, **check the result for `NULL`** (report with `pd_error` and bail if it fails), and free in the
destructor. If `dsp` can run again (sample rate or block size changed), free the old buffer before allocating the
new one, and update your stored size only *after* a successful allocation — so a failed `getbytes` never leaves the
struct describing a buffer that isn't there. If your object's I/O count varies at runtime, build the argument array
yourself and call `dsp_addv` instead of `dsp_add`.

## The `perform` routine — the DSP heart

Called once per signal block. It receives `t_int *w`, an array of the pointers you passed to `dsp_add`,
and must hand back the address just past its slots.

```c
t_int *gain_tilde_perform(t_int *w) {
  t_gain_tilde *x  = (t_gain_tilde *)(w[1]);   /* w[1] = first dsp_add pointer */
  t_sample     *in = (t_sample *)(w[2]);
  t_sample    *out = (t_sample *)(w[3]);
  int            n = (int)(w[4]);
  t_sample    gain = x->x_gain;

  for (int i = 0; i < n; i++)
    out[i] = in[i] * gain;                     /* read in[] before writing out[] (see below) */

  return (w + 5);                              /* n_args (4) + 1 */
}
```

Three rules — break any one and you get crashes or garbage audio:

1. **Indices start at `w[1]`.** `w[0]` is the perform routine's own address (Pd-internal); your first
   pointer is `w[1]`, second `w[2]`, … Cast each back to the type you passed.
2. **Return `w + (n + 1)`** where `n` is the `dsp_add` count. It points just past your slots so Pd can find
   the next object. (4 args → `w + 5`; 5 args → `w + 6`.) A wrong return walks the DSP chain into invalid
   memory → crash.
3. **In-place aliasing: read inputs before writing outputs.** Pd may assign an input and an output the
   *same* buffer address to save a copy. If you overwrite `out[i]` before reading every `in[i]` you still
   need, you clobber your own input. Compute from inputs first (for per-sample ops like above this is
   automatic; for anything reordering or reusing samples, be deliberate).

Keep perform routines real-time safe: no allocation, no locking, no I/O, no `post()` in the hot path.

## Destructor

Free anything you allocated — extra iolets and any `getbytes` buffers:

```c
void gain_tilde_free(t_gain_tilde *x) {
  inlet_free(x->x_in2);
  outlet_free(x->x_out);
  /* freebytes(x->x_buf, x->x_bufsize * sizeof(t_sample)); */
}
```

Strictly, Pd auto-frees inlets/outlets; explicit `inlet_free`/`outlet_free` is shown for completeness and
is required if you do iolet "magic". Heap memory from `getbytes`/`malloc` you **must** free yourself.

## Useful DSP queries

- `float sys_getsr(void);` — system sample rate (e.g. for time→samples conversions).
- `int sys_getblksize(void);` — top-level block size. **Not necessarily** your perform routine's vector
  length: a `block~`/`switch~` can change that. For the actual length use `s_n` from a `t_signal` in your
  `dsp` method.

## Worked example — `xfade~` (crossfade two signals)

Two signal inlets + a `float` mix factor on a third (passive) inlet → one signal out.

```c
#include "m_pd.h"

static t_class *xfade_tilde_class;

typedef struct _xfade_tilde {
  t_object  x_obj;
  t_float   x_pan;    /* mix 0..1 */
  t_float   f;        /* dummy for CLASS_MAINSIGNALIN */
  t_inlet  *x_in2;
  t_inlet  *x_in3;
  t_outlet *x_out;
} t_xfade_tilde;

t_int *xfade_tilde_perform(t_int *w) {
  t_xfade_tilde *x = (t_xfade_tilde *)(w[1]);
  t_sample    *in1 = (t_sample *)(w[2]);
  t_sample    *in2 = (t_sample *)(w[3]);
  t_sample    *out = (t_sample *)(w[4]);
  int            n = (int)(w[5]);
  t_sample     pan = (x->x_pan < 0) ? 0.0 : (x->x_pan > 1) ? 1.0 : x->x_pan;  /* clip */
  for (int i = 0; i < n; i++)
    out[i] = in1[i] * (1 - pan) + in2[i] * pan;
  return (w + 6);                  /* 5 args + 1 */
}

void xfade_tilde_dsp(t_xfade_tilde *x, t_signal **sp) {
  dsp_add(xfade_tilde_perform, 5, x, sp[0]->s_vec, sp[1]->s_vec, sp[2]->s_vec, sp[0]->s_n);
}

void xfade_tilde_free(t_xfade_tilde *x) {
  inlet_free(x->x_in2);
  inlet_free(x->x_in3);
  outlet_free(x->x_out);
}

void *xfade_tilde_new(t_floatarg f) {
  t_xfade_tilde *x = (t_xfade_tilde *)pd_new(xfade_tilde_class);
  x->x_pan = f;
  x->x_in2 = inlet_new(&x->x_obj, &x->x_obj.ob_pd, &s_signal, &s_signal); /* 2nd signal in */
  x->x_in3 = floatinlet_new(&x->x_obj, &x->x_pan);                        /* mix factor in */
  x->x_out = outlet_new(&x->x_obj, &s_signal);
  return (void *)x;
}

void xfade_tilde_setup(void) {
  xfade_tilde_class = class_new(gensym("xfade~"),
        (t_newmethod)xfade_tilde_new, (t_method)xfade_tilde_free,
        sizeof(t_xfade_tilde), CLASS_DEFAULT, A_DEFFLOAT, 0);
  class_addmethod(xfade_tilde_class, (t_method)xfade_tilde_dsp, gensym("dsp"), A_CANT, 0);
  CLASS_MAINSIGNALIN(xfade_tilde_class, t_xfade_tilde, f);
}
```
