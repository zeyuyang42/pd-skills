# Building & loading externals

A Pd external is a shared library that exports a `<name>_setup()` function. Pd resolves the Pd API symbols
(`post`, `class_new`, …) from the host at load time, so you **don't link against a Pd library** on
Linux/macOS — you build a plugin with undefined symbols left to be filled in by Pd. The only header you
need is `m_pd.h`.

## Recommended: pd-lib-builder

[`pd-lib-builder`](https://github.com/pure-data/pd-lib-builder) is the community-standard helper Makefile.
It autodetects the platform, picks the right compiler flags and file extension, and gives you `make` /
`make install` / `make clean`. Your Makefile just declares the library and sources, then includes it:

```make
# Makefile
lib.name = myobj                 # library name (and object name for a single-object lib)
class.sources = myobj.c          # one source per class; basename == object name
datafiles = myobj-help.pd README.md  # extra files for `make install`
PDLIBBUILDER_DIR = ./pd-lib-builder/
include $(PDLIBBUILDER_DIR)/Makefile.pdlibbuilder
```

Vendor `Makefile.pdlibbuilder` next to your project (git submodule or copy). Then:

```sh
make                                  # build myobj.<platform-ext>
make PDDIR=/path/to/Pd                # if m_pd.h isn't on the default search path
make install PDLIBDIR=~/Documents/Pd/externals   # install the libdir
make clean
```

### Pointing at a Pd installation

If `m_pd.h` isn't found automatically, set one of these (as a make argument or in the environment):

| variable | meaning |
|----------|---------|
| `PDDIR` | root of a Pd package; `PDINCLUDEDIR`=`$(PDDIR)/src`, `PDBINDIR`=`$(PDDIR)/bin` are derived |
| `PDINCLUDEDIR` | directory containing `m_pd.h` (overrides the default) |
| `PDBINDIR` | directory containing `pd.dll` (Windows linking only) |
| `PDLIBDIR` | install root for `make install` |

**On this macOS machine** Pd ships its headers inside the app bundle, so:

```sh
make PDDIR=/Applications/Pd-0.55-2.app/Contents/Resources
```

(`m_pd.h` is at `/Applications/Pd-0.55-2.app/Contents/Resources/src/m_pd.h`.)

### Multiple classes in one library

List every source in `class.sources`; each builds to its own object. Add an explicit library setup function
`void <lib.name>_setup(void)` that calls each class's setup, so loading the library registers them all.
A single-object library can skip this — its `<name>_setup` is enough.

## Building one file by hand (no Makefile)

Useful for a quick compile check. Define `PD` and point `-I` at the headers.

**macOS** (plugin bundle; symbols resolved by Pd at load):
```sh
PDINC=/Applications/Pd-0.55-2.app/Contents/Resources/src
cc -DPD -I"$PDINC" -bundle -undefined dynamic_lookup -arch arm64 -o myobj.pd_darwin myobj.c
```
(Drop `-arch arm64`, or use `-arch x86_64 -arch arm64` for a universal binary, as needed.)

**Linux**:
```sh
cc -DPD -I/path/to/pd/src -shared -fPIC -o myobj.pd_linux myobj.c
```

**Windows (MinGW)** — here you *do* link the Pd import lib:
```sh
gcc -DPD -I/path/to/pd/src -shared -o myobj.dll myobj.c -L/path/to/pd/bin -lpd
```

A plain syntax/structure check without producing a loadable binary:
```sh
cc -DPD -I"$PDINC" -fsyntax-only myobj.c
```

## Standard headers (a common build failure)

`m_pd.h` does **not** pull in the C standard library for you. If you call `floor`/`sin`/`pow` you must
`#include <math.h>`; for `memset`/`memcpy` add `<string.h>`; for `malloc`/`rand`/`atoi` add `<stdlib.h>`.
Omitting them is a frequent cause of build failures — on modern compilers an implicit function declaration
is an **error** (C99+), not a warning, so the external won't build at all. (Prefer Pd's `getbytes`/`freebytes`
over `malloc`/`free` anyway; and integer `/` and `%` avoid needing `floor` for integer division.)

## Platform file extensions

The loadable file's extension is platform- (and sometimes arch-) specific. pd-lib-builder picks it for you;
know them for manual builds and for recognizing externals:

| OS | extension(s) |
|----|--------------|
| Linux | `.pd_linux` (any arch); `.l_i386`, `.l_amd64`, `.l_arm`, `.l_arm64` |
| macOS | `.pd_darwin` (any arch); `.d_fat`, `.d_amd64`, `.d_arm64`, `.d_i386`, `.d_ppc` |
| Windows | `.dll` (any arch); `.m_i386`, `.m_amd64` |

## Single vs double precision

Pd can run with 64-bit samples. Build a matching external by defining `PD_FLOATSIZE`:

```sh
make CPPFLAGS="-DPD_FLOATSIZE=64"
```

Because `t_sample`/`t_float` follow `PD_FLOATSIZE`, code written with the `t_` types compiles for both
precisions unchanged — another reason to avoid raw `float`/`double` in signal code.

## How Pd loads libraries

Pd loads a library `my_lib` (and runs `my_lib_setup()`) in three ways:

- startup flag `-lib my_lib` — best for multi-object libraries;
- a `[declare -lib my_lib]` object in the patch;
- instantiating a `[my_lib]` object — Pd searches the paths for `my_lib.<ext>` and loads it.

On load Pd calls `my_lib_setup()`, which registers the classes. A library can't share a name with an
already-loaded class (e.g. you can't name a library `abs`). Install the built binary somewhere on Pd's
search path (e.g. `~/Documents/Pd/externals`, then add it via Preferences → Path, or use `make install`).

## Help patches

Right-clicking an object opens its help patch — by default `doc/5.reference/<classname>.pd`. Ship a
`<name>-help.pd` (a small patch demonstrating the object) alongside the binary, or call
`class_sethelpsymbol(c, gensym("other-help"))` in setup to redirect several classes to one help patch.
