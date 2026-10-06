"""The showcase: the library's demo, one module per concern.

``page`` is the page model (a page is a name, a description and a builder
returning a body of blocks plus how it can be played with); ``components``,
``styles``, ``features``, ``markdown`` and ``chat`` are the pages themselves,
one module per family; ``registry`` lists them and derives the palette lines;
``session`` is the :class:`~showcase.session.Showcase` controller and its host
loop; ``script`` is the headless replay; ``content`` holds the canned copy.

``examples/demo.py`` -- the entry point the README and the benchmark both
name -- is only wiring: it picks the live, piped or ``--pages`` path.
"""
