#!/usr/bin/env python3
"""LaTeX-artifact cleaner used by the EA daily report cron.

Equivalent in intent to the inline one-liner in the cron prompt, but with
quoting made explicit so it actually runs under bash:
  - unwraps \\text{..} / \\textit{..} / \\textbf{..}
  - converts \\to and \\rightarrow / \\longrightarrow to ->
  - currency '$' is PRESERVED (the inline version's `re.sub(r'\\$','',c)` collapses
    to the zero-width end-of-string anchor after bash unescaping, i.e. a no-op,
    which is why all 30 archived reports still show $ balances).
"""
import re
import sys

def clean(path: str) -> int:
    with open(path, encoding="utf-8") as fh:
        c = fh.read()
    orig = c
    c = re.sub(r'\\(?:text|textit|textbf)\{([^}]*)\}', r'\1', c)
    c = re.sub(r'\\(?:right|longright)arrow', '\u2192', c)
    c = re.sub(r'\\to\b', '\u2192', c)
    if c != orig:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(c)
        print(f"cleaned (modified): {path}")
        return 1
    print(f"cleaned (no LaTeX artifacts, unchanged): {path}")
    return 0

if __name__ == "__main__":
    sys.exit(0 if all(clean(p) == 0 for p in sys.argv[1:]) else 0)
