#!/usr/bin/env python3
"""LaTeX artifact cleaner for EA daily reports.

Strips LaTeX-isms (\text{...}, \textit{...}, \textbf{...}, \rightarrow, \to).
Currency dollar signs are preserved: the '$' step in the original one-liner is a
no-op because '\$' unescapes to '$' inside a double-quoted shell string, and
stripping real '$' would corrupt every currency amount in the report tables.
"""
import re
import sys

PATTERNS = [
    (re.compile(r"\\(?:text|textit|textbf)\{([^}]*)\}"), r"\1"),
    (re.compile(r"\\(?:right|longright)arrow"), "\u2192"),
    (re.compile(r"\\to"), "\u2192"),
]

for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    cleaned = original
    for rx, repl in PATTERNS:
        cleaned = rx.sub(repl, cleaned)
    # currency safety: never emit a bare '$' that could open a math span
    assert cleaned.count("$") == original.count("$"), f"$ count changed in {path}"
    if cleaned != original:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cleaned)
        print(f"cleaned: {path}")
    else:
        print(f"no LaTeX artifacts: {path}")
