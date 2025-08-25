"""Tools for managing the rectangular image node."""

from .. import q_utils
from . import png_rect_node


class PNGImgNode(png_rect_node.PNGNode):
    """Node which displays a pixmap."""

    def __init__(self, scene, name, img, **kwargs):
        """Constructor.

        Args:
            scene (QGraphicsScene): scene
            name (str): item name
            img (QPixmap|str): item pixmap
        """
        self.img = img
        self.raw_pix = q_utils.to_pixmap(img)
        super().__init__(scene=scene, name=name, col=None, **kwargs)

    def paint(self, painter, option, widget=None):
        """Paint event.

        Args:
            painter (QPainter): painter
            option (QStyleOptionGraphicsItem): option
            widget (QWidget): parent widget
        """
        super().paint(painter, option, widget)
        _pix = self.raw_pix.resize(self.rect().size())
        _pos = self.rect().topLeft()
        painter.drawPixmap(_pos.x(), _pos.y(), _pix)
