"""Tools for managing releasing code."""

from .check import suggest_docs, CheckFile
from .r_deprecate import apply_deprecation
from .r_notes import PRNotes
from .r_version import PRVersion, RELEASE_TYPES, DEV_VER, ZERO_VER
from .r_repo import PRRepo, PINI, cur_ver, add_repo
from .r_test_file import PRTestFile
from .r_tools import find_tests, run_tests, find_test

REPOS = [PINI]
