/* ============================================================================
 * Pure Data CONTROL (message) external — starting template.
 *
 * To adapt: replace "myobj" everywhere with your object name (struct t_myobj,
 * the myobj_* functions, gensym("myobj"), and myobj_setup). For a single-object
 * library the object name, the source-file basename, and the setup-function
 * prefix must all match, or Pd won't find/load it.
 *
 * This object: holds a float; bang outputs it; a float sets it; "reset" zeroes
 * it. See references/control-objects.md for inlets/outlets, creation args, and
 * the full message API.
 * ========================================================================== */

#include "m_pd.h"                         /* the Pd API — always first */

static t_class *myobj_class;              /* the class pointer (one per class) */

/* ---- data space: per-instance state. t_object MUST be the first member. ---- */
typedef struct _myobj {
  t_object  x_obj;
  t_float   x_value;                      /* example state */
  t_outlet *x_out;                        /* store outlet handles you create */
} t_myobj;

/* ---- methods: one per message. Signature must match how it's registered. ---- */

/* "bang": output the current value */
void myobj_bang(t_myobj *x) {
  outlet_float(x->x_out, x->x_value);
}

/* "float": store the incoming number (registered with class_addfloat) */
void myobj_float(t_myobj *x, t_floatarg f) {
  x->x_value = f;
}

/* custom "reset" selector, no arguments (registered with class_addmethod) */
void myobj_reset(t_myobj *x) {
  x->x_value = 0;
}

/* ---- constructor: one t_floatarg because class_new declares A_DEFFLOAT ---- */
void *myobj_new(t_floatarg f) {
  t_myobj *x = (t_myobj *)pd_new(myobj_class);

  x->x_value = f;                         /* initialise state from the creation arg */

  /* Create inlets/outlets here, LEFT TO RIGHT (creation order == on-screen order).
   * The leftmost inlet already exists. Examples of extra inlets:
   *   floatinlet_new(&x->x_obj, &x->x_value);                              // passive float inlet
   *   inlet_new(&x->x_obj, &x->x_obj.ob_pd, gensym("list"), gensym("set"));// active inlet -> "set"
   */
  x->x_out = outlet_new(&x->x_obj, &s_float);   /* &s_bang / &s_symbol / &s_list / 0(any) for others */

  return (void *)x;                       /* return NULL => Pd reports "couldn't create" */
}

/* ---- destructor: only needed if you allocate. Register it as class_new's 3rd
 * arg (0 below means none). Free heap memory and any extra iolets here:
 *   void myobj_free(t_myobj *x) { freebytes(x->buf, x->size * sizeof(t_float)); }
 */

/* ---- setup: runs once when the library loads. Name MUST be <name>_setup. ---- */
void myobj_setup(void) {
  myobj_class = class_new(gensym("myobj"),
        (t_newmethod)myobj_new,           /* constructor */
        0,                                /* destructor (0 = none) */
        sizeof(t_myobj),                  /* data-space size */
        CLASS_DEFAULT,                    /* graphical flags */
        A_DEFFLOAT, 0);                   /* creation-arg types, 0-terminated */

  class_addbang (myobj_class, myobj_bang);
  class_addfloat(myobj_class, myobj_float);
  class_addmethod(myobj_class, (t_method)myobj_reset, gensym("reset"), 0);
}
