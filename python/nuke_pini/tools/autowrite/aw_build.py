"""Tools for building autowrite 2.0 nodes."""

import logging

import nuke

from pini import pipe
from pini.tools import usage, error, helper
from pini.utils import single
from nuke_pini.utils import set_node_col

from . import aw_callbacks, aw_node
from .aw_utils import (
    COL_FMT, DEFAULT_COL, INTERNAL_COL, FILE_COL, ERROR_COL)

_LOGGER = logging.getLogger(__name__)


def _add_divider(node):
    """Add divider knob.

    Args:
        node (Node): node to build on
    """
    _div = nuke.Text_Knob('', '')
    node.addKnob(_div)


def _build_header(node):
    """Build header section of node.

    Args:
        node (Node): node to build on
    """

    # Build update
    _cmd = '\n'.join([
        'from pini.tools import error',
        'from nuke_pini.tools import autowrite',
        'autowrite.flush_callbacks()',
        '_node = autowrite.CAutowrite2(nuke.thisNode())',
        '_func = error.catch(_node.update)',
        '_func()',
        'autowrite.install_callbacks()',
    ])
    _update = nuke.PyScript_Knob('update', 'Update', _cmd)
    node.addKnob(_update)

    # Build reset
    _cmd = '\n'.join([
        'from pini.tools import error',
        f'import {aw_node.__name__} as _mod',
        '_node = _mod.CAutowrite2(nuke.thisNode())',
        '_func = error.catch(_node.reset)',
        '_func()'])
    _update = nuke.PyScript_Knob('reset', 'Reset', _cmd)
    node.addKnob(_update)

    # Build show internals
    _internals = nuke.Boolean_Knob('show_internals', 'show internals')
    _internals.clearFlag(nuke.STARTLINE)
    node.addKnob(_internals)

    # Mark as autowrite 2
    _label = COL_FMT.format(
        col='yellow', text='&nbsp;&nbsp;is autowrite 2.0')
    _is_autowrite = nuke.Boolean_Knob(
        'is_pini_autowrite_2', _label, True)
    _is_autowrite.setVisible(False)
    _is_autowrite.setKeyAt(0)  # doesn't hold val
    _is_autowrite.setFlag(nuke.STARTLINE)
    node.addKnob(_is_autowrite)

    _add_divider(node)

    _tmpl = nuke.Enumeration_Knob('tmpl', 'template', ['render', 'plate'])
    node.addKnob(_tmpl)


def _build_pipeline(node):
    """Build pipeline section.

    Args:
        node (Node): node to build on
    """
    _add_divider(node)

    # Build pipeline section
    for _label, _name, _allow_edit in [
            ('entity type', 'ety_type', False),
            ('entity', 'ety', False),
            ('task', 'task', False),
            ('tag', 'tag', False),
            ('version', 'ver', False),
    ]:
        _opts = ['Linked', 'Select']
        if _allow_edit:
            _opts += ['Manual']
        _label = COL_FMT.format(col=DEFAULT_COL, text=_label)
        _mode = nuke.Enumeration_Knob(_name + '_mode', _label, _opts)
        node.addKnob(_mode)

        _list = nuke.Enumeration_Knob(_name, ' ', [])
        _list.clearFlag(nuke.STARTLINE)
        _list.setEnabled(False)
        node.addKnob(_list)

    _work = nuke.File_Knob('work', COL_FMT.format(
        col=INTERNAL_COL, text='work'))
    _work.setFlag(nuke.READ_ONLY)
    node.addKnob(_work)


def _build_output_name(node):
    """Build output name section.

    Args:
        node (Node): node to build on
    """
    _add_divider(node)

    # Add desc line
    _modes = ["From node", 'Manual']
    _name_mode = nuke.Enumeration_Knob(
        'desc_mode', 'description', _modes)
    node.addKnob(_name_mode)
    _desc_text = nuke.String_Knob('desc_text', '', 'render')
    _desc_text.clearFlag(nuke.STARTLINE)
    _desc_text.setEnabled(False)
    node.addKnob(_desc_text)

    # Add res line
    _res = nuke.Enumeration_Knob(
        'res_mode', 'res', ['Auto', 'Manual', 'Disable'])
    _res.setValue('Disable')
    node.addKnob(_res)
    _res_text = nuke.String_Knob('res_text', '', 'unset')
    _res_text.clearFlag(nuke.STARTLINE)
    node.addKnob(_res_text)

    # Add grade line
    _grade = nuke.Enumeration_Knob(
        'grade', 'grade', ['RAW', 'GRADE', 'TECH', 'Disable'])
    node.addKnob(_grade)

    # Add layer line
    _layers = [f'L{_idx:02d}' for _idx in range(1, 11)] + ['Disable']
    _layer = nuke.Enumeration_Knob('aw_layer', 'layer', _layers)
    node.addKnob(_layer)

    # Add denoise line
    _dn = nuke.Enumeration_Knob(
        'denoise', 'denoise', ['N', 'DN', 'Disable'])
    node.addKnob(_dn)

    # Add denoise line
    _tw = nuke.Enumeration_Knob(
        'timewarp', 'timewarp', ['Disable', 'TW', 'NTW'])
    _tw.setValue('Disable')
    node.addKnob(_tw)

    # Add output line
    _label = COL_FMT.format(col=INTERNAL_COL, text='output')
    _name = nuke.String_Knob('output_name', _label, '')
    node.addKnob(_name)


def _build_footer(node):
    """Build footer section.

    Args:
        node (Node): node to build on
    """
    _add_divider(node)

    # Add error text
    _text = "you shouldn't see this"
    _label = COL_FMT.format(col=ERROR_COL, text=_text)
    _err = nuke.Text_Knob('error', ' ', _label)
    node.addKnob(_err)

    # Add file
    _file = nuke.File_Knob('aw_file', '')
    node.addKnob(_file)
    for _name in ['file', 'aw_file']:
        _label = COL_FMT.format(col=FILE_COL, text='file')
        node[_name].setLabel(_label)


def _check_compatibility():
    """Check current job is compatible with Autowrite2."""
    _job = pipe.cur_job()
    if not _job:
        raise error.HandledError(
            f'No current job found.\n\nPlease save your scene '
            f'with {helper.TITLE} to use this node.')
    if not pipe.is_valid_token(
            value='blah_blah', token='output_name', job=_job):
        raise error.HandledError(
            f'Current job {_job.name} is not compatible with Autowrite2 as '
            f'the structure does not allow underscores in output names.\n\n'
            f'Please use the legacy Autowrite node.')


@error.catch
@usage.get_tracker('Autowrite2')
def build(name='main', show_internals=False):
    """Build autowrite 2.0 node.

    Args:
        name (str): node name
        show_internals (bool): show hidden internal knobs

    Returns:
        (CAutowrite2): autowrite
    """
    _LOGGER.info('BUILD AUTOWRITE 2')
    _check_compatibility()
    _task = pipe.cur_task()
    _fmt = 'png' if _task == 'lsc' else 'exr'
    _colspace = 'rec709' if _task == 'lsc' else None

    aw_callbacks.flush_callbacks()

    _pos = None
    _sel = single(nuke.selectedNodes(), catch=True)
    if _sel:
        _pos = _sel.xpos(), _sel.ypos() + 100

    # Create node
    _node = nuke.createNode('Write')
    _node.setName(name)
    set_node_col(_node, 'DodgerBlue')
    _node['file_type'].setValue(_fmt)
    if _colspace:
        _node['colorspace'].setValue(_colspace)
    _node['label'].setValue('[AUTOWRITE]')
    if _pos:
        _node.setXYpos(*_pos)

    # Build knobs
    _node.addKnob(nuke.Tab_Knob("Pipeline"))
    _build_header(_node)
    _build_pipeline(_node)
    _build_output_name(_node)
    _build_footer(_node)

    # _build_render(_node)
    if show_internals:
        _node['show_internals'].setValue(True)

    # Update
    _node = aw_node.CAutowrite(_node)
    _node.update()
    _LOGGER.debug(' - UPDATED NODE')
    _node['file'].setFlag(nuke.READ_ONLY)  # Switch back to Write tab

    aw_callbacks.install_callbacks()

    return _node
