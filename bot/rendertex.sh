#!/bin/bash
cd .tex && \
pdflatex -halt-on-error -interaction=errorstopmode render.tex && \
convert -density 256 render.pdf -quality 100 -colorspace RGB render.png
