#!/bin/sh
# KM pre-commit hook — export active branch case graph before commit (spec §2.6)
km export-case || exit 1
