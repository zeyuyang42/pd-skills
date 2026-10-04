# Building & loading externals

An external is a shared library that exports `<name>_setup()`. On Linux and macOS you **don't link against Pd**: the
API symbols (`post`, `class_new`, …) are left undefined, and Pd supplies them at load time. The only header you need is `m_pd.h`.

## Where `m_pd.h` lives

| Platform | Typical include dir |
|----------|---------------------|
| macOS (app bundle) | `/Applications/Pd-<version>.app/Contents/Resources/src` |
| Linux (package) | `/usr/include/pd` or `/usr/local/include/pd` (Debian/Ubuntu: `puredata-dev`) |
| Windows | `<Pd install dir>/src` (import lib `pd.dll` in `<Pd install dir>/bin`) |
| Source checkout | `<pure-data repo>/src` |

If you're unsure, run `find / -name m_pd.h 2>/dev/null`.

## pd-lib-builder (recommended)

[`pd-lib-builder`](https://github.com/pure-data/pd-lib-builder) is the community-standard Makefile. It detects the
platform and picks the flags and file extension for you. Vendor `Makefile.pdlibbuilder` next to your project (copy it or add it as a git submodule):

```make
lib.name = myobj                     # library name (== object name for a single-object lib)
class.sources = myobj.c              # one source per class; basename == class name
datafiles = myobj-help.pd            # extra files for `make install`
PDLIBBUILDER_DIR = ./pd-lib-builder/
include $(PDLIBBUILDER_DIR)/Makefile.pdlibbuilder
```

```sh
make                                          # build
make PDINCLUDEDIR=/path/to/pd/src             # if m_pd.h isn't found
make PDDIR=/path/to/pd                        # or: Pd root (PDINCLUDEDIR=$(PDDIR)/src, PDBINDIR=$(PDDIR)/bin)
make install PDLIBDIR=~/Documents/Pd/externals
make clean
```

**Multiple classes in one library:** list every source in `class.sources` and write a `void <lib.name>_setup(void)`
that calls each class's setup function.

## Building one file by hand

```sh
PDINC=/path/to/pd/src
cc -DPD -I"$PDINC" -fsyntax-only myobj.c                                          # quick check
cc -DPD -I"$PDINC" -bundle -undefined dynamic_lookup -o myobj.pd_darwin myobj.c   # macOS (add -arch arm64 -arch x86_64 for universal)
cc -DPD -I"$PDINC" -shared -fPIC -o myobj.pd_linux myobj.c                        # Linux
gcc -DPD -I"$PDINC" -shared -o myobj.dll myobj.c -L/path/to/pd/bin -lpd           # Windows (MinGW): links pd.dll
```

## Standard headers

`m_pd.h` does **not** include the C library. Add `<math.h>` (`sin`, `floor`, `pow`), `<string.h>` (`memset`, `memcpy`)
and `<stdlib.h>` (`rand`, `atoi`) yourself. In C99 and later, an implicit declaration is an error, so a missing header breaks the build.

## File extensions

| OS | extension(s) |
|----|--------------|
| Linux | `.pd_linux`; arch-specific `.l_amd64`, `.l_arm64`, … |
| macOS | `.pd_darwin`; arch-specific `.d_fat`, `.d_arm64`, `.d_amd64`, … |
| Windows | `.dll`; arch-specific `.m_amd64`, `.m_i386` |

## Double precision

Build for 64-bit Pd with `make CPPFLAGS="-DPD_FLOATSIZE=64"`. Code that sticks to `t_float`/`t_sample` compiles for both
precisions unchanged, which is a good reason to avoid raw `float`/`double` in signal code.

## How Pd loads a library

Pd loads `my_lib.<ext>` and calls `my_lib_setup()` in any of these cases:
- the startup flag `-lib my_lib` is given
- a patch contains `[declare -lib my_lib]`
- a patch creates `[my_lib]` and Pd finds it on the search path

Install binaries on the search path, e.g. `~/Documents/Pd/externals`, then add that folder in Preferences › Path. A library
can't take the name of an already-loaded class.

## Help patches

Right-clicking an object opens `<classname>-help.pd`. Ship one next to the binary, or call `class_sethelpsymbol(c, gensym("other"))`
to make several classes share one help patch.
