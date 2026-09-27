"""Statischer Prüfer gegen die Fehlerklasse „Name vor seiner Zuweisung benutzt".

Zwei reale Nutzer-Abstürze dieser Art (UnboundLocalError decryptor_list,
NameError refz_btn) hat KEIN Syntax-Check und kein String-Test gefunden -
beide traten erst zur Laufzeit auf, tief in sehr langen UI-Funktionen.

Erkannt werden drei Muster innerhalb JEDER Funktion und ein viertes
dateiuebergreifend (Muster D, siehe check_alle).

Innerhalb einer Funktion:
  A) Direkte Vorwärts-Referenz: ein lokaler Name wird auf Statement-Ebene
     gelesen, bevor er in derselben Funktion zugewiesen wird.
  B) Closure-Falle: eine verschachtelte Funktion liest einen Namen der
     äußeren Funktion, und die äußere Funktion RUFT diese verschachtelte
     Funktion auf, BEVOR der Name zugewiesen ist.

Bewusst konservativ: nur Namen, die in derselben Funktion zugewiesen werden
(keine Globals/Builtins/Argumente), und nur Aufrufe auf Statement-Ebene.
"""
import ast
import sys


def _assigned_names(fn):
    """Namen, die im Funktionskörper (ohne verschachtelte Defs) zugewiesen
    werden -> erste Zeilennummer."""
    out = {}

    def walk(node, top=True):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Lambda, ast.ClassDef, ast.ListComp,
                                  ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.setdefault(child.name, child.lineno)
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                out.setdefault(child.id, child.lineno)
            elif isinstance(child, ast.alias):
                nm = (child.asname or child.name).split(".")[0]
                out.setdefault(nm, getattr(child, "lineno", 0))
            walk(child, False)
    walk(fn)
    return out


def _nested_funcs(fn):
    return {c.name: c for c in ast.iter_child_nodes(fn)
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _names_read(node):
    """Alle gelesenen Namen (rekursiv, inkl. verschachtelter Defs)."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            out.add(n.id)
    return out


def _declared_global(fn):
    """Namen aus `global`/`nonlocal`: die gehören NICHT der Funktion, eine
    Zuweisung weiter unten ist also keine Vorwärts-Referenz (Fehlalarme an
    _skill_time_bonus_cache und ci real geprüft)."""
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
    return out


def _params(fn):
    a = fn.args
    names = {p.arg for p in list(a.args) + list(a.posonlyargs) + list(a.kwonlyargs)}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


def check_function(fn, path):
    problems = []
    assigned = _assigned_names(fn)
    params = _params(fn) | _declared_global(fn)
    nested = _nested_funcs(fn)
    # Default-Argumente einer verschachtelten Funktion werden bei der
    # DEFINITION ausgewertet - dort gilt die normale Vorwärts-Regel.
    for name, sub in nested.items():
        for d in list(sub.args.defaults) + [d for d in sub.args.kw_defaults if d]:
            for rd in _names_read(d):
                if rd in assigned and rd not in params and assigned[rd] > d.lineno:
                    problems.append(
                        f"{path}:{d.lineno}: Default-Argument von '{name}' liest "
                        f"'{rd}', zugewiesen erst Zeile {assigned[rd]}")

    # A) Direkte Vorwärts-Referenz im eigenen Ablauf (Muster decryptor_list):
    #    ein lokaler Name wird gelesen, bevor er zugewiesen ist.
    def _own_nodes(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Lambda, ast.ClassDef, ast.ListComp,
                                  ast.SetComp, ast.DictComp,
                                  ast.GeneratorExp)):
                continue
            yield child
            yield from _own_nodes(child)

    for nd in _own_nodes(fn):
        if not (isinstance(nd, ast.Name) and isinstance(nd.ctx, ast.Load)):
            continue
        nm = nd.id
        if nm in params or nm not in assigned:
            continue
        if assigned[nm] > nd.lineno:
            problems.append(
                f"{path}:{nd.lineno}: '{nm}' wird gelesen, aber erst Zeile "
                f"{assigned[nm]} zugewiesen (Vorwärts-Referenz)")

    # Aufrufe verschachtelter Funktionen im EIGENEN Ablauf der äußeren
    # Funktion. Bewusst NICHT durch verschachtelte Defs hindurch: ein Aufruf
    # in einem Callback läuft asynchron SPÄTER, da ist die Zuweisung längst
    # passiert (das wäre ein Fehlalarm - real geprüft an _refill_schedule).
    def _own_statements(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Lambda, ast.ClassDef, ast.ListComp,
                                  ast.SetComp, ast.DictComp,
                                  ast.GeneratorExp)):
                continue
            yield child
            yield from _own_statements(child)

    for stmt in _own_statements(fn):
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        f = stmt.value.func
        if not isinstance(f, ast.Name) or f.id not in nested:
            continue
        sub = nested[f.id]
        call_line = stmt.lineno
        if sub.lineno > call_line:
            continue                      # Aufruf vor der Definition: anderer Fall
        sub_params = _params(sub)
        sub_local = _assigned_names(sub)
        for rd in _names_read(sub):
            if rd in sub_params or rd in sub_local:
                continue                  # eigener Parameter/lokal -> harmlos
            if rd in assigned and rd not in params and assigned[rd] > call_line:
                problems.append(
                    f"{path}:{call_line}: Aufruf von '{f.id}()' liest '{rd}' "
                    f"aus der äußeren Funktion, dort erst Zeile {assigned[rd]} "
                    f"zugewiesen")

    # D) CLOSURE-SHADOWING (Nutzer-Absturz "cannot access local variable
    #    'sell'"): eine verschachtelte Funktion LIEST einen Namen aus der
    #    äußeren Funktion und WEIST ihm später auch zu. Durch die Zuweisung
    #    wird der Name für die GESAMTE innere Funktion lokal - der frühere
    #    Lesezugriff knallt zur Laufzeit als UnboundLocalError.
    #    Reine Syntax-Checks sehen das nicht; Regel A greift nicht, weil der
    #    Name in der ÄUSSEREN Funktion sauber vorher zugewiesen ist.
    for name, sub in nested.items():
        if any(isinstance(n, ast.Global) or isinstance(n, ast.Nonlocal)
               for n in ast.walk(sub)):
            continue                      # explizit deklariert -> Absicht
        sub_assigned = _assigned_names(sub)
        sub_params = _params(sub)
        for nm, aline in sub_assigned.items():
            if nm in sub_params or nm not in assigned:
                continue                  # kein Name aus der äußeren Funktion
            # NUR den eigenen Namensraum ansehen: Comprehensions, Lambdas und
            # verschachtelte Funktionen haben in Python 3 EIGENE Scopes - ein
            # gleichnamiger Name dort ist ein anderer Name. Ohne diese
            # Einschraenkung meldet die Regel z.B.
            # `[(bp_id, pid) for bp_id, pid in ...]` faelschlich (bemerkt beim
            # ersten Lauf ueber die Codebasis).
            first_read = None
            _stack = [sub]
            while _stack:
                _n = _stack.pop()
                for _c in ast.iter_child_nodes(_n):
                    if isinstance(_c, (ast.FunctionDef, ast.AsyncFunctionDef,
                                       ast.Lambda, ast.ClassDef, ast.ListComp,
                                       ast.SetComp, ast.DictComp,
                                       ast.GeneratorExp)):
                        continue
                    if (isinstance(_c, ast.Name)
                            and isinstance(_c.ctx, ast.Load) and _c.id == nm):
                        if first_read is None or _c.lineno < first_read:
                            first_read = _c.lineno
                    _stack.append(_c)
            if first_read is not None and first_read < aline:
                problems.append(
                    f"{path}:{first_read}: '{name}()' liest '{nm}' aus der "
                    f"äußeren Funktion, weist es aber Zeile {aline} auch zu "
                    f"-> UnboundLocalError. Anderen Namen verwenden.")

    # C) SELBSTBEZUG IN DER ERSTEN ZUWEISUNG:  x = f(x)  bzw.  x += 1,
    #    wenn DIESE Zeile die erste Zuweisung von x in dieser Funktion ist.
    #    Dann ist x hier lokal, aber noch unbelegt - und zwar in der ganzen
    #    Funktion, auch weiter oben.
    #
    #    WARUM ES DIESE PRUEFUNG GIBT (Nutzer-Befund 20.09.2026): im
    #    Bauplan-Job stand `opts = self._multi_opts_je_ende(opts, recipes)`.
    #    `opts` gehoerte der aeusseren Funktion; durch diese eine Zeile war
    #    es in job() lokal und damit ueberall unbelegt. Im Programm sah das
    #    so aus: "Open build plan" oeffnete einfach kein Fenster, in der
    #    Statuszeile stand die Meldung. Muster B findet das NICHT (es sucht
    #    Lesen VOR der Zuweisungszeile), Muster A auch nicht (gelesen und
    #    zugewiesen in DERSELBEN Zeile).
    def _liest_ohne_comprehension(node):
        """Gelesene Namen - ohne die eigenen Scopes von Comprehensions und
        Lambdas (deren Laufvariablen gehoeren nicht hierher)."""
        out, stapel = set(), [node]
        while stapel:
            nd = stapel.pop()
            for ch in ast.iter_child_nodes(nd):
                if isinstance(ch, (ast.Lambda, ast.ListComp, ast.SetComp,
                                   ast.DictComp, ast.GeneratorExp)):
                    continue
                if isinstance(ch, ast.Name) and isinstance(ch.ctx, ast.Load):
                    out.add(ch.id)
                stapel.append(ch)
        return out

    for stmt in _own_statements(fn):
        if isinstance(stmt, ast.Assign):
            ziele = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            gelesen = _liest_ohne_comprehension(stmt.value)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            ziele = [stmt.target.id]
            gelesen = {stmt.target.id}
        else:
            continue
        for nm in ziele:
            if nm in params or nm not in gelesen:
                continue
            if assigned.get(nm) == stmt.lineno:      # ERSTE Zuweisung hier
                problems.append(
                    f"{path}:{stmt.lineno}: '{nm}' wird in seiner eigenen "
                    f"ersten Zuweisung gelesen -> in dieser Funktion lokal "
                    f"und unbelegt (UnboundLocalError). Anderen Namen nehmen "
                    f"oder das Objekt an Ort und Stelle aendern.")
    return problems


def check_file(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            problems += check_function(node, path)
    return problems


# ----------------------------------------------------------------- Muster D
# QT REICHT SEIN SIGNAL-ARGUMENT AN JEDEN SLOT DURCH, DER EINS ANNEHMEN KANN.
#
# WARUM ES DIESE PRUEFUNG GIBT (Nutzer-Befund 20.09.2026: "klicke ich jetzt
# auf multibuildplan passiert gar nichts"): der Rail-Knopf hing mit
# `b.clicked.connect(self._open_multi_bauplan_dialog)` an einer Methode, die
# gerade den Parameter `bearbeiten=None` bekommen hatte. `clicked` traegt ein
# `checked`-Bool - Qt uebergab es, `False is not None` fuehrte in den
# Bearbeiten-Zweig, der nach einem Plan mit der id `False` suchte, keinen fand
# und still zurueckkehrte. Kein Absturz, keine Meldung, nichts im Log.
#
# Harmlos ist derselbe Weitergabe-Stil, solange die Vorgabe `False` oder `0`
# ist: genau das schickt Qt ohnehin (`checked`, Index). Gemeldet wird also nur
# die gefaehrliche Form - erster Parameter nach `self` mit einer Vorgabe, die
# WEDER False NOCH 0 ist. Abhilfe ist immer dieselbe: ueber ein Lambda
# verbinden, das nichts annimmt.
#
# Dateiuebergreifend, weil die Methode fast nie in der Datei steht, in der der
# Knopf gebaut wird (Mixins).
def _erster_default(fn):
    """Vorgabewert des ERSTEN Parameters nach `self` - oder _KEIN."""
    a = fn.args
    pos = [x.arg for x in a.args]
    if not (pos and pos[0] == "self" and len(pos) > 1 and a.defaults):
        return _KEIN
    if len(pos) - len(a.defaults) != 1:      # der erste hat keine Vorgabe
        return _KEIN
    try:
        return ast.literal_eval(a.defaults[0])
    except Exception:
        return _UNKLAR


class _KEIN:
    pass


class _UNKLAR:
    pass


def check_alle(pfade):
    """Muster D ueber ALLE uebergebenen Dateien."""
    defs = {}
    for p in pfade:
        try:
            tree = ast.parse(open(p, encoding="utf-8").read(), filename=p)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(node.name, []).append(_erster_default(node))
    # Nur wenn ALLE gleichnamigen Definitionen gefaehrlich sind - sonst weiss
    # der Pruefer nicht, welche gemeint ist, und raet lieber nicht.
    def _gefaehrlich(vals):
        if not vals:
            return False
        for v in vals:
            if v is _KEIN or v is _UNKLAR:
                return False
            if v is False or (isinstance(v, int) and not isinstance(v, bool)
                              and v == 0):
                return False
        return True

    heikel = {nm for nm, vals in defs.items() if _gefaehrlich(vals)}
    problems = []
    for p in pfade:
        try:
            src = open(p, encoding="utf-8").read()
            tree = ast.parse(src, filename=p)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            args = list(node.args) + [k.value for k in node.keywords]
            for a in args:
                if not (isinstance(a, ast.Attribute)
                        and isinstance(a.value, ast.Name)
                        and a.value.id == "self" and a.attr in heikel):
                    continue
                problems.append(
                    f"{p}:{node.lineno}: 'self.{a.attr}' wird als Rueckruf "
                    f"weitergereicht, hat aber einen ersten Parameter mit "
                    f"einer Vorgabe ungleich False/0. Ein Qt-Signal (etwa "
                    f"`clicked`) uebergibt sein Argument JEDEM Slot, der eins "
                    f"annehmen kann - der Wert landet dann dort. Ueber ein "
                    f"Lambda verbinden, das nichts annimmt.")
    return problems


if __name__ == "__main__":
    allp = []
    for p in sys.argv[1:]:
        allp += check_file(p)
    allp += check_alle(sys.argv[1:])
    for p in allp:
        print("  " + p)
    print(f"{len(allp)} Befund(e)")
    sys.exit(1 if allp else 0)
