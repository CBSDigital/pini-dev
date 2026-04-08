"""Tools for managing installing pini in substance painter."""

from spainter_pini import ui

from .. import i_installer


class PISPainterInstaller(i_installer.PIInstaller):
    """Installs pini in substance painter."""

    def run(self, *args, **kwargs):
        """Execute this installer."""
        ui.obt_menu(self.name, flush=True)
        super().run(*args, **kwargs)


INSTALLER = PISPainterInstaller()
