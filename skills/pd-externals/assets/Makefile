# ============================================================================
# Makefile for a Pure Data external, using pd-lib-builder.
#
# Adapt the two variables below. For a signal object the source keeps its tilde,
# e.g.  class.sources = myobj~.c
#
# Build:   make
#          make PDDIR=/path/to/Pd          # if m_pd.h isn't auto-found
#   macOS app bundle ships headers inside it, e.g.:
#          make PDDIR=/Applications/Pd-0.55-2.app/Contents/Resources
# Install: make install PDLIBDIR=~/Documents/Pd/externals
# Clean:   make clean
#
# pd-lib-builder autodetects the platform and picks the right compiler flags and
# file extension (.pd_linux / .pd_darwin / .dll). See references/building.md.
# ============================================================================

# library name (== object name for a single-object library)
lib.name = myobj

# one source file per class; basename must equal the object/class name
class.sources = myobj.c

# extra files bundled by `make install` (help patch, docs, ...)
datafiles = myobj-help.pd

# Where Makefile.pdlibbuilder lives. Vendor it next to this Makefile (copy or
# git submodule from https://github.com/pure-data/pd-lib-builder), then:
PDLIBBUILDER_DIR = ./pd-lib-builder/
include $(PDLIBBUILDER_DIR)/Makefile.pdlibbuilder
