#!/bin/bash
# Fast LaTeX compilation script

cd "$(dirname "$0")"

# Use the first argument as the target file, or default to "resume.tex"
TARGET="${1:-resume.tex}"
BASENAME="${TARGET%.*}"
PDFNAME="${BASENAME}.pdf"

echo "Compiling $TARGET..."

# batchmode: completely silent
pdflatex -interaction=batchmode -file-line-error "$TARGET" > /dev/null 2>&1

if [ -f "$PDFNAME" ]; then
    echo "✓ Compilation successful! PDF: $PDFNAME"
else
    echo "⚠ Compilation may have issues. Check $BASENAME.log for details."
    exit 1
fi
