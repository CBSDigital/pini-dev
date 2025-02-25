"""Tools for managing cacheable shots."""

# pylint: disable=too-many-ancestors

import logging

from ..ccp_utils import pipe_cache_result
from ...elem import CPShot
from . import ccp_ety
from .. import ccp_ety_type

_LOGGER = logging.getLogger(__name__)


class CCPShot(ccp_ety.CCPEntity, CPShot):
    """Cacheable version of the shot object."""

    __init__ = CPShot.__init__

    def create(self, **kwargs):
        """Create this shot."""
        _LOGGER.debug('CREATE SHOT')
        super().create(**kwargs)

        # Update cache on parent
        _seq = self.to_sequence()
        _LOGGER.debug(' - UPDATING SEQUENCE CACHE %s', _seq)
        _shots = _seq.find_shots(force=True)
        assert self in _shots
        assert self in _seq.shots

        assert self in self.job.shots

    @pipe_cache_result
    def to_sequence(self):
        """Obtain this shot's corresponding sequence object.

        Returns:
            (CCPSequence): sequence
        """
        try:
            return self.job.find_sequence(self.sequence)
        except ValueError:
            return ccp_ety_type.CCPSequence(self.path, job=self.job)
