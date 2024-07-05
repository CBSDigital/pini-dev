"""Base class for graph space and graph space elements."""

# pylint: disable=no-member

from pini.utils import single, passes_filter


class CGraphElemBase(object):
    """Base class for graph + elements."""

    def append_child_elem(self, elem):
        """Add element to this space.

        Args:
            elem (CGraphElem): element to adde
        """
        if elem.name in (_elem.name for _elem in self.elems):
            raise RuntimeError('Name clash '+elem.name)

        # Set graph link
        elem.graph = self
        for _child in elem.find_elems():
            _child.graph = self

        self.elems.append(elem)

    def add_basic_elem(self, class_=None, **kwargs):
        """Add basic element to the graph.

        Args:
            class_ (class): override element class

        Returns:
            (CGBasicElem): basic element
        """
        from . import elem
        _class = class_ or elem.CGBasicElem
        return _class(parent=self, **kwargs)

    def add_icon_elem(self, icon, **kwargs):
        """Add icon element to the graph.

        Args:
            icon (str/CPixmap): icon to display

        Returns:
            (CGIconElem): icon element
        """
        from . import elem
        return elem.CGIconElem(icon, parent=self, **kwargs)

    def add_move_elem(self, **kwargs):
        """Add move element to the graph.

        Returns:
            (CGMoveElem): move element
        """
        from . import elem
        return elem.CGMoveElem(parent=self, **kwargs)

    def add_stretch_elem(self, class_=None, **kwargs):
        """Add stretch element to the graph.

        Args:
            class_ (class): override element class

        Returns:
            (CGStretchElem): stretch element
        """
        from . import elem
        _class = class_ or elem.CGStretchElem
        return _class(parent=self, **kwargs)

    def add_text_elem(self, text, **kwargs):
        """Add a text element to the graph.

        Args:
            text (str): element text

        Returns:
            (CGTextElem): text element
        """
        from . import elem
        return elem.CGTextElem(parent=self, text=text, **kwargs)

    def find_elem(self, match=None, selected=None, catch=True):
        """Find element inside this space.

        Args:
            match (str): token to match (eg. name)
            selected (bool): filter by selected status
            catch (bool): no error if element no found

        Returns:
            (CGraphElem): matching element
        """
        _elems = self.find_elems(selected=selected)

        if len(_elems) == 1:
            return single(_elems)

        _match_elems = [
            _elem for _elem in _elems if match in (_elem.name, _elem.full_name)]
        if len(_match_elems) == 1:
            return single(_match_elems)

        _filter_elems = [
            _elem for _elem in _elems if passes_filter(_elem.name, match)]
        if len(_filter_elems) == 1:
            return single(_filter_elems)

        if catch:
            return None
        raise ValueError(match)

    def find_elems(
            self, saveable=None, head=None, class_=None, selected=None,
            recursive=True):
        """Find child elements of this space.

        Args:
            saveable (bool): filter by saveable state
            head (str): filter by start of name
            class_ (class): filter by class
            selected (bool): filter by selected status
            recursive (bool): find elements within elements

        Returns:
            (CGraphElem list): matching elements
        """
        _elems = []
        for _elem in self._read_elems(recursive=recursive):
            if class_ and not isinstance(_elem, class_):
                continue
            if saveable is not None and saveable != _elem.saveable:
                continue
            if head and not _elem.name.startswith(head):
                continue
            if selected is not None and _elem.selected != selected:
                continue
            _elems.append(_elem)

        return _elems

    def _read_elems(self, recursive=True):
        """Read all child elements.

        Args:
            recursive (bool): read children of children

        Returns:
            (CGBasicElem list): children
        """
        _elems = []
        for _elem in self.elems:
            _elems.append(_elem)
            if recursive:
                _elems += _elem.find_elems()
        return _elems
