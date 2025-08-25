# """Tools for managing image nodes."""

# from .. import q_utils
# from . import png_node


# class PNGImgNode(png_node.PNGNode):
#     """Node which displays a pixmap."""

#     def __init__(self, scene, name, img, **kwargs):
#         """Constructor.

#         Args:
#             scene (QGraphicsScene): scene
#             name (str): item name
#             img (QPixmap|str): item pixmap
#         """
#         asdasdas
#         self.img = img
#         self.raw_pix = q_utils.to_pixmap(img)
#         super().__init__(scene=scene, name=name, col=None, **kwargs)

#     def paint(self, painter, option, widget=None):
#         """Paint event.

#         Args:
#             painter (QPainter): painter
#             option (QStyleOptionGraphicsItem): option
#             widget (QWidget): parent widget
#         """
#         super().paint(painter, option, widget)
#         _pix = self.raw_pix.resize(self.rect.size())
#         painter.drawPixmap(self.local_rect.x(), self.local_rect.y(), _pix)
