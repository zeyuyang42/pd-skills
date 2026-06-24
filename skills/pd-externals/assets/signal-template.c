/* ============================================================================
 * Pure Data SIGNAL (~) external — starting template.
 *
 * To adapt: replace "myobj" everywhere. Note the C naming for tilde objects:
 * the object is "myobj~", but in C the '~' becomes "_tilde" — struct
 * t_myobj_tilde, functions myobj_tilde_*, setup myobj_tilde_setup. The SOURCE
 * FILE keeps the literal tilde: myobj~.c. gensym() uses the real name "myobj~".
 *
 * This object: a gain. One signal in (left), a gain factor on a float inlet
 * (right), one signal out. See references/signal-objects.md for the DSP model,
 * multiple/variable I/O, and the perform-routine rules summarized below.
 * ========================================================================== */

#include "m_pd.h"

static t_class *myobj_tilde_class;

/* ---- data space. t_object first. ---- */
typedef struct _myobj_tilde {
  t_object  x_obj;
  t_float   x_gain;     /* control parameter (written by the float inlet) */
  t_float   f;          /* dummy for CLASS_MAINSIGNALIN: float-as-signal on inlet 0 */
  t_inlet  *x_in2;      /* handles for extra iolets, so the destructor can free them */
  t_outlet *x_out;
} t_myobj_tilde;

/* ---- perform: the DSP heart, called once per signal block ----
 * RULES (break any one => crash or garbage audio):
 *   - your pointers start at w[1]  (w[0] is the perform routine's own address)
 *   - return w + (n + 1), where n is dsp_add's 2nd arg (here 4 -> return w+5)
 *   - read inputs before writing outputs (in/out buffers may be the SAME memory)
 *   - real-time safe: no malloc, no locks, no post()/printf here
 */
t_int *myobj_tilde_perform(t_int *w) {
  t_myobj_tilde *x  = (t_myobj_tilde *)(w[1]);
  t_sample      *in = (t_sample *)(w[2]);
  t_sample     *out = (t_sample *)(w[3]);
  int             n = (int)(w[4]);
  t_sample     gain = x->x_gain;
  int i;

  for (i = 0; i < n; i++)
    out[i] = in[i] * gain;

  return (w + 5);       /* n (4) + 1 */
}

/* ---- dsp: schedule perform when audio starts ----
 * sp[] is inputs left->right then outputs left->right; s_vec is the buffer,
 * s_n the block length. dsp_add's 2nd arg counts the trailing pointers (4 here).
 */
void myobj_tilde_dsp(t_myobj_tilde *x, t_signal **sp) {
  dsp_add(myobj_tilde_perform, 4, x, sp[0]->s_vec, sp[1]->s_vec, sp[0]->s_n);
}

/* ---- destructor: free the iolets we created (and any getbytes buffers) ---- */
void myobj_tilde_free(t_myobj_tilde *x) {
  inlet_free(x->x_in2);
  outlet_free(x->x_out);
}

/* ---- constructor ---- */
void *myobj_tilde_new(t_floatarg f) {
  t_myobj_tilde *x = (t_myobj_tilde *)pd_new(myobj_tilde_class);

  x->x_gain = f;

  /* The leftmost signal inlet is provided by CLASS_MAINSIGNALIN — don't recreate it.
   * Here we add a passive float inlet for the gain. To make an extra SIGNAL inlet
   * instead, use:
   *   x->x_in2 = inlet_new(&x->x_obj, &x->x_obj.ob_pd, &s_signal, &s_signal);
   */
  x->x_in2 = floatinlet_new(&x->x_obj, &x->x_gain);
  x->x_out = outlet_new(&x->x_obj, &s_signal);

  return (void *)x;
}

/* ---- setup ---- */
void myobj_tilde_setup(void) {
  myobj_tilde_class = class_new(gensym("myobj~"),
        (t_newmethod)myobj_tilde_new,
        (t_method)myobj_tilde_free,       /* destructor: we created extra iolets */
        sizeof(t_myobj_tilde),
        CLASS_DEFAULT,
        A_DEFFLOAT, 0);

  /* register the DSP setup method; A_CANT keeps users from crashing Pd by
   * sending a manual "dsp" message */
  class_addmethod(myobj_tilde_class, (t_method)myobj_tilde_dsp, gensym("dsp"), A_CANT, 0);

  /* make the leftmost inlet a signal inlet; 'f' receives float-as-signal there.
   * (Therefore inlet 0 cannot also have a float method.) */
  CLASS_MAINSIGNALIN(myobj_tilde_class, t_myobj_tilde, f);
}
