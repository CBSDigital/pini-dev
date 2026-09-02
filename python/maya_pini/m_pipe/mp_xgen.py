"""Tools for managing xgen within pini pipeline."""

import logging

from maya import cmds

from pini import qt
from pini.utils import Dir

_LOGGER = logging.getLogger(__name__)

XGEN_TYPES = (
    'xgmPalette',  # legacy XGen collection
    'xgmSplineDescription',  # interactive groom splines
)


def copy_xgen_collections_dir(work, pub, force=False):
    """Copy xgen collections dir to publish.

    Args:
        work (CPWork): source work
        pub (CPOutputFile): target publish
        force (bool): apply sync without confirmation

    Returns:
        (Dir|None): target xgen dir (if any)
    """

    import xgenm

    _LOGGER.info('COPY XGEN COLLECTIONS DIR')

    # Determine src dir
    _proj = Dir(xgenm.getProjectPath())
    _src = _proj.to_subdir('xgen/collections')
    _LOGGER.info(' - SRC %s %s', _src.nice_size(), _src)
    if not _src.exists():
        _LOGGER.info(' - MISSING XGEN SRC %s', _src)
        return None

    # Build output dir
    _trg = pub.to_dir().to_subdir(f'xgen/{work.base}')
    _LOGGER.info(' - TRG %s', _trg)

    if not force:
        qt.ok_cancel('Sync dir?')
    _src.copy_to(_trg, force=force)

    return _trg


def update_xgen_sidecar_files(pub, xgen, edit=False, force=False):
    """Update xgen sidecar files to point to publish location.

    Args:
        pub (CPOutputFile): target publish
        xgen (Dir): xgen data dir
        edit (bool): open sidecars in text editor on update (for debugging)
        force (bool): apply updates without confirmation
    """

    _LOGGER.info('UPDATE XGEN SIDECAR FILES')
    _dir = pub.to_dir()
    _xgens = _dir.find(
        depth=1, type_='f', extn='xgen', head=pub.base, class_=True)
    _xg_data = xgen.to_subdir('collection')
    # _proj = abs_path(xgenm.getProjectPath()).rstrip('/')

    for _xgen in _xgens:

        _LOGGER.info(' - XGEN SIDECAR %s', _xgen)
        if edit:
            _xgen.edit()

        _base, _col = _xgen.base.split('__')
        assert _base == pub.base
        _LOGGER.info('   - COL %s', _col)

        _to_replace = set()
        for _line in _xgen.read_lines():
            _tokens = _line.split()
            if len(_tokens) != 2:
                continue
            _key, _val = _tokens
            if _key == 'xgProjectPath':
                _LOGGER.debug('   - LINE        %s', _line)
                _cur_path = _val.rstrip('/')
                _new_path = xgen.path
                if _cur_path == _new_path:
                    continue
                _LOGGER.info('   - CUR PATH %s', _cur_path)
                _LOGGER.info('   - NEW PATH %s', _new_path)
                assert Dir(_new_path).exists()

                _new_line = _line.replace(_cur_path, _new_path)
                _LOGGER.info(' - NEW LINE %s', _new_line)
                _to_replace.add((_line, _new_line))

            elif _key == 'xgDataPath':
                _LOGGER.debug(' - LINE        %s', _line)
                if '${PROJECT}' not in _line:
                    assert Dir(_val).exists()
                    continue
                _cur_path = _val
                _new_path = _xg_data.path
                _new_line = _line.replace(_cur_path, _new_path)
                _to_replace.add((_line, _new_line))

        if _to_replace:
            _body = _xgen.read()
            for _find, _replace in _to_replace:
                _body = _body.replace(_find, _replace)
            _xgen.write(_body, diff=True, wording='Update', force=force)
        else:
            _LOGGER.info(' - NOTHING TO FIX %s', _xgen)


def xgen_in_use():
    """Test whether xgen is in use in the current scene.

    Returns:
        (bool): whether xgen in use
    """
    if not cmds.pluginInfo('xgenToolkit', query=True, loaded=True):
        return False

    for _type in XGEN_TYPES:
        if cmds.ls(type=_type):
            return True

    return False
