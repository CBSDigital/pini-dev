"""Tools for managing cacheable entity types."""

import logging

from .ccp_utils import pipe_cache_on_obj
from ..elem import CPSequence

_LOGGER = logging.getLogger(__name__)


class CCPSequence(CPSequence):
    """Cacheable version of the sequence object."""

    @property
    def shots(self):
        """Get list of shots in this sequence.

        Returns:
            (CCPShot list): shots
        """
        return self.find_shots()

    def create(self, *args, **kwargs):
        """Create a new sequence in this job.

        Args:
            force (bool): create without confirmation dialog
        """
        super().create(*args, **kwargs)
        self.job.find_sequences(force=True)

    def find_shots(self, force=False, **kwargs):
        """Find shots within this sequence.

        Args:
            force (bool): force reread shots from disk

        Returns:
            (CCPShot list): matching shots
        """
        if force:
            self._update_shots_cache()
        return super().find_shots(**kwargs)

    def _update_shots_cache(self):
        """Rebuild cache of shots for this sequence."""
        from pini import pipe
        if pipe.MASTER == 'disk':
            self._read_shots(force=True)
        elif pipe.MASTER == 'shotgrid':
            self.job.read_shots(force=True)
        else:
            raise ValueError

    @pipe_cache_on_obj
    def _read_shots(self, class_=None, force=False):
        """Read shots in the given sequence.

        Args:
            class_ (class): override shot class
            force (bool): force reread from disk

        Returns:
            (CCPShot list): shots in sequence
        """
        from .. import cache
        _class = class_ or cache.CCPShot
        return super()._read_shots(class_=_class)
