"""Tools for managing cacheable assets."""

# pylint: disable=too-many-ancestors

import logging

from pini.utils import nice_id

from ...elem import CPAsset
from . import ccp_ety

_LOGGER = logging.getLogger(__name__)


class CCPAsset(ccp_ety.CCPEntity, CPAsset):
    """Cacheable version of the asset object."""

    __init__ = CPAsset.__init__

    def create(self, **kwargs):
        """Create this asset."""
        _LOGGER.debug('[CCPAsset] CREATED %s (ready for discard)',
                      nice_id(self))
        super().create(**kwargs)

        assert self.exists()

        # Update caches
        self.job.find_asset_types(force=True)
        self.job.read_type_assets(asset_type=self.asset_type, force=True)

        assert self.asset_type in self.job.asset_types
        assert self in self.job.assets
        _LOGGER.debug(' - CREATE COMPLETE %s', nice_id(self))
