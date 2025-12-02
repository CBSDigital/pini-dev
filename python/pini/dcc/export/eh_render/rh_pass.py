"""Tools for managing the render pass object."""

from pini import pipe, icons
from pini.tools import helper
from pini.utils import basic_repr

_NO_WORK_ICON = icons.find('Red Circle')


class CRenderPass:
    """Represents a renderable pass in a dcc."""

    def __init__(self, node, name, extn):
        """Constructor.

        Args:
            node (any): pass node
            name (str): pass output name
            extn (str): pass output image format
        """
        self.node = node
        self.name = name
        self.extn = extn

    @property
    def renderable(self):
        """Test whether this pass is renderable."""
        raise NotImplementedError

    def set_renderable(self, renderable):
        """Set renderable state of this pass.

        Args:
            renderable (bool): state to apply
        """
        raise NotImplementedError

    def to_icon(self):
        """Obtain icon for this pass.

        Returns:
            (QPixmap): icon
        """
        _out = self.to_output()
        if _out:
            return helper.output_to_icon(_out)
        return helper.obt_pixmap(_NO_WORK_ICON)

    def to_output(self, work=None):
        """Obtain output for this pass.

        Args:
            work (CPWork): override current work file

        Returns:
            (CPOutput): render output
        """
        _work = work or pipe.CACHE.cur_work
        if not _work:
            return None
        return _work.to_output(
            'render', output_name=self.name, extn=self.extn or 'exr')

    def __eq__(self, other):
        if isinstance(other, CRenderPass):
            return self.node == other.node
        return False

    def __hash__(self):
        return hash(self.name)

    def __lt__(self, other):
        if isinstance(other, CRenderPass):
            return self.node < other.node
        return self.node < other

    def __repr__(self):
        return basic_repr(self, self.name)
