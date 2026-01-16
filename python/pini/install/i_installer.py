"""Tools for managing installers.

These are used to install pini into a dcc interface, and are run
each time a dcc launches.
"""

import copy
import logging

from pini import icons, pipe, dcc
from pini.tools import job_manager
from pini.utils import basic_repr, is_pascal

from .i_tool import PITool, PIDivider
from . import i_tool_defs, i_tool

ICON = icons.find('White Circle')

_LOGGER = logging.getLogger(__name__)


class PIInstaller(object):
    """Used to manage installation of pini tools."""

    name = 'Pini'
    prefix = 'PI'

    _items = None
    allows_context = False

    def __init__(self, name=None, dividers=True, prefix=None, label=None):
        """Constructor.

        Args:
            name (str): override installer name
            dividers (bool): whether to build dividers
            prefix (str): apply name prefix for element uids
            label (str): label for installer (if different from name)
        """
        if name:
            self.name = name
        if prefix:
            self.prefix = prefix
        assert is_pascal(self.name)
        self.dividers = dividers
        self.label = label or self.name

    @property
    def items(self):
        """Obtain/gather list of tools/dividers to install.

        Returns:
            (PITools/PIDivider list): tools/dividers
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
        if 'shelf' in _name.lower():
            return 'shelf'
        return 'menu'

    def _gather_items_list(self):
        """Gather list of tools/dividers to install.

        Returns:
            (PITools/PIDivider list): tools/dividers
        """
        _items = []

        self._gather_helper_tools(_items)

        # Add JobManager
        if pipe.admin_mode():
            _manager = PITool(
                name='JobManager', command='\n'.join([
                    'from pini.tools import job_manager',
                    'job_manager.launch()']),
                icon=job_manager.ICON, label=job_manager.TITLE)
            _LOGGER.debug(' - ADDING SHOT BUILDER (ADMIN MODE)')
            _items += [_manager]

        # Add SanityCheck
        _items += [i_tool_defs.SANITY_CHECK]

        # Add dcc/site items
        _dcc_items = self._gather_dcc_items()
        if _dcc_items:
            _div = PIDivider('DccToolsDivider')
            _items += [_div] + _dcc_items
        _site_items = self._gather_site_items()
        _LOGGER.debug(' - ADD SITE ITEMS %s', _site_items)
        if _site_items:
            _div = PIDivider('SiteToolsDivider')
            _items += [_div] + _site_items
        _, _items = self._gather_reload_tools(_items)

        return _items

    def _gather_helper_tools(self, items):
        """Gather pini helper tools.

        Args:
            items (list): items list to append to
        """
        if not self.allows_context:
            items += [
                i_tool_defs.PINI_HELPER_TOOL,
                i_tool_defs.VERSION_UP_TOOL,
                i_tool_defs.LOAD_RECENT_TOOL,
                PIDivider('DividerA'),
            ]
        else:
            items += [i_tool_defs.PINI_HELPER_TOOL]

    def _gather_dcc_items(self):
        """Add dcc-specfic items (to be implemented in sub-class)."""
        return []

    def _gather_site_items(self):
        """Add site-specfic items (to be implemented in sub-class)."""
        return []

    def _gather_reload_tools(self, items):
        """Gather reload tools.

        For shelves, the reload button is added at the front, but for menus
        the button is added at the end.

        Args:
            items (list): items list to append to

        Returns:
            (list): updated items list
        """
        _items = copy.copy(items)
        _LOGGER.debug('GATHER RELOAD TOOLS')
        _div = PIDivider('ReloadDivider')
        if self.style == 'menu':
            _items += [_div, i_tool_defs.RELOAD_TOOL]
        elif self.style == 'shelf':
            _to_add = [i_tool_defs.RELOAD_TOOL]
            if self.dividers:
                _to_add += [_div]
            _items = _to_add + _items

        return i_tool_defs.RELOAD_TOOL, _items

    def _build_item(self, item, parent=None):
        """Build the given tool/divider.

        Args:
            item (PITool/PIDivider): item to add
            parent (any): item parent

        Returns:
            (any): dcc item representation
        """
        if isinstance(item, i_tool.PITool):
            assert item.command
            return self._build_tool(item, parent=parent)
        if isinstance(item, i_tool.PIDivider):
            return self._build_divider(item, parent=parent)
        raise ValueError(item)

    def _build_tool(self, tool, parent=None):
        """Build the given tool into the dcc.

        Args:
            tool (PITool): tool to build
            parent (any): tool parent

        Returns:
            (any): dcc tool representation
        """
        _tool = dcc.add_menu_item(
            parent=parent, name=tool.to_uid(prefix=self.prefix),
            command=tool.command,
            image=tool.icon, label=tool.label)
        if self.allows_context:
            raise NotImplementedError
        return _tool

    def _build_divider(self, divider, parent=None):
        """Build the given divider into the dcc.

        Args:
            divider (PIDivider): divider to buil
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
            item (PITool/PIDivider): context item
            parent (any): item parent
        """

    def _install_ui_elements(self, parent):
        """Install interface elements (eg. menu/shelf items).

        Args:
            parent (str): name of parent menu/shelf

        Returns:
            (PITool list): tools which were installed
        """
        _LOGGER.debug(' - INSTALL UI ELEMS %d', dcc.batch_mode())

        if dcc.batch_mode():
            return []

        _parent = parent or self.name
        _items = []
        for _item in self.items:
            _LOGGER.debug(' - BUILD ITEM %s parent=%s', _item, _parent)
            _result = self._build_item(_item, parent=_parent)
            _items.append(_result)
            _LOGGER.debug('   - RESULT %s', _result)

        return _items

    def run(self, parent=None, launch_helper=None):  # pylint: disable=unused-argument
        """Execute this installer - build the items into the current dcc.

        Args:
            parent (any): parent for items
            launch_helper (bool): launch pini helper on startup

        Returns:
            (list): new tools
        """
        _LOGGER.info('RUN %s', self)

        _items = self._install_ui_elements(parent=parent)

        return _items

    def to_uid(self):
        """Obtain uid for this installer.

        Returns:
            (str): shelf/menu uid (eg. PI_Pini)
        """
        return self.prefix + '_' + self.name

    def __repr__(self):
        return basic_repr(self, label=None)
