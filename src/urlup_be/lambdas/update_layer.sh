#!/bin/bash

DEPDIR=".venv"

rm -rf $DEPDIR

pip install \
	-r requirements.txt \
	-t $DEPDIR/python
