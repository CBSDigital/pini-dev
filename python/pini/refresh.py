"""Tools for managing reloading pini in the current session.

NOTE: this should be as low level as possible to allow usage in
environments where qt is not availabe (eg. C4D).
"""

import importlib
import logging
import os
import sys
import time
import traceback
import types

from pini.utils import apply_filter, lprint, abs_path, check_heart

_LOGGER = logging.getLogger(__name__)

RELOAD_ORDER = [
    'pini.utils.u_session',
    'pini.utils.u_text',
    'pini.utils.u_misc',
    'pini.utils.u_yaml',
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
    'pini.dcc.pipe_ref.pr_base',
    'pini.dcc.pipe_ref',
    'pini.dcc.export.eh_utils',
    'pini.dcc.export.eh_ui',
    'pini.dcc.export.eh_base',
    'pini.dcc.export.eh_publish.ph_basic',
    'pini.dcc.export.eh_publish.ph_maya.phm_base',
    'pini.dcc.export.eh_publish.ph_maya.phm_basic',
    'pini.dcc.export.eh_publish',
    'pini.dcc.export.eh_blast',
    'pini.dcc.export.eh_cache',
    'pini.dcc.export.eh_render.rh_pass',
    'pini.dcc.export.eh_render.rh_base',
    'pini.dcc.export.eh_render.rh_maya.rhm_layer',
    'pini.dcc.export.eh_render.rh_maya',
    'pini.dcc.export.eh_render.rh_tools',
    'pini.dcc.export.eh_render',
    'pini.dcc',

    'pini.pipe.cp_utils',
    'pini.pipe.cp_template',
    'pini.pipe.elem.cp_settings_elem',
    'pini.pipe.elem.job',
    'pini.pipe.elem.entity_type',
    'pini.pipe.elem.entity.cp_ety_base',
    'pini.pipe.elem.entity.cp_ety_disk',
    'pini.pipe.elem.entity.cp_ety_sg',
    'pini.pipe.elem.entity',
    'pini.pipe.elem.asset',
    'pini.pipe.elem.shot',
    'pini.pipe.elem.work_dir',
    'pini.pipe.elem.work',
    'pini.pipe.elem.output',
    'pini.pipe.elem.output.ccp_out_base',
    'pini.pipe.elem.output.ccp_out_file',
    'pini.pipe.elem.output.ccp_out_video',
    'pini.pipe.elem',

    'pini.pipe.cache.ccp_utils',
    'pini.pipe.cache.job',
    'pini.pipe.cache.ccp_ety_type',
    'pini.pipe.cache.entity.ccp_ety_base',
    'pini.pipe.cache.entity.ccp_ety_disk',
    'pini.pipe.cache.entity.ccp_ety_sg',
    'pini.pipe.cache.entity.ccp_ety',
    'pini.pipe.cache.entity',
    'pini.pipe.cache.output',
    'pini.pipe.cache.work_dir',
    'pini.pipe.cache.ccp_work',
    'pini.pipe.cache.root',
    'pini.pipe.cache',

    'pini.pipe.shotgrid.sg_handler',
    'pini.pipe.shotgrid.cache.sgc_elem_reader',
    'pini.pipe.shotgrid.cache.sgc_elem',
    'pini.pipe.shotgrid.cache.sgc_elems',
    'pini.pipe.shotgrid.cache.sgc_ety',
    'pini.pipe.shotgrid',

    'pini.pipe',

    'pini.qt.q_utils',
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
    'pini.farm.deadline.submit.ds_utils',
    'pini.farm.deadline.submit.ds_job',
    'pini.farm.deadline.submit.ds_maya_job',
    'pini.farm.deadline.submit',
    'pini.farm.deadline.d_farm_job',
    'pini.farm.deadline.d_farm',
    'pini.farm.deadline',
    'pini.farm',

    'pini.install.i_tool',
    'pini.install.i_tools',
    'pini.install.i_installer',
    'pini.install',

    'pini.tools.error.e_tools',
    'pini.tools.error',

    'pini.tools.pyui.cpnt',
    'pini.tools.pyui.ui.pu_base',
    'pini.tools.pyui.ui.pu_maya',
    'pini.tools.pyui.ui',
    'pini.tools.pyui',

    'pini.tools.release.check',
    'pini.tools.release.test',
    'pini.tools.release.r_version',
    'pini.tools.release',

    'pini.tools.sanity_check.core.sc_fail',
    'pini.tools.sanity_check.core.sc_check',
    'pini.tools.sanity_check.core.sc_check_maya',
    'pini.tools.sanity_check.core.sc_checks',
    'pini.tools.sanity_check.core',
    'pini.tools.sanity_check.utils',
    'pini.tools.sanity_check.checks.scc_maya',
    'pini.tools.sanity_check.checks.scc_maya_asset',
    'pini.tools.sanity_check.checks',
    'pini.tools.sanity_check.ui',

    'pini.tools.helper.ph_utils',
    'pini.tools.helper.ui.phu_work_item',
    'pini.tools.helper.ui.phu_output_item',
    'pini.tools.helper.ui.phu_scene_ref_item',
    'pini.tools.helper.ui.phu_header',
    'pini.tools.helper.ui.phu_work_tab',
    'pini.tools.helper.ui.phu_export_tab',
    'pini.tools.helper.ui.phu_scene_tab',
    'pini.tools.helper.ui.phu_base',
    'pini.tools.helper.ui',
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
    RELOAD_ORDER += _RELOAD_ORDER_APPEND.split(',')


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

    _order = order or RELOAD_ORDER

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
        _val -= _name.count('.') * 0.1
        _LOGGER.log(9, ' - VAL A %f', _val)

        # Apply ordering
        _idx = 0
        _tokens = _name.split('.')
        _LOGGER.log(9, ' - TOKENS %s', _tokens)
        for _idx in range(_name.count('.') + 1):
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
        _val += _order_idx * 10
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
        importlib.reload(mod)
    except ImportError as _exc:
        print("### RELOAD ERROR ###")
        print(traceback.format_exc())
        if not catch:
            from pini import qt
            qt.ok_cancel(
                f'Failed to reload "{_name}".\n\nRemove from '
                f'sys.path?',
                verbose=0)
            del sys.modules[_name]
        return
    _dur = time.time() - _start

    # Print status
    if len(_name) > 53:
        _name = _name[:50] + ' ...'
    lprint(
        f'{sort(_name):<7.02f} {_name:<55} {_dur:5.02f}s    '
        f'{abs_path(mod.__file__)}',
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
        qt.close_all_progress_bars()

    # Get list of modules to reload
    _sort = sort or get_mod_sort(order=RELOAD_ORDER)
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
        _LOGGER.info(
            'Reloaded %d libs in %.01fs', _count, time.time() - _start)

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
    _root = abs_path(check_root) + '/'
    _LOGGER.info('UPDATE LIBS root=%s', _root)

    # Find modules to reload
    _mods = _find_pini_mods(filter_=filter_)
    _LOGGER.info(
        ' - FOUND %d MODS %s', len(_mods), _mods if verbose > 1 else '')
    assert _mods

    # Reload modules until they all fall inside root
    _dur = None
    for _attempt in range(1, attempts + 1):
        check_heart()
        _start = time.time()
        _fails = _count_root_match_fails(root=_root, mods=_mods)
        if not _fails:
            _LOGGER.info(' - NO FAILS attempt=%d', _attempt)
            break
        _LOGGER.info(
            ' - RELOADING MODS attempt=%d fails=%d %s %s',
            _attempt, len(_fails),
            f'dur={_dur:.01f}s' if _dur else '',
            sorted([_mod.__name__ for _mod in _fails]) if verbose > 1 else '')
        reload_libs(mods=_mods, verbose=0)
        _dur = time.time() - _start
    else:
        import pprint
        pprint.pprint(_fails)
        _LOGGER.error(' - FAILS %s', _fails)
        # import testing
        # testing.print_sys_paths()
        pprint.pprint(sys.path)
        raise RuntimeError(_root)

    if verbose > 1:
        for _mod in _mods:
            _LOGGER.info('   - MOD %s', _mod)
    _LOGGER.info(' - UPDATE SUCCESSFUL attempts=%d root=%s', _attempt, _root)
