"""Tools for managing maya shelves.

WARNING: global qt import here was cause cyclical import as this
is used globally in pini.MayaDCC
"""

import logging

from maya import cmds

from pini import icons
from pini.utils import File, single, cache_result, TMP

_LOGGER = logging.getLogger(__name__)


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


@cache_result
def _get_separator_icon(icon='Fleur-de-lis'):
    """Build separator icon (only needs to happen once).

    Args:
        icon (str): path to icon

    Returns:
        (File): separator icon
    """
    from pini import qt

    _file = TMP.to_file('pini/spacer_icon_{}.png'.format(icon))
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
            name, image=_icon, command='# {}\npass'.format(name),
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
    _btns = []
    for _btn in cmds.lsUI(controls=True):
        _LOGGER.debug('TESTING BUTTON %s', _btn)
        if not cmds.shelfButton(_btn, query=True, exists=True):
            continue
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
