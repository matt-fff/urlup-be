#!/bin/bash

DEPDIR=".venv"

rm -rf $DEPDIR

rye run pip install \
  -r requirements.txt \
  -t $DEPDIR/python

