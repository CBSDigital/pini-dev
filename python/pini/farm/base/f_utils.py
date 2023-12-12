"""General farm utilities."""

import logging

_LOGGER = logging.getLogger(__name__)


def set_farm(farm_):
    """Set the current default farm.

    This promotes all the given farm's attributes and methods to be
    available at pini.farm module level.

    Args:
        farm_ (CFarm): farm to apply
    """
    _LOGGER.info('SET CURRENT FARM %s', farm_)
    from pini import farm
    for _name in dir(farm_):
        if _name.startswith('__'):
            continue
        _attr = getattr(farm_, _name)
        setattr(farm, _name, _attr)
