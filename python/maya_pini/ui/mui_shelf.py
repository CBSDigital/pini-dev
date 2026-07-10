"""Tools for managing maya shelves.

WARNING: global qt import here was cause cyclical import as this
is used globally in pini.MayaDCC
"""

import collections
import logging
import os
import pprint

from maya import cmds, mel

from pini import icons
from pini.utils import (
    File, single, cache_result, TMP, split_base_index, HOME,
    ints_to_str, Dir, passes_filter)

from maya_pini.utils import restore

_LOGGER = logging.getLogger(__name__)

_MAYA_VER = cmds.about(majorVersion=True)
_SHELVES_DIR = HOME.to_subdir(f'Documents/maya/{_MAYA_VER}/prefs/shelves')


def add_shelf_button(
        name, command, image, parent, annotation, source_type='python',
        width=None, enable=True, flush_key='annotation'):
    """Add a shelf button.

    Args:
        name (str): uid for button (will replace existing)
        command (fn): shelf button command
        image (str): path to shelf button icon
        parent (str): parent shelf
        annotation (str): shelf button annotation
        source_type (str): source type (python/mel)
        width (int): apply width
        enable (bool): apply enabled status
        flush_key (str): key to match to replace any existing button
    """
    _LOGGER.debug('ADD SHELF BUTTON %s', name)

    # Replace existing
    _LOGGER.debug(' - CHECKING FOR EXISTING')
    _to_delete = set()
    if flush_key == 'annotation':
        _to_delete |= set(find_shelf_buttons(
            parent=parent, label=annotation))
    elif flush_key == 'command':
        _to_delete |= set(find_shelf_buttons(
            parent=parent, command=command))
    else:
        raise ValueError(flush_key)
    if cmds.shelfButton(name, query=True, exists=True):
        _to_delete.add(name)
    _LOGGER.debug(' - FOUND %d EXISTING', len(_to_delete))
    for _btn in _to_delete:
        cmds.deleteUI(_btn)

    # Build button
    _image = File(image)
    _kwargs = {}
    if width:
        _kwargs['width'] = width
    _btn = cmds.shelfButton(
        name, command=command, image=_image.path, parent=parent,
        annotation=annotation, label=annotation, sourceType=source_type,
        enable=enable, **_kwargs)

    return _btn


def cur_shelf():
    """Read currently selected shelf.

    Returns:
        (str): name of selected shelf
    """
    _shelves = cmds.layout('ShelfLayout', query=True, childArray=True)
    _idx = cmds.shelfTabLayout('ShelfLayout', query=True, selectTabIndex=True)
    return _shelves[_idx - 1]


@cache_result
def _get_separator_icon(icon='Fleur-de-lis'):
    """Build separator icon (only needs to happen once).

    Args:
        icon (str): path to icon

    Returns:
        (File): separator icon
    """
    from pini import qt

    _file = TMP.to_file(f'pini/spacer_icon_{icon}.png')
    _pix = qt.CPixmap(70, 100)
    _pix.fill('Transparent')

    _over = icons.EMOJI.find(icon, catch=True)
    if not _over:
        return None

    _pix.draw_overlay(_over, pos=_pix.center(), size=30, anchor='C')
    _pix.save_as(_file, force=True)
    return _file


def add_shelf_separator(name, parent, style='Fleur-de-lis'):
    """Add shelf separator.

    By default this is a separator with a small fleur-de-lis icon.

    Args:
        name (str): ui element name for separator (must be unique)
        parent (str): parent shelf
        style (str): icon style
    """
    if style == 'maya':
        if cmds.separator(name, exists=True):
            cmds.deleteUI(name)
        cmds.separator(name, style='shelf', parent=parent)
    elif style == 'Fleur-de-lis':
        _LOGGER.debug('ADD DIVIDER %s', name)
        _icon = _get_separator_icon()
        add_shelf_button(
            name, image=_icon, command=f'# {name}\npass',
            width=10, parent=parent, annotation='** Separator **',
            enable=False, flush_key='command')
    else:
        raise ValueError(style)


def find_shelf_button(label, parent, catch=True):
    """Find a shelf button matching the given parameters.

    Args:
        label (str): button label
        parent (str): button parent shelf
        catch (bool): no error if matching button not found

    Returns:
        (str): shelf button ui element
    """
    return single(find_shelf_buttons(label=label, parent=parent), catch=catch)


def find_shelf_buttons(parent=None, label=None, command=None):
    """Search for shelf buttons.

    Args:
        parent (str): filter list by button parent shelf name (eg. Custom)
        label (str): filter list by button label
        command (str): filter by command

    Returns:
        (str list): list of button names
    """
    _LOGGER.debug('FIND SHELF BUTTONS')
    _all_btns = sorted([
        _ctrl for _ctrl in cmds.lsUI(controls=True)
        if cmds.shelfButton(_ctrl, query=True, exists=True)])
    _LOGGER.debug(' - FOUND %d BTNS', len(_all_btns))
    _btns = []
    for _btn in _all_btns:
        _LOGGER.debug('TESTING BUTTON %s', _btn)
        if parent:
            _parent_ui = cmds.shelfButton(_btn, query=True, parent=True)
            _LOGGER.debug(' - PARENT UI %s', _parent_ui)
            _parent = _parent_ui.split('|')[-1]
            if _parent != parent:
                continue
        if label:
            _label = cmds.shelfButton(_btn, query=True, label=True)
            _LOGGER.debug(' - LABEL %s', _label)
            if _label != label:
                continue
        if command:
            _cmd = cmds.shelfButton(_btn, query=True, command=True)
            _LOGGER.debug(' - CMD %s', _cmd)
            if _cmd != command:
                continue
        _btns.append(_btn)
    return _btns


@cache_result
def _read_default_shelves():
    """Read default shelves from maya install dir.

    Returns:
        (str list): default shelf names
    """
    _loc = Dir(os.environ['MAYA_LOCATION'])
    _dir = _loc.to_subdir('scripts/shelves')
    _defs = []
    for _mel in _dir.find(
            depth=1, type_='f', extn='mel', class_=True, head='shelf_'):
        _LOGGER.debug('MEL %s', _mel)
        _shelf = _mel.base.replace('shelf_', '')
        _LOGGER.debug(' - SHELF %s', _shelf)
        _defs.append(_shelf)
    _LOGGER.debug('DEFAULT SHELVES %s', _defs)

    return _defs


def find_shelves(default=True, filter_=None):
    """Find shelves in current maya session.

    Args:
        default (bool): include default shelves
        filter_ (str): apply shelf name filter

    Returns:
        (str list): matching shelves
    """
    _shelves = []
    for _shelf in cmds.layout('ShelfLayout', query=True, childArray=True):
        if filter_ and not passes_filter(_shelf):
            continue
        if not default and _shelf in _read_default_shelves():
            continue
        _shelves.append(_shelf)

    return _shelves


@restore(shelf=True)
def fix_broken_shelves(
        filter_=None, default=False, update_opt_vars=False, force=False):
    """Fix broken shelves.

    This fixes a bug in maya where custom shelves appear with no buttons
    in them. It checks each shelf has buttons, which requries switching to
    each shelf to check as some shelves only populate when they are
    selected.

    Args:
        filter_ (str): apply shelf name filter
        default (bool): check default shelves
        update_opt_vars (bool): update option vars (doesn't seem to help bug)
        force (bool): fix shelves without confirmation
    """
    from pini import qt

    # Check shelves
    _to_rebuild = []
    for _shelf in find_shelves(default=default, filter_=filter_):

        # Test whether shelf has buttons
        _btns = find_shelf_buttons(parent=_shelf)
        _LOGGER.debug('SHELF %s %d', _shelf, len(_btns))
        if _btns:
            _LOGGER.debug(' - SHELF HAS BUTTONS')
            continue

        # Switch to shelf + check for buttons again
        select_shelf(_shelf)
        _btns = find_shelf_buttons(parent=_shelf)
        if _btns:
            _LOGGER.debug(' - SHELF HAS BUTTONS AFTER SWITCHING')
            continue
        _LOGGER.debug(' - SHELF HAS NO BUTTONS AFTER SWITCHING')

        # Check mel has buttons
        _mel = _SHELVES_DIR.to_file(f'shelf_{_shelf}.mel')
        _LOGGER.debug(' - MEL %s', _mel)
        if not _mel.exists():
            _LOGGER.debug(' - MISSING MEL')
            continue
        _n_btns = _mel.read().count('\n    shelfButton\n        ')
        _LOGGER.debug(' - N MEL BTNS %d', _n_btns)
        if not _n_btns:
            _LOGGER.debug(' - MEL HAS NO BTNS')
            continue
        _to_rebuild.append(_shelf)

    # Execute rebuild
    if _to_rebuild:
        if not force:
            _shelves_s = '\n    - '.join(_to_rebuild)
            qt.ok_cancel(
                f'Rebuild {len(_to_rebuild)} broken shelves?'
                f'\n\n    - {_shelves_s}')
        for _shelf in qt.progress_bar(_to_rebuild, 'Rebuilding {:d} shelves'):
            _rebuild_shelf(_shelf, force=True)
    else:
        _LOGGER.debug('NOTHING TO REBUILD')
        if not force:
            qt.notify('No shelves found to rebuild')

    if update_opt_vars:
        _check_shelf_opt_vars()


def _rebuild_shelf(shelf, force=False):
    """Rebuild the given shelf from its mel file.

    Args:
        shelf (str): shelf to rebuild
        force (bool): rebuild shelf without confirmation
    """
    from pini import qt

    if not force:
        qt.ok_cancel(f'Rebuild broken shelf "{shelf}"?')

    _mel = _SHELVES_DIR.to_file(f'shelf_{shelf}.mel')
    _del = _SHELVES_DIR.to_file(f'{_mel.filename}.deleted')

    _mel.bkp()
    _mel.copy_to(_del, force=True)

    # Delete shelf
    if shelf in find_shelves():
        cmds.deleteUI(shelf)

    # Rebuild
    if not _mel.exists():
        _del.move_to(_mel)
    mel.eval(f'loadNewShelf("{_mel.path}")')


def _check_shelf_opt_vars(force=False):  # pylint: disable=too-many-branches,too-many-statements
    """Check shelf option vars exist and don't overlap.

    This seems to be maya's internal system for managing shelves, via a
    collection of optionVar settings. Sometimes they seem to all get out
    of sync which could possibly cause the buttons to not appear.

    Args:
        force (bool): fix vars without confirmation
    """
    from pini import qt

    # Read optionVar data
    _opt_data = collections.defaultdict(dict)
    for _key in cmds.optionVar(category='Shelves', list=True):
        _val = cmds.optionVar(query=_key)
        _base, _idx = split_base_index(_key)
        if _base in ('shelfVersion', ) or not _idx:
            continue
        _LOGGER.info(' - VAR %s %s %s', _base, _idx, _val)
        _token = _base.replace('shelf', '')
        _opt_data[_idx][_token.lower()] = _val
    _opt_data = dict(_opt_data)
    pprint.pprint(_opt_data, width=200)

    # Sort into shelves
    _to_remove = []
    _shelves = find_shelves()
    _shelves_data = {}
    for _shelf_idx, _shelf_data in _opt_data.items():
        _name = _shelf_data.pop('name')
        if _name not in _shelves:
            _LOGGER.info('MISSING SHELF %s', _name)
        if _name in _shelves_data:
            _LOGGER.info('NAME CLASH %s %s', _name, _shelf_data)
            for _token in ['Align', 'Load', 'File', 'Name']:
                _key = f'shelf{_token}{_shelf_idx}'
                if cmds.optionVar(exists=_key):
                    _to_remove.append(_key)
            continue
            # asdasd
        _shelves_data[_name] = _shelf_data
        _shelf_data['idx'] = _shelf_idx
    pprint.pprint(_shelves_data, width=200)

    # Remove overlapping data
    if _to_remove:
        pprint.pprint(_to_remove)
        if not force:
            qt.ok_cancel(f'Remove {len(_to_remove)} bad optionVar tokens?')
        for _token in _to_remove:
            cmds.optionVar(remove=_token)
    else:
        _LOGGER.info('ALL SHELF OPTION VARS CORRECT')

    # Check for missing data
    _idxs = sorted(_opt_data.keys())
    _LOGGER.info(' - IDX KEYS %s', ints_to_str(_idxs))
    _to_add = []
    for _shelf in _shelves:
        if _shelf not in _shelves_data:
            _LOGGER.info('SHELF %s MISSING optionVar DATA', _shelf)
            _to_add.append(_shelf)
    if _to_add:
        _idx = max(_idxs) + 1
        assert _idxs[0] == 1
        assert _idxs[-1] == len(_idxs)
        _vars = []
        for _shelf in _to_add:
            for _token, _val in [
                    ('Name', _shelf),
                    ('Align', 'left'),
                    ('File', f'shelf_{_shelf}'),
                    ('Load', 1),
            ]:
                _vars.append((f'shelf{_token}{_idx}', _val))
            _idx += 1
        if not force:
            qt.ok_cancel(f'Add {len(_to_remove)} missing optionVar tokens?')
        pprint.pprint(_vars)
        for _key, _val in _vars:
            _kwargs = {'category': 'Shelves'}
            if isinstance(_val, str):
                _kwargs['stringValue'] = _key, _val
            elif isinstance(_val, int):
                _kwargs['intValue'] = _key, _val
            else:
                raise NotImplementedError(_val)
            cmds.optionVar(**_kwargs)

    else:
        _LOGGER.info('ALL SHELVES HAVE VARS')


def flush_shelf(name):
    """Remove all buttons in this given shelf.

    Args:
        name (str): shelf to flush
    """
    for _btn in find_shelf_buttons(parent=name):
        cmds.deleteUI(_btn)


def obtain_shelf(name):
    """Obtain shelf, creating if needed.

    Args:
        name (str): shelf name

    Returns:
        (str): shelf uid
    """
    _layout_name = name.replace(' ', '_')

    # Check if shelf exists
    _shelves = cmds.lsUI(type='shelfLayout') or []
    _exists = _layout_name in _shelves

    if not _shelves:
        raise RuntimeError

    if not _exists:
        _test_shelf = cmds.lsUI(type='shelfLayout')[0]
        _parent = cmds.shelfLayout(_test_shelf, query=True, parent=True)
        _layout_name = cmds.shelfLayout(name, parent=_parent)

    return _layout_name


def select_shelf(shelf):
    """Select the given shelf.

    Args:
        shelf (str): name of shelf to select
    """
    _shelves = cmds.layout('ShelfLayout', query=True, childArray=True)
    _idx = _shelves.index(shelf) + 1
    _LOGGER.debug(' - SELECT IDX %d', _idx)
    cmds.shelfTabLayout('ShelfLayout', edit=True, selectTabIndex=_idx)
