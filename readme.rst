VersionOne to JIRA Reflector
============================


This is a little utility you can use for creating/updating JIRA issues
matching one's VersionOne stories.


Installation
------------

Using pip::

    pip install versionone-to-jira-reflector

Use
---

The first time you run the command, it will ask you for various bits
of information that it will use for interacting with VersionOne
and JIRA.

Basic use:

.. code-block::

   v1tojira D-08248

The app will proceed to ask you for connection information if such
details have not previously been saved, and will create or update
a JIRA issue to match your the story identifiers you have supplied.

.. note::

   All configuration data except passwords will be written to
   ``~/.versionone-to-jira-reflector`` should you need to edit it after
   saving.  Passwords will be queried from (and saved to) the system
   keyring.


Caveat Emptor
-------------

Although this is a totally workable solution, this was mostly a quick
hack to solve a temporary need, and it isn't exactly code that I'm
proud of.  If you end up using this tool, feel free to fork this
code and clean things up to your liking.
