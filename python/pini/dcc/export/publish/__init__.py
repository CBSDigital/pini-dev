"""Tools for managing publish handlers.

These facilitate generation of the publish export type - eg. publishing
a rig/model/lookdev.
"""

from pini import dcc

from .ph_basic import CBasicPublish

if dcc.NAME == 'maya':
    from .ph_maya import (
        CMayaBasicPublish, CMayaLookdevPublish, CMayaModelPublish,
        PubRefsMode, get_pub_refs_mode, set_pub_refs_mode)
