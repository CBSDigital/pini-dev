"""Tools for managing the dcc object.

This managing interactions with the current dcc, providing a unified
api across all dccs.
"""

import logging
import os

_LOGGER = logging.getLogger(__name__)

DCC = None
DCCS = [
    'maya', 'nuke', 'hou', 'c4d', 'flame', 'blender', 'unreal', 'terragen',
    'substance']

_LOGGER.debug('IMPORT DCC')

if not DCC and os.environ.get('PINI_DCC') == 'terragen':
    from .d_terragen import TerragenDCC
    DCC = TerragenDCC()

if not DCC:
    try:
        from .d_maya import MayaDCC
        DCC = MayaDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - MAYA REJECTED %s', _exc)

if not DCC:
    try:
        from .d_nuke import NukeDCC
        DCC = NukeDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - NUKE REJECTED %s', _exc)

if not DCC:
    try:
        from .d_hou import HouDCC
        DCC = HouDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - HOU REJECTED %s', _exc)

if not DCC:
    try:
        from .d_c4d import C4dDCC
        DCC = C4dDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - C4D REJECTED %s', _exc)

if not DCC:
    try:
        from .d_flame import FlameDCC
        DCC = FlameDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - FLAME REJECTED %s', _exc)

if not DCC:
    try:
        from .d_blender import BlenderDCC
        DCC = BlenderDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - BLENDER REJECTED %s', _exc)

if not DCC:
    try:
        from .d_unreal import UnrealDCC
        DCC = UnrealDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - UNREAL REJECTED %s', _exc)

if not DCC:
    try:
        from .d_substance import SubstanceDCC
        DCC = SubstanceDCC()
    except ImportError as _exc:
        _LOGGER.debug(' - SUBSTANCE REJECTED %s', _exc)

if not DCC:
    from . import d_base
    DCC = d_base.BaseDCC()
    _LOGGER.debug(' - ACCEPTED NO DCC')

if DCC and DCC.NAME:
    assert DCC.NAME in DCCS
