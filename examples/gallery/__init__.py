"""The gallery: the library's demo, one module per concern.

``page`` is the page model (a page is a name, a tab label, a description and
a builder returning a body of blocks plus how it can be played with);
``pages/`` holds the twelve category exhibits, one theme per page;
``registry`` lists them and derives the palette's page commands; ``shell``
is the pinned header, the pinned status row and the modal ``Palette``
overlay; ``session`` is the :class:`~gallery.session.Gallery` controller and
its host loop; ``script`` is the headless replay; ``content`` holds the
theme variants and the block splitter.

``examples/demo.py`` -- the entry point the README names -- is only wiring:
it picks the live, piped or ``--pages`` path.

The gallery is **one** page of exhibits and nothing else: there is no
persistent input box anywhere (the ``/`` palette brings its own query row
and disappears when it closes), every interactive component is mounted as
its own block so a click resolves to it, and every page is built from the
same four helpers (``header`` / ``try_line`` / ``section`` / ``api_note``).
"""
