"""Tools for managing maya rig publish handler."""

import logging

from pini import icons
from pini.utils import plural

from maya_pini import m_pipe

from . import phm_scene

_LOGGER = logging.getLogger(__name__)


class CMayaRigPublish(phm_scene.CMayaScenePublish):
    """Manages maya rig publish."""

    NAME = 'Rig Publish'
    ACTION = 'RigPublish'

    ICON = icons.find('Bone')
    COL = 'Indian Red'

    LABEL = '\n'.join([
        'Copies this scene to the publish directory - this is generally '
        'used to pass a rig asset down the pipeline for use in shots.',
        '',
        'Here are some tips:',
        '',
        ' - The top node should be RIG',
        ' - All the geometry should be added to a set named cache_SET',
        f' - Use {phm_scene.JUNK_GRPS_S} group{plural(m_pipe.JUNK_GRPS)} for '
        'nodes that should not get published',
        ' - For referenced geo, use the import references option',
        '',
        'You can use the sanity check tool to check your scene.',
    ])

    add_abc_export = True
    priority = 60
