"""Run in houdini before ui is built."""

import os
import time

import pini_startup


def _main():
    """Run on houdini startup."""
    os.environ['PSYHIVE_PYRC'] = time.strftime('%H%M%S')
    pini_startup.init()


if __name__ == '__main__':
    _main()
