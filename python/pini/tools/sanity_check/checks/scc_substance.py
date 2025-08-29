"""Sanity checks for substance."""

from substance_pini.utils import project_uses_udims

from .. import core


class CheckProjectUsesUdims(core.SCCheck):
    """Check current project uses udims."""

    def run(self):
        """Run this check."""
        if not project_uses_udims():
            self.add_fail('Current project does not use udims')
