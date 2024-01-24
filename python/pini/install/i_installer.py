"""Tools for managing installers.

These are used to install pini into a dcc interface, and are run
each time a dcc launches.
"""

import copy
import logging

from pini import icons, pipe, dcc, testing, qt
from pini.tools import helper, job_manager, sanity_check, error
from pini.utils import basic_repr, wrap_fn

from .i_tool import CITool, CIDivider

ICON = icons.find('White Circle')

_LOGGER = logging.getLogger(__name__)


class CIInstaller(object):
    """Used to manage installation of pini tools."""

    name = 'Pini'
    prefix = 'PI'
    _items = None
    allows_context = False

    def __init__(self, dividers=True):
        """Constructor.

        Args:
            dividers (bool): whether to build dividers
        """
        self.dividers = dividers
        self.helper_cmd = '\n'.join([
            'from pini.tools import helper',
            'helper.launch()'])
        self.refresh_cmd = '\n'.join([
            'from pini import refresh',
            'refresh.reload_libs()'])

    @property
    def items(self):
        """Obtain/gather list of tools/dividers to install.

        Returns:
            (CITools/CIDivider list): tools/dividers
        """
        if self._items is None:
            self._items = self._gather_items_list()
        return self._items

    @property
    def style(self):
        """Obtain style for this installer.

        Returns:
            (str): style (menu/shelf)
        """
        _name = type(self).__name__
        if 'menu' in _name.lower():
            return 'menu'
        if 'shelf' in _name.lower():
            return 'shelf'
        raise ValueError(_name)

    def _gather_items_list(self):
        """Gather list of tools/dividers to install.

        Returns:
            (CITools/CIDivider list): tools/dividers
        """
        _items = []

        self._gather_helper_tools(_items)

        # Add JobManager
        if pipe.admin_mode():
            _manager = CITool(
                name=self.prefix+'_JobManager', command='\n'.join([
                    'from pini.tools import job_manager',
                    'job_manager.launch()']),
                icon=job_manager.ICON, label=job_manager.TITLE)
            _LOGGER.debug(' - ADDING SHOT BUILDER (ADMIN MODE)')
            _items += [_manager]

        # Add SanityCheck
        _sanity = CITool(
            name=self.prefix+'_SanityCheck', command='\n'.join([
                'from pini.tools import sanity_check',
                'sanity_check.launch_ui()']),
            icon=sanity_check.ICON, label='Sanity Check')
        _items += [_sanity]

        # Add dcc/site items
        _dcc_items = self._gather_dcc_items()
        if _dcc_items:
            _div = CIDivider(self.prefix+'DccToolsDivider')
            _items += [_div] + _dcc_items
        _site_items = self._gather_site_items()
        _LOGGER.info(' - ADD SITE ITEMS %s', _site_items)
        if _site_items:
            _div = CIDivider(self.prefix+'SiteToolsDivider')
            _items += [_div] + _site_items
        _, _items = self._gather_refresh_tools(_items)

        return _items

    def _gather_helper_tools(self, items):
        """Gather pini helper tools.

        Args:
            items (list): items list to append to
        """
        _helper = CITool(
            name=self.prefix+'_PiniHelper', command=self.helper_cmd,
            icon=helper.ICON, label=helper.TITLE)
        _version_up = CITool(
            name=self.prefix+'_VersionUp', command='\n'.join([
                'from pini import pipe',
                'pipe.version_up()']),
            icon=icons.find('Up Arrow'), label='Version Up')
        _load_recent = CITool(
            name=self.prefix+'_LoadRecent', command='\n'.join([
                'from pini import pipe',
                'pipe.load_recent()']),
            icon=icons.LOAD, label='Load recent')

        # Context only
        _launch_basic = CITool(
            name=self.prefix+'_PiniHelperBasic',
            label='Launch basic {}'.format(helper.TITLE),
            icon=helper.ICON, command='\n'.join([
                'from pini.tools import helper',
                'helper.launch(use_basic=True)']))
        _revert = CITool(
            name=self.prefix+'_Revert', label='Revert scene', icon=icons.LOAD,
            command='\n'.join([
                'from pini import dcc',
                '_file = dcc.cur_file()',
                'dcc.load(_file)']))
        _copy_cur_scene = CITool(
            name=self.prefix+'_CopyCurScene',
            label='Copy path to current scene',
            icon=icons.COPY, command='\n'.join([
                'from pini import dcc',
                'from pini.utils import copy_text',
                'copy_text(dcc.cur_file())']))
        _copy_sel_ref = CITool(
            name=self.prefix+'_CopySelRef',
            label='Copy path to selected reference',
            icon=icons.COPY, command='\n'.join([
                'from pini import dcc',
                'from pini.utils import copy_text',
                'copy_text(dcc.find_pipe_ref(selected=True).path)']))

        if not self.allows_context:
            items += [
                _helper,
                _version_up,
                _load_recent,
                CIDivider(self.prefix+'_DividerA'),
            ]
        else:
            _ctx_items = [
                _launch_basic,
                CIDivider(''),
                _version_up,
                _load_recent,
                _revert,
                CIDivider(''),
                _copy_cur_scene,
                _copy_sel_ref,
            ]
            for _item in _ctx_items:
                _helper.add_context(_item)
            items += [_helper]

    def _gather_dcc_items(self):
        """Add dcc-specfic items (to be implemented in sub-class)."""
        return []

    def _gather_site_items(self):
        """Add site-specfic items (to be implemented in sub-class)."""
        return []

    def _gather_refresh_tools(self, items):
        """Gather refresh tools.

        For shelves, the refresh button is added at the front, but for menus
        the button is added at the end.

        Args:
            items (list): items list to append to

        Returns:
            (list): updated items list
        """
        _items = copy.copy(items)

        _LOGGER.debug('GATHER REFRESH TOOLS')
        _refresh = CITool(
            name=self.prefix+'_Refresh', command=self.refresh_cmd,
            icon=icons.REFRESH, label='Reload tools')

        _fs_toggle = wrap_fn(testing.enable_file_system, None)
        _nir_toggle = wrap_fn(testing.enable_nice_id_repr, None)
        for _ctx in [
                CITool(
                    name=self.prefix+'_ToggleErrorCatcher',
                    label='Toggle error catcher',
                    icon=icons.find('Police Car Light'), command=error.toggle),
                CITool(
                    name=self.prefix+'_ToggleSanityCheck',
                    label='Toggle sanity check',
                    icon=icons.find('Police Car Light'),
                    command=testing.enable_sanity_check),
                CITool(
                    name=self.prefix+'_ToggleFileSystem',
                    label='Toggle file system',
                    icon=icons.find('Police Car Light'), command=_fs_toggle),
                CITool(
                    name=self.prefix+'_ToggleNiceIdRepr',
                    label='Toggle nice id repr',
                    icon=icons.find('Police Car Light'), command=_nir_toggle),
                CITool(
                    name=self.prefix+'_FlushDialogStack',
                    label='Flush dialog stack',
                    icon=icons.CLEAN, command=qt.flush_dialog_stack),
        ]:
            _refresh.add_context(_ctx)

        _div = CIDivider(self.prefix+'_RefreshDivider')
        if self.style == 'menu':
            _items += [_div, _refresh]
        elif self.style == 'shelf':
            _to_add = [_refresh]
            if self.dividers:
                _to_add += [_div]
            _items = _to_add + _items

        return _refresh, _items

    def _build_item(self, item, parent=None):
        """Build the given tool/divider.

        Args:
            item (CITool/CIDivider): item to add
            parent (any): item parent

        Returns:
            (any): dcc item representation
        """
        if isinstance(item, CITool):
            assert item.command
            return self._build_tool(item, parent=parent)
        if isinstance(item, CIDivider):
            return self._build_divider(item, parent=parent)
        raise ValueError(item)

    def _build_tool(self, tool, parent=None):
        """Build the given tool into the dcc.

        Args:
            tool (CITool): tool to build
            parent (any): tool parent

        Returns:
            (any): dcc tool representation
        """
        _tool = dcc.add_menu_item(
            parent=parent, name=tool.name,
            command=tool.command,
            image=tool.icon, label=tool.label)
        if self.allows_context:
            raise NotImplementedError
        return _tool

    def _build_divider(self, divider, parent=None):
        """Build the given divider into the dcc.

        Args:
            divider (CIDivider): divider to buil
            parent (any): divider parent

        Returns:
            (any): dcc tool representation
        """
        return dcc.add_menu_divider(parent=parent, name=divider.name)

    def _build_context_item(self, item, parent):
        """Build a context (right-click) item.

        In the case of menu installers this will do nothing, but in shelf
        installers this can be implemented if it is supported in the dcc
        (eg. in maya but not houdini).

        Args:
            item (CITool/CIDivider): context item
            parent (any): item parent
        """

    def run(self, parent='Pini', launch_helper=True):  # pylint: disable=unused-argument
        """Execute this installer - build the items into the current dcc.

        Args:
            parent (any): parent for items
            launch_helper (bool): launch pini helper on startup

        Returns:
            (list): new tools
        """
        _LOGGER.info('RUN %s', self)
        _results = []
        for _item in self.items:
            _LOGGER.debug(' - BUILD ITEM %s parent=%s', _item, parent)
            _result = self._build_item(_item, parent=parent)
            _results.append(_result)
            _LOGGER.debug('   - RESULT %s', _result)
        return _results

    def __repr__(self):
        return basic_repr(self, label=None)
