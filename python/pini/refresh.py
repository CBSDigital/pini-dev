"""Tools for managing reloading pini in the current session.

NOTE: this should be as low level as possible to allow usage in
environments where qt is not availabe (eg. C4D).
"""

import logging
import os
import sys
import time
import traceback
import types

from pini.utils import (
    apply_filter, six_reload, lprint, abs_path, check_heart)

_LOGGER = logging.getLogger(__name__)

_RELOAD_ORDER = [
    'pini.utils.u_misc',
    'pini.utils.u_yaml',
    'pini.utils.u_six',
    'pini.utils.path.up_utils',
    'pini.utils.path.up_path',
    'pini.utils.path',
    'pini.utils.cache.uc_memory',
    'pini.utils.cache',
    'pini.utils.py_file.upy_elem',
    'pini.utils.py_file',
    'pini.utils.clip.uc_clip',
    'pini.utils.clip',
    'pini.utils',

    'pini.dcc.dcc.d_base',
    'pini.dcc.dcc',
    'pini.dcc.pipe_ref',
    'pini.dcc.export_handler.eh_base',
    'pini.dcc.export_handler.publish.ph_basic',
    'pini.dcc.export_handler.publish.ph_maya.phm_base',
    'pini.dcc.export_handler.publish.ph_maya.phm_basic',
    'pini.dcc.export_handler.publish',
    'pini.dcc.export_handler.render',
    'pini.dcc.export_handler',
    'pini.dcc',

    'pini.pipe.cp_utils',
    'pini.pipe.cp_template',
    'pini.pipe.cp_settings',
    'pini.pipe.cp_job',
    'pini.pipe.cp_sequence',
    'pini.pipe.cp_entity',
    'pini.pipe.cp_asset',
    'pini.pipe.cp_shot',
    'pini.pipe.cp_work_dir',
    'pini.pipe.cp_work',
    'pini.pipe.cp_output',

    'pini.pipe.cache.ccp_utils',
    'pini.pipe.cache.ccp_job',
    'pini.pipe.cache.ccp_entity',
    'pini.pipe.cache.ccp_work_dir',
    'pini.pipe.cache.ccp_work',
    'pini.pipe.cache.ccp_output',
    'pini.pipe.cache.ccp_cache',
    'pini.pipe.cache',
    'pini.pipe',

    'pini.qt.utils',
    'pini.qt.wrapper.widgets.qw_base_widget',
    'pini.qt.wrapper.widgets.qw_list_widget_item',
    'pini.qt.wrapper.widgets.qw_pixmap_label',
    'pini.qt.wrapper.widgets.qw_list_view_widget_item',
    'pini.qt.wrapper.widgets.qw_list_view_pixmap_item',
    'pini.qt.wrapper.widgets',
    'pini.qt.wrapper',
    'pini.qt.q_ui_container',
    'pini.qt.custom.qc_mixin',
    'pini.qt.custom',

    'pini.qt.graph.c_graph_elem',
    'pini.qt.graph.elem.cg_basic_elem',
    'pini.qt.graph.elem.cg_pixmap_elem',
    'pini.qt.graph.elem.cg_move_elem',
    'pini.qt.graph.elem',
    'pini.qt.graph',

    'pini.qt.q_ui_loader',
    'pini.qt',

    'pini.farm.base',
    'pini.farm.deadline.d_utils',
    'pini.farm.deadline.d_farm',
    'pini.farm.deadline.d_job',
    'pini.farm.deadline',
    'pini.farm',

    'pini.install.i_tool',
    'pini.install.i_tools',
    'pini.install.i_installer',
    'pini.install',

    'pini.tools.pyui.cpnt',
    'pini.tools.pyui.ui.pu_base',
    'pini.tools.pyui.ui.pu_maya',
    'pini.tools.pyui.ui',
    'pini.tools.pyui',

    'pini.tools.release.r_version',
    'pini.tools.sanity_check.core.sc_fail',
    'pini.tools.sanity_check.core.sc_base',
    'pini.tools.sanity_check.core.sc_check',
    'pini.tools.sanity_check.core.sc_tools',
    'pini.tools.sanity_check.core.sc_utils_maya',
    'pini.tools.sanity_check.core',
    'pini.tools.sanity_check.checks.scc_maya',
    'pini.tools.sanity_check.checks.scc_maya_asset',
    'pini.tools.sanity_check.checks',
    'pini.tools.sanity_check.ui',

    'pini.tools.helper.ph_utils',
    'pini.tools.helper.elem.phe_output_item',
    'pini.tools.helper.elem.phe_scene_ref_item',
    'pini.tools.helper.elem',
    'pini.tools.helper.ph_base',
    'pini.tools.helper.ph_dialog',
    'pini.tools.helper.ph_nuke',

    'pini.tools',
    'pini.testing',

    'pini',

    'maya_pini.utils',
    'maya_pini.ref.r_namespace_clash_ui',
    'maya_pini.ref',
    'maya_pini.m_pipe.cache.mpc_cacheable',
    'maya_pini.m_pipe',

    'maya_pini.open_maya.pom_utils',
    'maya_pini.open_maya.pom_cmds',
    'maya_pini.open_maya.base.pom_base_node',
    'maya_pini.open_maya.base.pom_base_transform',
    'maya_pini.open_maya.base',
    'maya_pini.open_maya.wrapper.pom_node',
    'maya_pini.open_maya.wrapper',
    'maya_pini.open_maya',

    'maya_pini.m_pipe',
    'maya_pini',

    'hou_pini.utils',
    'hou_pini',
]

_RELOAD_ORDER_APPEND = os.environ.get('PINI_RELOAD_ORDER_APPEND')
if _RELOAD_ORDER_APPEND:
    _RELOAD_ORDER += _RELOAD_ORDER_APPEND.split(',')


def find_mods(base=None):
    """Find modules.

    Modules without __file__ attribute are ignored.

    Args:
        base (str): match by module base (eg. pini)

    Returns:
        (mod list): matching modules
    """
    _mods = []
    for _name, _mod in sorted(sys.modules.items()):
        if (
                not _mod or
                not hasattr(_mod, '__file__') or
                not _mod.__file__):
            continue
        if base and not _name.startswith(base):
            continue
        _mods.append(_mod)

    return _mods


def _find_pini_mods(sort=None, filter_=None, mod_names=None):
    """Find modules to reload.

    Args:
        sort (fn): module sort function
        filter_ (str): filter list by module name
        mod_names (str list): force list of module names - otherwise
            all pini modules are used

    Returns:
        (mod list): modules to reload
    """
    _sort = sort or get_mod_sort()

    # Get list of mod names to sort
    _mod_names = mod_names or apply_filter(sys.modules.keys(), 'pini')
    if filter_:
        _mod_names = apply_filter(_mod_names, filter_)
    _mod_names.sort(key=_sort)

    _mods = []
    for _mod_name in _mod_names:
        _mod = sys.modules[_mod_name]
        if (
                not _mod or
                not _mod.__file__):
            continue
        _mods.append(_mod)

    return _mods


def get_mod_sort(order=None):
    """Obtain module sort function.

    Args:
        order (str list): order list

    Returns:
        (fn): sort function
    """

    _order = order or _RELOAD_ORDER

    def _mod_sort(name):

        _name = name
        if isinstance(_name, types.ModuleType):
            _name = _name.__name__

        _LOGGER.log(9, 'SORT MOD %s', _name)

        # Apply default sort
        _val = 10.0
        if 'utils' in _name:
            _val -= 0.03
        if 'base' in _name:
            _val -= 0.02
        if 'misc' in _name:
            _val -= 0.01
        if 'tools' in _name:
            _val += 0.01
        if _name.endswith('_ui'):
            _val += 0.02
        if 'tests' in _name:
            _val += 0.03
        if 'launch' in _name:
            _val += 0.04
        _val -= _name.count('.')*0.1
        _LOGGER.log(9, ' - VAL A %f', _val)

        # Apply ordering
        _idx = 0
        _tokens = _name.split('.')
        _LOGGER.log(9, ' - TOKENS %s', _tokens)
        for _idx in range(_name.count('.')+1):
            _n_tokens = _name.count('.') + 1 - _idx
            _r_name = '.'.join(_tokens[:_n_tokens])
            _LOGGER.log(9, ' - TESTING %s %d', _r_name, _n_tokens)
            if _r_name in _order:
                _LOGGER.log(9, ' - MATCH %s %d', _r_name, _idx)
                _order_idx = _order.index(_r_name)
                break
        else:
            _order_idx = len(_order)
            _LOGGER.log(9, ' - NO MATCH %s %d', _name, _idx)
        _val += _order_idx*10
        _LOGGER.log(9, ' - VAL B %f', _val)

        return _val

    return _mod_sort


def _reload_mod(mod, sort, catch=False, verbose=0):
    """Reload the given module.

    Args:
        mod (mod): module to sort
        sort (fn): sort function (for verbose output)
        catch (bool): catch modules that fail to reload
        verbose (int): print process data
    """
    _name = mod.__name__

    # Try to reload
    _start = time.time()
    try:
        six_reload(mod)
    except ImportError as _exc:
        print("### RELOAD ERROR ###")
        print(traceback.format_exc())
        if not catch:
            from pini import qt
            qt.ok_cancel(
                'Failed to reload "{}".\n\nRemove from '
                'sys.path?'.format(_name),
                verbose=0)
            del sys.modules[_name]
        return
    _dur = time.time() - _start

    # Print status
    if len(_name) > 53:
        _name = _name[:50]+' ...'
    lprint(
        '{:<7.02f} {:<55} {:5.02f}s    {}'.format(
            sort(_name), _name, _dur, abs_path(mod.__file__)),
        verbose=verbose > 1)


def reload_libs(
        filter_=None, close_interfaces=True, mods=None, mod_names=None,
        sort=None, run_setup=False, verbose=1):
    """Reload pini modules.

    Args:
        filter_ (str): filter module list
        close_interfaces (bool): close interfaces before reload
        mods (module list): override list of modules to reload
        mod_names (str): override list of module names
        sort (fn): override module sort function
        run_setup (bool): run setup command - this reinstalls pini
        verbose (int): print process data
    """
    _LOGGER.debug('RELOAD LIBS')

    if close_interfaces:
        from pini import qt
        _LOGGER.debug(' - CLOSING INTERFACES')
        qt.close_all_interfaces()

    # Get list of modules to reload
    _sort = sort or get_mod_sort(order=_RELOAD_ORDER)
    _mods = mods or _find_pini_mods(
        sort=_sort, filter_=filter_, mod_names=mod_names)

    # Reload the modules
    _count = 0
    _start = time.time()
    for _mod in _mods:
        _reload_mod(mod=_mod, sort=_sort, verbose=verbose)
        _count += 1

    # Print summary
    if verbose:
        _LOGGER.info('Reloaded %d libs in %.01fs', _count, time.time()-_start)

    # Run setup
    if run_setup:
        from pini import install
        install.setup(build_ui=False)


def _count_root_match_fails(root, mods):
    """Check how many of the given modules fail to match the given root.

    Args:
        root (str): root directory to match
        mods (module list): modules to read file path from

    Returns:
        (int): number of modules which not inside root
    """
    _mods = mods or _find_pini_mods()
    _root = abs_path(root)
    _LOGGER.debug('CHECK ROOT %s', _root)

    _fails = []
    for _mod in _mods:
        _mod_path = abs_path(_mod.__file__)
        _failed = not _mod_path.startswith(_root)
        if _failed:
            _fails.append(_mod)
        _LOGGER.debug(' - CHECKED %d %s', _failed, _mod_path)

    return _fails


def update_libs(check_root, filter_=None, attempts=7, verbose=1):
    """Update libraries to match the given root.

    The libraries are reloaded until all of their file paths have been updated
    to match the root provided, or until the maximum number of attempts is
    reached.

    Args:
        check_root (str): required root paths
        filter_ (str): module name filter
        attempts (int): maximum number of attempts
        verbose (int): print process data
    """
    _root = abs_path(check_root)+'/'
    _LOGGER.info('UPDATE LIBS root=%s', _root)

    # Find modules to reload
    _mods = _find_pini_mods(filter_=filter_)
    _LOGGER.info(
        ' - FOUND %d MODS %s', len(_mods), _mods if verbose > 1 else '')
    assert _mods

    # Reload modules until they all fall inside root
    _dur = None
    for _attempt in range(1, attempts+1):
        check_heart()
        _start = time.time()
        _fails = _count_root_match_fails(root=_root, mods=_mods)
        if not _fails:
            _LOGGER.info(' - NO FAILS attempt=%d', _attempt)
            break
        _LOGGER.info(
            ' - RELOADING MODS attempt=%d fails=%d %s %s',
            _attempt, len(_fails),
            'dur={:.01f}s'.format(_dur) if _dur else '',
            sorted([_mod.__name__ for _mod in _fails]) if verbose > 1 else '')
        reload_libs(mods=_mods, verbose=0)
        _dur = time.time() - _start
    else:
        raise RuntimeError(_root)

    if verbose > 1:
        for _mod in _mods:
            _LOGGER.info('   - MOD %s', _mod)
    _LOGGER.info(' - UPDATE SUCCESSFUL attempts=%d root=%s', _attempt, _root)
