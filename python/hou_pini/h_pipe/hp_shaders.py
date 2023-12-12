"""Houdini pipeline shading tools."""

import logging

import hou

from pini import qt, icons

_LOGGER = logging.getLogger(__name__)


def import_assgz_shaders(out, parent=None, force=False):
    """Import ass.gz shaders into houdini.

    Args:
        out (CPOutput): ass.az output file
        parent (QDialog): parent dialog
        force (bool): replace existing matnet without confirmation

    Returns:
        (ShopNode): material network
    """
    from htoa import material  # pylint: disable=import-error

    _ns = out.entity.name

    _LOGGER.info('IMPORT ASS GZ %s', out.path)
    _LOGGER.info(' - NS %s', _ns)

    # Obtain empty matnet
    _name = 'shaders_'+_ns
    _obj = hou.node('/obj')
    _net = _obj.node(_name)
    if _net:
        if not force:
            qt.ok_cancel(
                'Replace existing shaders?\n\n{}'.format(_net.path()),
                title='Confirm Replace', icon=icons.find('Palette'),
                parent=parent)
        _net.destroy()
        _net = None
    if not _net:
        _net = _obj.createNode('matnet', _name)
    _LOGGER.info(' - NET %s', _net)
    _net.setColor(hou.Color(1, 1, 0))
    assert not _net.children()

    # Import shaders
    _mats_root = hou.node('/mat')
    _cur_mat_names = [_mat.name() for _mat in _mats_root.children()]
    _LOGGER.info(' - CUR MATS %d %s', len(_cur_mat_names), _cur_mat_names)
    material.materialImport(node=_mats_root, filename=out.path)
    _new_mats = [
        _mat for _mat in _mats_root.children()
        if _mat.name() not in _cur_mat_names]
    _LOGGER.info(' - NEW MATS %d %s', len(_new_mats), _new_mats)
    hou.moveNodesTo(_new_mats, _net)

    # Set source attr
    _ptg = _net.parmTemplateGroup()
    _tmpl = hou.StringParmTemplate(
        "source", "Source", 1, default_value=[out.path])
    _ptg.append(_tmpl)
    _net.setParmTemplateGroup(_ptg)
    _parm = _net.parm('source')
    _parm.lock(True)

    # Mark as managed shaders ass.gz
    _ptg = _net.parmTemplateGroup()
    _tmpl = hou.ToggleParmTemplate(
        "isManagedShadersAssGz",
        "Managed shaders ass.gz import", default_value=True)
    _LOGGER.info(' - TMPL %s', _tmpl)
    _ptg.append(_tmpl)
    _net.setParmTemplateGroup(_ptg)
    _parm = _net.parm('isManagedShadersAssGz')
    _parm.lock(True)
    _parm.hide(True)

    hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor).cd('/obj')

    return _net
