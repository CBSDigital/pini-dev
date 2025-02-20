"""Tools for managing icon elements."""

from ... import q_utils
from . import cg_move_elem


class CGIconElem(cg_move_elem.CGMoveElem):
    """An element which displays an icon."""

    def __init__(
            self, icon, col='Transparent', bevel=0, lock=True, scale=0.9,
            **kwargs):
        """Constructor.

        Args:
            icon (str/CPixmap): icon to display
            col (str): background colour
            bevel (int): edge bevel (in graph space)
            lock (str): axis lock
                None/False - no lock
                H - horizontal lock
                V - vertical lock
                True - lock movement
            scale (float): icon scale
        """
        self.pixmap = q_utils.to_pixmap(icon)
        self.scale = scale
        super().__init__(
            col=col, bevel=bevel, lock=lock, **kwargs)

    def update_pixmap(self, pix):
        """Update this element's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on (in local space)
        """
        pix.fill(self.col)
        pix.draw_overlay(
            self.pixmap, size=pix.size() * self.scale, anchor='C',
            pos=pix.center())
