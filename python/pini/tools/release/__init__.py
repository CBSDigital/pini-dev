"""Tools for managing releasing code."""

from .check import suggest_docs, CheckFile, check_file, transfer_kwarg_docs
from .test import PRTestFile, find_tests, run_tests, find_test, to_test_sort_key

from .r_deprecate import apply_deprecation
from .r_notes import PRNotes
from .r_version import PRVersion, RELEASE_TYPES, DEV_VER, ZERO_VER
from .r_repo import PRRepo, PINI, cur_ver, add_repo

REPOS = [PINI]
