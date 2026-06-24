#!/usr/bin/env python3
"""
Grader for the pd-externals skill evals.

Checks each eval's assertions against a run's outputs/ directory. Structural
assertions are verified by regex over the generated source; "compiles cleanly"
is verified by actually building the .c against a real m_pd.h. Writes
grading.json (schema: expectations[{text,passed,evidence}] + summary) next to
outputs/ (i.e. in the run dir).

Usage:
  python3 grade_pd.py --eval-id N --run-dir <dir-containing-outputs> \
      [--pd-include /Applications/Pd-0.55-2.app/Contents/Resources/src]
"""
import argparse, json, re, subprocess, tempfile, os, glob
from pathlib import Path

PD_INCLUDE_DEFAULT = "/Applications/Pd-0.55-2.app/Contents/Resources/src"


def read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def strip_comments(src):
    """Remove /* */ and // comments so structural checks test code, not prose."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def find_c(outputs, prefer):
    """Pick the most relevant .c file in outputs/."""
    cs = sorted(glob.glob(os.path.join(outputs, "*.c")))
    if not cs:
        return None
    for c in cs:
        if Path(c).name == prefer:
            return c
    # fall back: prefer one whose basename starts with the object name stem
    stem = prefer.replace("~.c", "").replace(".c", "")
    for c in cs:
        if Path(c).name.startswith(stem):
            return c
    return cs[0]


def find_makefile(outputs):
    for name in ("Makefile", "makefile", "GNUmakefile"):
        p = os.path.join(outputs, name)
        if os.path.exists(p):
            return p
    return None


def first_struct_member(src):
    """Return the first member declaration inside the first typedef struct {...}."""
    m = re.search(r"typedef\s+struct\b[^{]*\{(.*?)\}", src, re.S)
    if not m:
        m = re.search(r"struct\s+\w+\s*\{(.*?)\}", src, re.S)
    if not m:
        return ""
    body = m.group(1)
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("/*", "*", "//")):
            continue
        return s
    return ""


def func_body(code, name_regex):
    """Return the {...} body of the first function whose name matches name_regex."""
    m = re.search(r"\b" + name_regex + r"\s*\([^)]*\)\s*\{", code)
    if not m:
        return ""
    i = m.end() - 1
    depth, start = 0, i
    for j in range(i, len(code)):
        if code[j] == "{":
            depth += 1
        elif code[j] == "}":
            depth -= 1
            if depth == 0:
                return code[start + 1:j]
    return code[start + 1:]


def class_new_args(code):
    """Return the argument text inside the first class_new(...) call."""
    m = re.search(r"class_new\s*\((.*?)\)\s*;", code, re.S)
    return m.group(1) if m else ""


def parse_dsp_return(code):
    """Return (dsp_add_count, perform_return_offset) or (None, None)."""
    n = r = None
    md = re.search(r"dsp_add\s*\(\s*\w+\s*,\s*(\d+)", code)
    if md:
        n = int(md.group(1))
    mr = re.search(r"return\s*\(?\s*w\s*\+\s*(\d+)", code)
    if mr:
        r = int(mr.group(1))
    return n, r


def compile_external(cfile, pd_include):
    """Build the .c into a loadable bundle. Return (ok, message)."""
    base = Path(cfile).stem
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, base + ".pd_darwin")
        cmd = ["cc", "-DPD", f"-I{pd_include}", "-Wall",
               "-bundle", "-undefined", "dynamic_lookup", "-o", out, cfile]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception as e:  # noqa
            return False, f"compiler invocation failed: {e}"
        if r.returncode == 0 and os.path.exists(out):
            warns = [l for l in r.stderr.splitlines() if "warning:" in l]
            note = f"compiled OK ({os.path.getsize(out)} bytes)"
            if warns:
                note += f"; {len(warns)} warning(s): " + warns[0][:160]
            return True, note
        err = (r.stderr or r.stdout).strip().splitlines()
        return False, "compile FAILED: " + (" / ".join(err[:4]) if err else "unknown error")


def makefile_builds(mk_text):
    if not mk_text:
        return False, "no Makefile found"
    if "Makefile.pdlibbuilder" in mk_text and ("lib.name" in mk_text or "class.sources" in mk_text):
        return True, "pd-lib-builder Makefile (lib.name/class.sources + include)"
    if re.search(r"\.pd_(darwin|linux)|\bdll\b|-bundle|-shared|dynamic_lookup", mk_text):
        return True, "manual build rule producing a platform binary"
    return False, "Makefile present but no recognizable build rule"


def grade_code_eval(eval_id, outputs, pd_include):
    """Evals 0 (randf) and 1 (mult~)."""
    prefer = "randf.c" if eval_id == 0 else "mult~.c"
    cfile = find_c(outputs, prefer)
    src = read(cfile) if cfile else ""
    code = strip_comments(src)
    mk = find_makefile(outputs)
    mk_text = read(mk) if mk else ""
    first = first_struct_member(src)
    results = []

    def add(text, passed, evidence):
        results.append({"text": text, "passed": bool(passed), "evidence": evidence})

    if not cfile:
        return None  # no source produced; caller marks all fail

    ok_compile, compile_msg = compile_external(cfile, pd_include)
    ok_mk, mk_msg = makefile_builds(mk_text)
    has_minc = bool(re.search(r'#include\s*"m_pd.h"', src))
    has_tobj_first = "t_object" in first
    has_pdnew = "pd_new" in src

    if eval_id == 0:
        add('randf.c includes "m_pd.h"', has_minc, f'include line: {has_minc}')
        add("The data-space struct has t_object (x_obj) as its first member",
            has_tobj_first, f'first member: "{first}"')
        add("The constructor calls pd_new() and returns the instance pointer",
            has_pdnew and "return" in src, f'pd_new present: {has_pdnew}')
        add('A setup function named randf_setup exists and calls class_new with gensym("randf")',
            re.search(r"\brandf_setup\b", src) and re.search(r'class_new\s*\(\s*gensym\s*\(\s*"randf"', src),
            f'randf_setup: {bool(re.search(r"randf_setup", src))}, class_new gensym: {bool(re.search(chr(34)+"randf"+chr(34), src))}')
        add("A bang handler is registered with class_addbang and outputs a float via outlet_float",
            "class_addbang" in src and "outlet_float" in src,
            f'class_addbang: {"class_addbang" in src}, outlet_float: {"outlet_float" in src}')
        add("The maximum is read from a creation argument (A_DEFFLOAT in class_new, or A_GIMME parsed with atom_getfloat)",
            "A_DEFFLOAT" in src or ("A_GIMME" in src and "atom_getfloat" in src),
            f'A_DEFFLOAT: {"A_DEFFLOAT" in src}, A_GIMME+atom_getfloat: {"A_GIMME" in src and "atom_getfloat" in src}')
        add("A second inlet updates the maximum (floatinlet_new, or inlet_new plus a registered method)",
            "floatinlet_new" in src or "inlet_new" in src,
            f'floatinlet_new: {"floatinlet_new" in src}, inlet_new: {"inlet_new" in src}')
        add("randf.c compiles cleanly against m_pd.h (produces a loadable binary with no errors)",
            ok_compile, compile_msg)
        add("A Makefile is provided that builds the external (pd-lib-builder with lib.name/class.sources, or a correct manual compile rule producing the platform extension)",
            ok_mk, mk_msg)
    else:  # eval_id == 1, mult~
        # parse dsp_add count and perform return offset (from comment-stripped code)
        n_dsp = None
        mdsp = re.search(r"dsp_add\s*\(\s*\w+\s*,\s*(\d+)", code)
        if mdsp:
            n_dsp = int(mdsp.group(1))
        r_ret = None
        mret = re.search(r"return\s*\(?\s*w\s*\+\s*(\d+)", code)
        if mret:
            r_ret = int(mret.group(1))
        ret_ok = (n_dsp is not None and r_ret is not None and r_ret == n_dsp + 1)
        sig_inlet = bool(re.search(r"inlet_new\s*\([^;]*s_signal[^;]*s_signal", code, re.S))
        sig_outlet = bool(re.search(r"outlet_new\s*\([^;]*s_signal", code))
        dsp_acant = ("A_CANT" in code) and bool(re.search(r'gensym\s*\(\s*"dsp"', code))

        add('mult~.c includes "m_pd.h"', has_minc, f'include line: {has_minc}')
        add("The data-space struct has t_object (x_obj) as its first member",
            has_tobj_first, f'first member: "{first}"')
        add("Uses CLASS_MAINSIGNALIN to make the left (first) inlet a signal inlet",
            "CLASS_MAINSIGNALIN" in src, f'CLASS_MAINSIGNALIN: {"CLASS_MAINSIGNALIN" in src}')
        add("Creates a second signal inlet with inlet_new(..., &s_signal, &s_signal) and a signal outlet with outlet_new(..., &s_signal)",
            sig_inlet and sig_outlet, f'signal inlet_new: {sig_inlet}, signal outlet_new: {sig_outlet}')
        add('Registers the dsp method with A_CANT: class_addmethod(c, ..., gensym("dsp"), A_CANT, 0)',
            bool(dsp_acant), f'A_CANT present: {"A_CANT" in src}, dsp method: {bool(re.search(chr(34)+"dsp"+chr(34), src))}')
        add("The perform routine casts its arguments starting at w[1] (not w[0])",
            "w[1]" in code and "w[0]" not in code,
            f'(comments stripped) w[1] in code: {"w[1]" in code}, w[0] in code: {"w[0]" in code}')
        add("The perform routine returns w + (n+1) consistent with the dsp_add pointer count",
            ret_ok, f'dsp_add count={n_dsp}, return w+{r_ret} (need {None if n_dsp is None else n_dsp+1})')
        add("The perform routine multiplies the two input sample vectors into the output vector",
            ("w[2]" in src and "w[3]" in src and "*" in src), 'two input casts (w[2],w[3]) and a multiply present')
        add("mult~.c compiles cleanly against m_pd.h (produces a loadable binary with no errors)",
            ok_compile, compile_msg)
        add("A Makefile is provided that builds the external", ok_mk, mk_msg)
    return results


def grade_debug_eval(outputs):
    ans = ""
    for cand in ("answer.md", "ANSWER.md", "answer.txt"):
        p = os.path.join(outputs, cand)
        if os.path.exists(p):
            ans = read(p)
            break
    if not ans:
        # any .md
        mds = glob.glob(os.path.join(outputs, "*.md"))
        if mds:
            ans = read(mds[0])
    low = ans.lower().replace(" ", "")
    results = []

    def add(text, passed, evidence):
        results.append({"text": text, "passed": bool(passed), "evidence": evidence})

    mentions_w5 = bool(re.search(r"w\s*\+\s*5", ans))
    mentions_w4 = bool(re.search(r"w\s*\+\s*4", ans))
    mentions_np1 = ("n+1" in low) or ("w+(n+1)" in low) or ("numberofpointers" in low)
    why_words = any(k in low for k in ["dspchain", "chain", "traversal", "traverse", "nextobject",
                                       "nextperform", "pastthe", "outofbounds", "invalidmemory",
                                       "corrupt", "garbage", "readspast", "wrongaddress", "offset"])
    acant = "a_cant" in low
    fixed_w5 = bool(re.search(r"return\s*\(?\s*w\s*\+\s*5", ans))

    add("Identifies the perform-routine return-value bug: it returns w+4 but must return w+5 (w + n + 1, with n=4 from dsp_add)",
        mentions_w5 and (mentions_w4 or mentions_np1),
        f'mentions w+5: {mentions_w5}, mentions w+4: {mentions_w4}, mentions n+1: {mentions_np1}')
    add("Explains WHY the wrong return crashes Pd when DSP starts (the DSP chain traversal reads past/short of the stored pointers into invalid memory)",
        why_words, f'explanatory keywords present: {why_words}')
    add("Notes that the dsp method should be registered with A_CANT rather than 0",
        acant, f'A_CANT mentioned: {acant}')
    add("Provides corrected code in which the perform routine returns (w + 5)",
        fixed_w5, f'corrected return (w + 5) present: {fixed_w5}')
    add("The diagnosis centers on the return value as the crash cause and does not invent an unrelated/incorrect root cause",
        mentions_w5, f'(heuristic) identifies return-value as the fix: {mentions_w5}')
    return results


def grade_delayline(outputs, pd_include):
    """Hard eval: signal object with a dynamically allocated buffer that must be freed."""
    cfile = find_c(outputs, "delayline~.c")
    if not cfile:
        return None
    src = read(cfile); code = strip_comments(src); first = first_struct_member(src)
    cn = class_new_args(code)
    free_m = re.search(r"\b(\w+_free)\s*\(", code)
    free_name = free_m.group(1) if free_m else None
    free_registered = bool(free_name and free_name in cn)
    fbody = func_body(code, r"\w+_free") if free_name else ""
    frees_buffer = bool(re.search(r"freebytes|free\s*\(", fbody))
    allocs = bool(re.search(r"getbytes|malloc|calloc", code))
    # sample rate may come from sys_getsr() OR the signal descriptor's s_sr field
    # (the latter is the per-signal rate, valid/idiomatic inside the dsp method)
    uses_sr = ("sys_getsr" in code) or ("s_sr" in code)
    n_dsp, r_ret = parse_dsp_return(code)
    ok_compile, cmsg = compile_external(cfile, pd_include)
    ok_mk, mkmsg = makefile_builds(read(find_makefile(outputs)) if find_makefile(outputs) else "")
    r = []
    def add(t, p, e): r.append({"text": t, "passed": bool(p), "evidence": e})
    add('delayline~.c includes "m_pd.h"', re.search(r'#include\s*"m_pd.h"', src), "")
    add("The data-space struct has t_object as its first member", "t_object" in first, f'first: "{first}"')
    add("Left inlet is a signal inlet (CLASS_MAINSIGNALIN) with a signal outlet",
        "CLASS_MAINSIGNALIN" in code and re.search(r"outlet_new\s*\([^;]*s_signal", code),
        f'CLASS_MAINSIGNALIN: {"CLASS_MAINSIGNALIN" in code}')
    add("Allocates the delay buffer dynamically and sizes it from the sample rate (sys_getsr)",
        allocs and uses_sr, f'alloc: {allocs}, sys_getsr: {uses_sr}')
    add("Registers a destructor (non-zero 3rd arg to class_new) to clean up",
        free_registered, f'free fn: {free_name}, referenced in class_new: {free_registered}')
    add("The destructor frees the allocated buffer (freebytes/free)",
        frees_buffer, f'free call in destructor body: {frees_buffer}')
    add('Registers the dsp method with A_CANT',
        "A_CANT" in code and bool(re.search(r'gensym\s*\(\s*"dsp"', code)), f'A_CANT: {"A_CANT" in code}')
    add("perform casts from w[1] and returns w+(n+1) per the dsp_add count",
        ("w[1]" in code and "w[0]" not in code and n_dsp is not None and r_ret == n_dsp + 1),
        f'w[1]: {"w[1]" in code}, dsp_add n={n_dsp}, return w+{r_ret}')
    add("delayline~.c compiles cleanly against m_pd.h", ok_compile, cmsg)
    add("A Makefile is provided that builds the external", ok_mk, mkmsg)
    return r


def grade_divmod(outputs, pd_include):
    """Hard eval: two-outlet control object that must fire right-to-left."""
    cfile = find_c(outputs, "divmod.c")
    if not cfile:
        return None
    src = read(cfile); code = strip_comments(src); first = first_struct_member(src)
    outs = re.findall(r"([A-Za-z_][\w\.\->]*)\s*=\s*outlet_new", code)
    rl_ok = False; rl_ev = "could not identify two stored outlet handles"
    if len(outs) >= 2:
        left, right = outs[0], outs[1]
        fbody = func_body(code, r"\w+_float") or func_body(code, r"\w+_list") or code
        pl = fbody.find("outlet_float(" + left) ; pl = fbody.find(left, fbody.find("outlet")) if pl < 0 else pl
        # robust: find first outlet_* call referencing each handle
        def first_emit(h):
            m = re.search(r"outlet_\w+\s*\(\s*" + re.escape(h), fbody)
            return m.start() if m else -1
        il, ir = first_emit(left), first_emit(right)
        if il >= 0 and ir >= 0:
            rl_ok = ir < il
            rl_ev = f'left handle "{left}" emitted at {il}, right handle "{right}" at {ir}; right-before-left: {rl_ok}'
        else:
            rl_ev = f'emit calls not both found (left@{il}, right@{ir})'
    ok_compile, cmsg = compile_external(cfile, pd_include)
    ok_mk, mkmsg = makefile_builds(read(find_makefile(outputs)) if find_makefile(outputs) else "")
    r = []
    def add(t, p, e): r.append({"text": t, "passed": bool(p), "evidence": e})
    add('divmod.c includes "m_pd.h"', re.search(r'#include\s*"m_pd.h"', src), "")
    add("The data-space struct has t_object as its first member", "t_object" in first, f'first: "{first}"')
    add("Creates two outlets and stores both handles in the data space",
        len(outs) >= 2, f'stored outlet handles: {outs}')
    add("A float handler computes integer quotient and remainder (uses / and %)",
        ("class_addfloat" in code) and ("/" in code) and ("%" in code),
        f'class_addfloat: {"class_addfloat" in code}, has / and %: {"/" in code and "%" in code}')
    add("Fires the RIGHT outlet before the LEFT outlet (Pd right-to-left convention)", rl_ok, rl_ev)
    add("Reads the divisor from a creation argument (A_DEFFLOAT)", "A_DEFFLOAT" in code, f'A_DEFFLOAT: {"A_DEFFLOAT" in code}')
    add("divmod.c compiles cleanly against m_pd.h", ok_compile, cmsg)
    add("A Makefile is provided that builds the external", ok_mk, mkmsg)
    return r


def grade_accum(outputs, pd_include):
    """Hard eval: list handler with atom type-checking and the modern pd_error API."""
    cfile = find_c(outputs, "accum.c")
    if not cfile:
        return None
    src = read(cfile); code = strip_comments(src); first = first_struct_member(src)
    has_list = ("class_addlist" in code) or bool(re.search(r'gensym\s*\(\s*"list"', code))
    type_check = ("a_type" in code) or ("atom_getfloatarg" in code)
    has_pderror = "pd_error(" in code
    bare_error = bool(re.search(r"(?<!pd_)\berror\s*\(", code))
    has_bang = "class_addbang" in code
    has_reset = bool(re.search(r'gensym\s*\(\s*"reset"', code))
    ok_compile, cmsg = compile_external(cfile, pd_include)
    ok_mk, mkmsg = makefile_builds(read(find_makefile(outputs)) if find_makefile(outputs) else "")
    r = []
    def add(t, p, e): r.append({"text": t, "passed": bool(p), "evidence": e})
    add('accum.c includes "m_pd.h"', re.search(r'#include\s*"m_pd.h"', src), "")
    add("The data-space struct has t_object as its first member", "t_object" in first, f'first: "{first}"')
    add("Registers a list handler (class_addlist or a list method)", has_list, f'list handler: {has_list}')
    add("Inspects each atom's type before summing (a_type check or atom_getfloatarg)",
        type_check, f'a_type: {"a_type" in code}, atom_getfloatarg: {"atom_getfloatarg" in code}')
    add("Reports non-numbers with the modern pd_error() API (not the removed error())",
        has_pderror and not bare_error, f'pd_error: {has_pderror}, bare error( used: {bare_error}')
    add("Registers a bang handler and a reset method",
        has_bang and has_reset, f'class_addbang: {has_bang}, reset method: {has_reset}')
    add("accum.c compiles cleanly against m_pd.h", ok_compile, cmsg)
    add("A Makefile is provided that builds the external", ok_mk, mkmsg)
    return r


def grade_dcblock(outputs, pd_include):
    """Trap eval: filter state must be per-instance (struct), NOT static locals in perform."""
    cfile = find_c(outputs, "dcblock~.c")
    if not cfile:
        return None
    src = read(cfile); code = strip_comments(src); first = first_struct_member(src)
    pbody = func_body(code, r"\w+_perform")
    no_static_state = "static" not in pbody          # static locals would be shared across instances = bug
    state_writeback = bool(re.search(r"x->\w+\s*=", pbody))  # persists state across blocks
    n_dsp, r_ret = parse_dsp_return(code)
    ok_compile, cmsg = compile_external(cfile, pd_include)
    ok_mk, mkmsg = makefile_builds(read(find_makefile(outputs)) if find_makefile(outputs) else "")
    r = []
    def add(t, p, e): r.append({"text": t, "passed": bool(p), "evidence": e})
    add('dcblock~.c includes "m_pd.h"', re.search(r'#include\s*"m_pd.h"', src), "")
    add("The data-space struct has t_object as its first member", "t_object" in first, f'first: "{first}"')
    add("Signal inlet (CLASS_MAINSIGNALIN) and a signal outlet",
        "CLASS_MAINSIGNALIN" in code and re.search(r"outlet_new\s*\([^;]*s_signal", code), "")
    add("Filter state (x[n-1], y[n-1]) is stored per-instance, NOT as static locals in perform",
        no_static_state and state_writeback,
        f'no static in perform: {no_static_state}, writes x->state in perform: {state_writeback}')
    add("perform persists the state across blocks (writes it back into the struct)",
        state_writeback, f'x->...= in perform: {state_writeback}')
    add("Registers the dsp method with A_CANT",
        "A_CANT" in code and bool(re.search(r'gensym\s*\(\s*"dsp"', code)), "")
    add("perform casts from w[1] and returns w+(n+1)",
        "w[1]" in code and "w[0]" not in code and n_dsp is not None and r_ret == n_dsp + 1,
        f'w[1]: {"w[1]" in code}, dsp_add n={n_dsp}, return w+{r_ret}')
    add("dcblock~.c compiles cleanly against m_pd.h", ok_compile, cmsg)
    add("A Makefile is provided that builds the external", ok_mk, mkmsg)
    return r


def grade_clip(outputs, pd_include):
    """Trap eval: runtime lo/hi must NOT use a float method on the CLASS_MAINSIGNALIN inlet."""
    cfile = find_c(outputs, "clip~.c")
    if not cfile:
        return None
    src = read(cfile); code = strip_comments(src); first = first_struct_member(src)
    mainsig = "CLASS_MAINSIGNALIN" in code
    no_float_conflict = "class_addfloat" not in code        # would clash with the signal main inlet
    runtime_update = ("floatinlet_new" in code) or ("class_addmethod" in code) or \
        bool(re.search(r'gensym\s*\(\s*"(set|lo|hi|low|high|range|clip)"', code))
    args_ok = code.count("A_DEFFLOAT") >= 2 or "A_GIMME" in code
    n_dsp, r_ret = parse_dsp_return(code)
    ok_compile, cmsg = compile_external(cfile, pd_include)
    ok_mk, mkmsg = makefile_builds(read(find_makefile(outputs)) if find_makefile(outputs) else "")
    r = []
    def add(t, p, e): r.append({"text": t, "passed": bool(p), "evidence": e})
    add('clip~.c includes "m_pd.h"', re.search(r'#include\s*"m_pd.h"', src), "")
    add("The data-space struct has t_object as its first member", "t_object" in first, f'first: "{first}"')
    add("Signal inlet (CLASS_MAINSIGNALIN) and a signal outlet",
        mainsig and re.search(r"outlet_new\s*\([^;]*s_signal", code), f'CLASS_MAINSIGNALIN: {mainsig}')
    add("Reads lo and hi from creation arguments (two A_DEFFLOAT, or A_GIMME)", args_ok,
        f'A_DEFFLOAT count: {code.count("A_DEFFLOAT")}, A_GIMME: {"A_GIMME" in code}')
    add("Runtime lo/hi update does NOT use a float method on the main signal inlet (no class_addfloat conflict)",
        no_float_conflict and runtime_update,
        f'class_addfloat present (conflict): {not no_float_conflict}, has separate inlet/message: {runtime_update}')
    add("Registers the dsp method with A_CANT",
        "A_CANT" in code and bool(re.search(r'gensym\s*\(\s*"dsp"', code)), "")
    add("perform clips each sample and returns w+(n+1) from w[1]",
        "w[1]" in code and n_dsp is not None and r_ret == n_dsp + 1,
        f'dsp_add n={n_dsp}, return w+{r_ret}')
    add("clip~.c compiles cleanly against m_pd.h", ok_compile, cmsg)
    add("A Makefile is provided that builds the external", ok_mk, mkmsg)
    return r


KINDS = {"delayline": grade_delayline, "divmod": grade_divmod, "accum": grade_accum,
         "dcblock": grade_dcblock, "clip": grade_clip}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-id", type=int, default=None)
    ap.add_argument("--kind", choices=sorted(KINDS), default=None,
                    help="hard-eval kind; overrides --eval-id routing")
    ap.add_argument("--run-dir", required=True, help="dir containing outputs/")
    ap.add_argument("--pd-include", default=PD_INCLUDE_DEFAULT)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    outputs = str(run_dir / "outputs")
    meta = {}
    for cand in (run_dir / "eval_metadata.json", run_dir.parent / "eval_metadata.json"):
        if cand.exists():
            meta = json.loads(cand.read_text())
            break

    if args.kind:
        results = KINDS[args.kind](outputs, args.pd_include)
    elif args.eval_id in (0, 1):
        results = grade_code_eval(args.eval_id, outputs, args.pd_include)
    else:
        results = grade_debug_eval(outputs)
    if results is None:
        results = [{"text": a, "passed": False, "evidence": "no source file produced in outputs/"}
                   for a in meta.get("assertions", [])]

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    grading = {
        "expectations": results,
        "summary": {"passed": passed, "failed": total - passed, "total": total,
                    "pass_rate": round(passed / total, 4) if total else 0.0},
    }
    # NOTE: intentionally do NOT embed timing here. aggregate_benchmark.py reads
    # both total_duration_seconds AND total_tokens from the sibling timing.json
    # only when grading.json has no timing block, so leaving it out populates tokens.
    out = run_dir / "grading.json"
    out.write_text(json.dumps(grading, indent=2) + "\n")
    print(f"[eval {args.eval_id}] {run_dir.parent.name}/{run_dir.name}: "
          f"{passed}/{total} passed -> {out}")


if __name__ == "__main__":
    main()
