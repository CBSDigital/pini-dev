"""Tools for managing the base reference class for maya pipe refs."""

import logging

from .. import pr_base

_LOGGER = logging.getLogger(__name__)


class CMayaPipeRef(pr_base.CPipeRef):
    """Base class for any pipelined maya reference."""

    top_node = None

    def _to_mtx(self):
        """Obtains top node transform matrix.

        Returns:
            (CMatrix): matrix
        """
        if self.top_node:
            return self.top_node.to_m()
        return None

    def _to_parent(self):
        """Obtain parent group.

        Returns:
            (CTransform): parent
        """
        if self.top_node:
            return self.top_node.to_parent()
        return None

    def delete(self, force=False):
        """Delete this reference.

        Args:
            force (bool): delete without confirmation
        """
        raise NotImplementedError(self)
