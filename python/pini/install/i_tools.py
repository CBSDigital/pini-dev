"""Module for setting up tool instances."""

from pini import icons, testing, qt
from pini.tools import error, helper, sanity_check
from pini.utils import wrap_fn

from .i_tool import PITool, PIDivider


def _build_refresh_tool():
    """Build refresh tool instance.

    Returns:
        (PITool): refresh tool
    """
    _cmd = '\n'.join([
        'from pini import refresh',
        'from pini.tools import usage',
        '_refresh = usage.get_tracker(name="ReloadTools")(refresh.reload_libs)',
        '_refresh()'])

    _refresh = PITool(
        name='Refresh', command=_cmd,
        icon=icons.REFRESH, label='Reload tools')

    _fs_toggle = wrap_fn(testing.enable_file_system, None)
    _nir_toggle = wrap_fn(testing.enable_nice_id_repr, None)
    for _ctx in [
            PITool(
                name='ToggleErrorCatcher',
                label='Toggle error catcher',
                icon=icons.find('Police Car Light'), command=error.toggle),
            PITool(
                name='ToggleSanityCheck',
                label='Toggle sanity check',
                icon=icons.find('Police Car Light'),
                command=testing.enable_sanity_check),
            PITool(
                name='ToggleFileSystem',
                label='Toggle file system',
                icon=icons.find('Police Car Light'), command=_fs_toggle),
            PITool(
                name='ToggleNiceIdRepr',
                label='Toggle nice id repr',
                icon=icons.find('Police Car Light'), command=_nir_toggle),
            PITool(
                name='FlushDialogStack',
                label='Flush dialog stack',
                icon=icons.CLEAN, command=qt.flush_dialog_stack),
    ]:
        _refresh.add_context(_ctx)

    return _refresh


REFRESH_TOOL = _build_refresh_tool()

VERSION_UP_TOOL = PITool(
    name='VersionUp', command='\n'.join([
        'from pini import pipe',
        'pipe.version_up()']),
    icon=icons.find('Up Arrow'), label='Version Up')

LOAD_RECENT_TOOL = PITool(
    name='LoadRecent', command='\n'.join([
        'from pini import pipe',
        'pipe.load_recent()']),
    icon=icons.LOAD, label='Load recent')

REVERT_SCENE_TOOL = PITool(
    name='Revert', label='Revert scene', icon=icons.LOAD,
    command='\n'.join([
        'from pini import dcc',
        '_file = dcc.cur_file()',
        'dcc.load(_file)']))

PINI_HELPER_BASIC_TOOL = PITool(
    name='PiniHelperBasic',
    label='Launch {} (non-docking)'.format(helper.TITLE),
    icon=helper.ICON, command='\n'.join([
        'from pini.tools import helper',
        'helper.launch(use_basic=True)']))

PINI_HELPER_NO_RESET = PITool(
    name='PiniHelperBasic',
    label='Launch {} (no cache reset)'.format(helper.TITLE),
    icon=helper.ICON, command='\n'.join([
        'from pini.tools import helper',
        'helper.launch(reset_cache=False)']))


def _build_helper_tool():
    """Build PiniHelper tool instance.

    Returns:
        (PITool): helper tool
    """
    _cmd = '\n'.join([
        'from pini.tools import helper',
        'helper.launch()'])
    _helper = PITool(
        name='PiniHelper', command=_cmd,
        icon=helper.ICON, label=helper.TITLE)

    _copy_cur_scene = PITool(
        name='CopyCurScene',
        label='Copy path to current scene',
        icon=icons.COPY, command='\n'.join([
            'from pini import dcc',
            'from pini.utils import copy_text',
            'copy_text(dcc.cur_file())']))
    _copy_sel_ref = PITool(
        name='CopySelRef',
        label='Copy path to selected reference',
        icon=icons.COPY, command='\n'.join([
            'from pini import dcc',
            'from pini.utils import copy_text',
            'copy_text(dcc.find_pipe_ref(selected=True).path)']))

    _ctx_items = [
        PINI_HELPER_BASIC_TOOL,
        PINI_HELPER_NO_RESET,
        PIDivider('HelperDiv1'),
        VERSION_UP_TOOL,
        LOAD_RECENT_TOOL,
        REVERT_SCENE_TOOL,
        PIDivider('HelperDiv2'),
        _copy_cur_scene,
        _copy_sel_ref,
    ]
    for _item in _ctx_items:
        _helper.add_context(_item)
    return _helper


PINI_HELPER_TOOL = _build_helper_tool()


def _build_sanity_check():
    """Build sanity check tool.

    Returns:
        (PITool): sanity check
    """
    _sanity = PITool(
        name='SanityCheck', command='\n'.join([
            'from pini.tools import sanity_check',
            'sanity_check.launch_ui()']),
        icon=sanity_check.ICON, label='Sanity Check')

    # Add no cache reset
    _no_reset = PITool(
        name='SanityCheckNoReset', command='\n'.join([
            'from pini.tools import sanity_check',
            'sanity_check.launch_ui(reset_pipe_cache=False)']),
        icon=sanity_check.ICON, label='Sanity Check (no cache reset)')
    _sanity.add_context(_no_reset)

    # Add paused
    _paused = PITool(
        name='SanityCheckPaused', command='\n'.join([
            'from pini.tools import sanity_check',
            'sanity_check.launch_ui(run=False)']),
        icon=sanity_check.ICON, label='Sanity Check (paused)')
    _sanity.add_context(_paused)

    _sanity.add_divider('SanityCheckDivider')

    # Add task filter modes
    for _task in ['model', 'rig', 'lookdev', 'anim', 'lighting']:
        _name = _task.capitalize()
        _sc_task = PITool(
            name='SanityCheck'+_name, command='\n'.join([
                'from pini.tools import sanity_check',
                'sanity_check.launch_ui(task="{}")'.format(_task)]),
            label='Launch {} Sanity Check'.format(_name),
            icon=sanity_check.ICON)
        _sanity.add_context(_sc_task)

    return _sanity


SANITY_CHECK = _build_sanity_check()
