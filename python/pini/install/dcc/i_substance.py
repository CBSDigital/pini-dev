"""Tools for managing installing pini in substance."""

from substance_pini import ui

from .. import i_installer


class PISubstanceInstaller(i_installer.PIInstaller):
    """Installs pini in substance."""

    def run(self, *args, **kwargs):
        """Execute this installer."""
        ui.obt_menu(self.name, flush=True)
        super().run(*args, **kwargs)


INSTALLER = PISubstanceInstaller()
