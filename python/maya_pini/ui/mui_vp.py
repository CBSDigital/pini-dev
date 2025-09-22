"""Viewport update tools."""

import logging

from maya import cmds

from pini.utils import to_camel, cache_result, single

_LOGGER = logging.getLogger(__name__)

_MODEL_EDITOR_ATTRS = [
    'bluePencil',
    'cameras',
    'controlVertices',
    'controllers',
    'clipGhosts',
    'cmEnabled',
    'deformers',
    'dimensions',
    'displayAppearance',
    'displayLights',
    'displayTextures',
    'dynamicConstraints',
    'dynamics',
    'fluids',
    'follicles',
    'grid',
    'hairSystems',
    'handles',
    'headsUpDisplay',
    'imagePlane',
    'ikHandles',
    'joints',
    'lights',
    'locators',
    'nCloths',
    'nParticles',
    'nRigids',
    'manipulators',
    'motionTrails',
    'nurbsCurves',
    'nurbsSurfaces',
    'particleInstancers',
    'pivots',
    'planes',
    'pluginShapes',
    'polymeshes',
    'selectionHiliteDisplay',
    'subdivSurfaces',
    'shadows',
    'strokes',
    'textures',
    'useDefaultMaterial',
    'wireframeOnShaded',
    'viewTransformName',
]


def find_model_editors():
    """Find model editors in the current scene.

    Returns:
        (str list): model editors
    """
    _editors = []
    for _panel in cmds.lsUI(panels=True):
        if not cmds.modelPanel(_panel, query=True, exists=True):
            continue
        _editor = cmds.modelPanel(_panel, query=True, modelEditor=True)
        _editors.append(_editor)
    return _editors


def get_active_model_editor(catch=True):
    """Get model editor for the active viewport.

    Args:
        catch (bool): no error if no active editor found

    Returns:
        (str): active model editor
    """
    _editors = find_model_editors()
    if len(_editors) == 1:
        return single(_editors)
    _editors = [_editor for _editor in _editors
                if cmds.modelEditor(_editor, query=True, activeView=True)]
    _LOGGER.debug(' - EDITORS %s', _editors)
    if len(_editors) == 1:
        return single(_editors)
    if catch:
        return None
    raise ValueError(
        'No active view found - try middle-mouse clicking the viewport')


def set_vp(
        display_lights=None,
        display_textures=None,
        grid=None,
        joints=None,
        locators=None,
        shadows=None,
):  # pylint: disable=unused-argument
    """Apply viewport settings.

    Args:
        display_lights (str): apply lighting in viewport
        display_textures (bool): display textures in viewport
        grid (bool): show grid in viewport
        joints (bool): show joints in viewport
        locators (bool): show locators in viewport
        shadows (bool): disaply shadows in viewport
    """

    # Convert kwargs to camel
    _kwargs = locals()
    for _o_key, _val in list(_kwargs.items()):
        _key = to_camel(_o_key)
        if _key != _o_key:
            _kwargs[_key] = _kwargs.pop(_o_key)

    _me = get_active_model_editor()
    _LOGGER.info('SET VIEWPORT %s', _me)

    for _key in list(_kwargs.keys()):
        _val = _kwargs.get(_key)
        if _val is None:
            del _kwargs[_key]
    assert _kwargs
    _LOGGER.info(' - KWARGS %s', _kwargs)

    # Check displayLights arg
    _display_lights = _kwargs.get('displayLights')
    if _display_lights:
        assert _display_lights in [
            "selected", "active", "all", "default", "none"]

    cmds.modelEditor(_me, edit=True, **_kwargs)


@cache_result
def to_model_editor_attrs():
    """Obtain list of model editor attributes.

    Some maya 2023 instances seem to report

    Returns:
        (str list): model editor attributes
    """
    _attrs = []
    _ed = get_active_model_editor()
    for _attr in _MODEL_EDITOR_ATTRS:
        try:
            cmds.modelEditor(_ed, query=True, **{_attr: True})
        except TypeError:
            _LOGGER.warning('Missing model editor attr: %s', _attr)
            continue
        _attrs.append(_attr)
    return _attrs
