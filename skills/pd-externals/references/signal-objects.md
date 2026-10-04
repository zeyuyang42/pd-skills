# Signal (`~`) objects — audio/DSP

A signal class is a normal Pd class (everything in `control-objects.md` applies) that also has a method for the
`dsp` selector. When audio starts, Pd sends `dsp` to every object, and the ones that respond are wired into the DSP graph.
Naming: the object `gain~` has C identifiers `t_gain_tilde` and `gain_tilde_*`, and lives in the file `gain~.c`.

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

`CLASS_MAINSIGNALIN(class, type, f)` makes the leftmost inlet a signal inlet. `f` is a **dummy `t_float` member**:
a float sent to an unconnected inlet is stored there and used as a constant signal. That is why this inlet can't also
have a `float` method.

## The data space of a signal object

```c
typedef struct _gain_tilde {
  t_object  x_obj;
  t_float   x_gain;    /* a control parameter */
  t_float   f;         /* dummy for CLASS_MAINSIGNALIN (float-as-signal on inlet 0) */
  t_inlet  *x_in2;     /* handles for extra inlets you create … */
  t_outlet *x_out;     /* … and outlets, so you can free them */
} t_gain_tilde;
```

The dummy `f` is only needed with `CLASS_MAINSIGNALIN`.

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
- `sp[i]->s_n`: the block length. It is `s_length` in Pd 0.54+, where `s_n` remains a compatible alias. All of an
  object's vectors share one length.
- `sp[i]->s_sr`: the sample rate. The field is `s_sr`, not `sr`. Inside `dsp`, prefer it to `sys_getsr()`.

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

The SKILL.md crash rules apply here in full:
- start at `w[1]`
- return `w + (n + 1)`
- read inputs before writing outputs, since buffers may alias
- keep the routine real-time safe

Filter or oscillator state (previous samples, phase) must be read from the struct at the start of `perform` and
written back at the end. Never keep it in a `static`.

## Destructor

Free any `getbytes` buffers. Calling `inlet_free`/`outlet_free` is optional because Pd frees iolets itself:

```c
void gain_tilde_free(t_gain_tilde *x) {
  inlet_free(x->x_in2);
  outlet_free(x->x_out);
  /* freebytes(x->x_buf, x->x_bufsize * sizeof(t_sample)); */
}
```

**Multichannel (0.54+)** works through `CLASS_MULTICHANNEL`, `s_nchans` and `signal_setmultiout`. See `api-reference.md` → DSP and `m_pd.h`.

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
