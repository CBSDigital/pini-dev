"""Tools for managing the cacheable object."""

import logging

from pini import pipe, qt

_LOGGER = logging.getLogger(__name__)


class CCacheable:
    """Base class for any object that can be cached to file/seq."""

    def __init__(
            self, output_name, extn, node, src_ref,
            output_type=None, label=None, icon=None, ref=None,
            template=None, top_node=None):
        """Constructor.

        Args:
            output_name (str): output name for export
            extn (str): output extension
            node (any): node being cached
            src_ref (CPOutput): source reference (eg. rig asset)
            output_type (str): output type for export
            label (str): override cacheable label
            icon (str): path to icon for this object
            ref (CReference): reference associated with this object
            template (CPTemplate): override template for output
            top_node (str): top node for this cache set
        """
        self.output_name = output_name
        self.output_type = output_type
        self.label = label or output_name
        self.extn = extn

        self._icon = icon

        self.template = template
        self.src_ref = src_ref
        self.ref = ref

        self.node = node
        self.top_node = top_node

    @property
    def icon(self):
        """Obtain path to icon for this cacheable.

        Returns:
            (str): path to icon
        """
        return self._to_icon()

    @property
    def output(self):
        """Obtain path to output for this cacheable.

        Returns:
            (CPOutput): path to cache file (eg. abc)
        """
        return self._to_output()

    def rename(self):
        """Rename this cacheable."""
        _name = qt.input_dialog(
            f'Enter new name for cacheable "{self.label}":',
            title='Rename cacheable')
        self._set_name(_name)

    def _set_name(self, name):
        """Set name of this cacheable.

        Args:
            name (str): name to apply
        """
        raise NotImplementedError

    def _to_icon(self):
        """Obtain icon for this cacheable.

        Returns:
            (str): path to icon
        """
        if self._icon:
            return self._icon
        raise RuntimeError(f"No icon set for cacheable {self.label}")

    def _to_output(self):
        """Get an output based on this camera.

        Returns:
            (CPOutput): output abc
        """
        _LOGGER.debug('TO OUTPUT %s', self)
        _work = pipe.cur_work()
        if not _work:
            return None
        _tmpl = self.template or _work.find_template(
            'cache', has_key={'output_name': True})
        return _work.to_output(
            _tmpl, extn=self.extn, output_type=self.output_type,
            output_name=self.output_name, task=_work.task)
