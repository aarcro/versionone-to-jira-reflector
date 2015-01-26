from jira.client import JIRA as JIRABase


class JIRA(JIRABase):
    """ Subclass of jira-python's jira.client that circumvents a bug.

    In jira-python -- there is currently a bug that prevents us from being
    able to post links.  As currently constructed, jira-python will attempt
    to execute a query to the ``listApplicationlinks/`` endpoint, but that
    endpoint is often secured.

    Querying this endpoint is *not* necessary for creating plain web links,
    so let's just shut that whole thing down.

    This *may* (or may not) be related to these issues:

    * https://bitbucket.org/bspeakmon/jira-python/issue/46
    * https://jira.atlassian.com/browse/JRA-38551

    """
    def applicationlinks(self):
        return []
