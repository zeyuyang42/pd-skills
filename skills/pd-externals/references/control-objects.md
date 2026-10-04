# Control (message) objects

Covers messages, methods, creation arguments, inlets and outlets. For audio, see `signal-objects.md`.

## Messages: selectors and atoms

A message is a **selector** symbol followed by **atoms**. Each atom is one of `A_FLOAT`, `A_SYMBOL` or `A_POINTER`,
and its type is in `a.a_type`. The predefined selectors have fixed addresses, so they need no `gensym`:

| selector | address | payload |
|----------|---------|---------|
| `bang` | `&s_bang` | none (a trigger) |
| `float` | `&s_float` | one `A_FLOAT` |
| `symbol` | `&s_symbol` | one `A_SYMBOL` |
| `pointer` | `&s_pointer` | one `A_POINTER` |
| `list` | `&s_list` | any atoms |
| *(signal)* | `&s_signal` | audio, not a message |

A message starting with a number and no explicit selector is auto-classified: one atom → `float`,
several → `list`. So `12.4` ≡ `float 12.4`, and `1 for you` ≡ `list 1 for you`. Any other word is a
custom selector; the receiving class needs a method for it (or an `anything` catch-all).

## Registering methods

Register every handler in the setup function. The method's C signature must match how you register it.

### Convenience registrations (for the predefined selectors)

| call | method signature |
|------|------------------|
| `class_addbang(c, fn)` | `void fn(t_x *x);` |
| `class_addfloat(c, fn)` | `void fn(t_x *x, t_floatarg f);` |
| `class_addsymbol(c, fn)` | `void fn(t_x *x, t_symbol *s);` |
| `class_addpointer(c, fn)` | `void fn(t_x *x, t_gpointer *p);` |
| `class_addlist(c, fn)` | `void fn(t_x *x, t_symbol *s, int argc, t_atom *argv);` |
| `class_addanything(c, fn)` | `void fn(t_x *x, t_symbol *s, int argc, t_atom *argv);` |

`anything` is the catch-all: it fires for any selector without its own method, with `s` set to that selector.

### Custom selectors: `class_addmethod`

```c
void class_addmethod(t_class *c, t_method fn, t_symbol *sel, t_atomtype arg1, ...);
```

`sel` is the selector (`gensym("reset")`). The `arg…` list declares the atoms that follow it, is
0-terminated, and **type-checks/coerces** the arguments for you so your handler receives plain C types:

| arg type | meaning | handler receives |
|----------|---------|------------------|
| `A_DEFFLOAT` | number, defaults to 0 if absent | `t_floatarg` |
| `A_FLOAT` | required number | `t_floatarg` |
| `A_DEFSYMBOL` | symbol, defaults to `&s_` (empty) | `t_symbol *` |
| `A_SYMBOL` | required symbol | `t_symbol *` |
| `A_POINTER` | a pointer | `t_gpointer *` |
| `A_GIMME` | the raw atom list (any length/types) | `t_symbol *s, int argc, t_atom *argv` |
| `A_CANT` | not callable from a patch — for internal selectors like `dsp` | (see signal-objects.md) |

Max **six** type-checked args. For more, or for variable/mixed argument lists, use `A_GIMME` and read the
atoms yourself with `atom_getfloat(argv+i)` / `atom_getsymbol(argv+i)` / `atom_getfloatarg(i, argc, argv)`.

```c
class_addmethod(c, (t_method)x_set,   gensym("set"),   A_DEFFLOAT, 0);              /* "set 5"     */
class_addmethod(c, (t_method)x_bound, gensym("bound"), A_DEFFLOAT, A_DEFFLOAT, 0);  /* "bound 0 9" */
/* handlers: void x_set(t_x *x, t_floatarg f);  void x_bound(t_x *x, t_floatarg lo, t_floatarg hi); */
```

## Creation arguments

The args you pass to `class_new` *after* the flags declare the object's creation arguments (typed
exactly like `class_addmethod`, 0-terminated, max six typed). The constructor receives matching params:

| `class_new` arg | constructor parameter |
|-----------------|-----------------------|
| `A_DEFFLOAT` | `t_floatarg f` |
| `A_DEFSYMBOL` | `t_symbol *s` |
| `A_GIMME` | `t_symbol *s, int argc, t_atom *argv` |

```c
/* one optional float arg: [counter 10] */
counter_class = class_new(gensym("counter"), (t_newmethod)counter_new, 0,
                          sizeof(t_counter), CLASS_DEFAULT, A_DEFFLOAT, 0);
void *counter_new(t_floatarg f) { ... }

/* arbitrary args: [counter 0 9 2] — parse argc/argv yourself */
counter_class = class_new(gensym("counter"), (t_newmethod)counter_new, 0,
                          sizeof(t_counter), CLASS_DEFAULT, A_GIMME, 0);
void *counter_new(t_symbol *s, int argc, t_atom *argv) { ... }
```

With `A_GIMME`, a `switch(argc)` with fall-through is the idiomatic way to apply defaults (see the worked
counter below).

## Inlets

The **leftmost inlet always exists** and is "active": messages there dispatch to your registered methods.
The default inlet is created for you (suppress it with the `CLASS_NOINLET` flag if you truly want none).
Create additional inlets in the constructor, **in left-to-right order** (creation order = on-screen order).

### Active inlets — route a message to a method

```c
inlet_new(&x->x_obj, &x->x_obj.ob_pd, gensym("list"), gensym("bound"));
```

This makes a right inlet where an incoming `list` (3rd arg) is re-labeled as selector `bound` (4th arg),
so it calls your `bound` method. Consequences:

- The substituting selector (`bound`) must be registered with `class_addmethod`.
- You can simulate that inlet from the left inlet by sending the substituted selector there.
- A right inlet can map **only one** selector — no `anything` catch-all on a right inlet.
- Use `gensym("")` as the substitute to make the inlet *unreachable* from the left inlet.

### Passive inlets — write straight into a variable (no method)

```c
floatinlet_new(&x->x_obj, &x->step);       /* float  -> x->step              */
symbolinlet_new(&x->x_obj, &x->name);      /* symbol -> x->name (t_symbol *)  */
pointerinlet_new(&x->x_obj, &x->ptr);      /* pointer-> x->ptr (t_gpointer)   */
```

Passive inlets store the value without calling you back, so they can't validate it or react when it arrives.

## Outlets

Create outlets in the constructor (again, order = on-screen order). `outlet_new`'s symbol declares the
type — purely for readability/connection hints; mechanically the types are interchangeable:

```c
x->f_out = outlet_new(&x->x_obj, &s_float);  /* a float outlet  */
x->b_out = outlet_new(&x->x_obj, &s_bang);   /* a bang outlet   */
/* &s_symbol, &s_list, &s_signal, or 0 for an "anything" outlet */
```

The **first** outlet's pointer is also stored in `x->x_obj.ob_outlet`, so with a single outlet you can skip
saving the handle. For **multiple outlets you must store each `t_outlet *`** in your struct, because
`ob_outlet` only holds one.

Send through a specific outlet handle:

```c
outlet_bang(x->b_out);
outlet_float(x->f_out, 42.f);
outlet_symbol(x->s_out, gensym("done"));
outlet_list(x->l_out, &s_list, argc, argv);
outlet_anything(x->a_out, gensym("mysel"), argc, argv);
```

### Output order: right to left

`outlet_*` runs everything downstream of that outlet before it returns. So when one message fires several outlets,
fire the **rightmost first**: by the time the left outlet triggers its chain, the right-hand values are already in place.
This matches `[trigger]`. Create outlets left to right and fire them in reverse:

```c
/* constructor: left outlet first, right outlet second */
x->out_left  = outlet_new(&x->x_obj, &s_float);
x->out_right = outlet_new(&x->x_obj, &s_float);

/* method: fire RIGHT before LEFT */
outlet_float(x->out_right, remainder);
outlet_float(x->out_left,  quotient);
```

## Worked example 1 — simple counter (state + one outlet)

Bang outputs the count, then increments. Note the reentrancy-safe ordering.

```c
#include "m_pd.h"

static t_class *counter_class;

typedef struct _counter {
  t_object x_obj;
  int i_count;            /* plain int — ordinary integer state */
} t_counter;

void counter_bang(t_counter *x) {
  t_float f = x->i_count; /* capture BEFORE mutating … */
  x->i_count++;
  outlet_float(x->x_obj.ob_outlet, f);  /* … so a feedback patch stays well-defined */
}

void *counter_new(t_floatarg f) {
  t_counter *x = (t_counter *)pd_new(counter_class);
  x->i_count = f;
  outlet_new(&x->x_obj, &s_float);
  return (void *)x;
}

void counter_setup(void) {
  counter_class = class_new(gensym("counter"), (t_newmethod)counter_new, 0,
                            sizeof(t_counter), CLASS_DEFAULT, A_DEFFLOAT, 0);
  class_addbang(counter_class, counter_bang);
}
```

## Worked example 2 — complex counter (args, extra inlets, two outlets, methods)

Lower/upper bound + step; `set`/`reset`/`bound` messages; bangs a second outlet on overrun.

```c
#include "m_pd.h"

static t_class *counter_class;

typedef struct _counter {
  t_object  x_obj;
  int       i_count;
  t_float   step;
  int       i_down, i_up;
  t_outlet *f_out, *b_out;   /* must store handles: more than one outlet */
} t_counter;

void counter_bang(t_counter *x) {
  t_float f = x->i_count;
  int step = x->step;
  x->i_count += step;
  if (x->i_down - x->i_up) {                 /* only wrap if bounds differ */
    if ((step > 0) && (x->i_count > x->i_up))      { x->i_count = x->i_down; outlet_bang(x->b_out); }
    else if (x->i_count < x->i_down)               { x->i_count = x->i_up;   outlet_bang(x->b_out); }
  }
  outlet_float(x->f_out, f);
}

void counter_reset(t_counter *x)                       { x->i_count = x->i_down; }
void counter_set(t_counter *x, t_floatarg f)           { x->i_count = f; }
void counter_bound(t_counter *x, t_floatarg f1, t_floatarg f2) {
  x->i_down = (f1 < f2) ? f1 : f2;
  x->i_up   = (f1 > f2) ? f1 : f2;
}

void *counter_new(t_symbol *s, int argc, t_atom *argv) {
  t_counter *x = (t_counter *)pd_new(counter_class);
  t_float f1 = 0, f2 = 0;
  x->step = 1;
  switch (argc) {                            /* fall-through applies defaults */
    default:
    case 3: x->step = atom_getfloat(argv + 2);
    case 2: f2 = atom_getfloat(argv + 1);
    case 1: f1 = atom_getfloat(argv); break;
    case 0: break;
  }
  if (argc < 2) f2 = f1;
  x->i_down = (f1 < f2) ? f1 : f2;
  x->i_up   = (f1 > f2) ? f1 : f2;
  x->i_count = x->i_down;

  inlet_new(&x->x_obj, &x->x_obj.ob_pd, gensym("list"), gensym("bound")); /* right inlet -> bound */
  floatinlet_new(&x->x_obj, &x->step);                                    /* passive step inlet  */
  x->f_out = outlet_new(&x->x_obj, &s_float);
  x->b_out = outlet_new(&x->x_obj, &s_bang);
  return (void *)x;
}

void counter_setup(void) {
  counter_class = class_new(gensym("counter"), (t_newmethod)counter_new, 0,
                            sizeof(t_counter), CLASS_DEFAULT, A_GIMME, 0);
  class_addbang  (counter_class, counter_bang);
  class_addmethod(counter_class, (t_method)counter_reset, gensym("reset"), 0);
  class_addmethod(counter_class, (t_method)counter_set,   gensym("set"),   A_DEFFLOAT, 0);
  class_addmethod(counter_class, (t_method)counter_bound, gensym("bound"), A_DEFFLOAT, A_DEFFLOAT, 0);
}
```
