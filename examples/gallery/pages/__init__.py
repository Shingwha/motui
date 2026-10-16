"""The twelve category pages, one module per theme.

Each module exposes one ``page(gallery) -> PageBody`` builder and keeps to
the exhibit grammar (``header`` / ``try_line`` / ``section`` / ``api_note``):
the page answers *what this is*, *what you do here* and *which API line it
is*, and nothing else.  One theme per page -- Text and Markdown on
``content``, the action primitives on ``action``, panes on ``features`` --
with every interactive component mounted as its own block, so a click
resolves to the widget it landed on.
"""
