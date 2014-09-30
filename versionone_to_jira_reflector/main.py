import getpass
import logging

from jira.client import JIRA
from six.moves import input
from six.moves.urllib import parse
from v1pysdk import V1Meta

from .exceptions import (
    ConfigurationError,
    NotFound,
)


VERSIONONE_TYPES = {
    'Story': {
        'jira_issue': 'Custom_JIRATicketNumber',
        'code_review_url': 'Custom_UserStoryCodeReview',
        'description': 'Description',
    },
    'Defect': {
        'jira_issue': 'Custom_JiraTicketNumber',
        'code_review_url': 'Custom_DefectCodeReview',
        'description': 'Description',
    }
}


logger = logging.getLogger(__name__)


def get_versionone_connection(config):
    if 'versionone' not in config:
        config['versionone'] = {}

    settings_saved = True

    username = config['versionone'].get('username')
    if not username:
        settings_saved = False
        username = input('VersionOne Username: ')

    url = config['versionone'].get('instance_url')
    if not url:
        settings_saved = False
        url = input(
            'VersionOne Instance URL '
            '(ex: http://www.v1host.com/MyInstance100/): '
        )

    password = getpass.getpass('VersionOne Password: ')

    if not settings_saved:
        save = input('Save VersionOne username and instance URL? (N/y): ')
        if save.upper() and save.upper()[0] == 'Y':
            config['versionone']['username'] = username
            config['versionone']['instance_url'] = url

    parsed_address = parse.urlparse(url)
    address = parsed_address.netloc
    path_parts = filter(None, parsed_address.path.split('/'))
    if not path_parts:
        raise ConfigurationError(
            "Could not identify a VersionOne instance name from '%s'." % (
                url,
            )
        )
    instance = path_parts[0]

    logger.debug(
        'Connecting to VersionOne with the following params: '
        'Address: %s; Instance: %s; Username: %s',
        address,
        instance,
        username,
    )

    connection = V1Meta(
        address,
        instance,
        username,
        password
    )
    return connection


def get_jira_connection(config):
    if 'jira' not in config:
        config['jira'] = {}

    settings_saved = True

    username = config['jira'].get('username')
    if not username:
        settings_saved = False
        username = input('JIRA Username: ')

    domain = config['jira'].get('domain')
    if not domain:
        settings_saved = False
        domain = input(
            'JIRA Domain '
            '(ex: http://jira.mycompany.com/): '
        )

    project = config['jira'].get('project')
    if not project:
        settings_saved = False
        project = input(
            'Default JIRA project for new issues: '
        )

    password = getpass.getpass('JIRA Password: ')

    if not settings_saved:
        save = input('Save JIRA username, domain, and project? (N/y): ')
        if save.upper() and save.upper()[0] == 'Y':
            config['jira']['username'] = username
            config['jira']['domain'] = domain
            config['jira']['project'] = project

    logger.debug(
        'Connecting to JIRA with the following params: ',
        'Domain: %s, Project: %s, Username: %s',
        domain,
        project,
        username
    )

    return JIRA(
        server=domain,
        basic_auth=(username, password)
    )


def get_jira_issue_for_v1_issue(
    versionone_issue, jira_connection, default_project
):
    pass


def get_versionone_story_by_name(connection, story_number):
    for type_name, field_data in VERSIONONE_TYPES.items():
        answers = list(
            getattr(connection, type_name).select(
                *field_data.values()
            ).where(
                Number=story_number
            )
        )
        if answers:
            return answers[0]

    raise NotFound('No story found matching %s' % story_number)


def get_standardized_versionone_data_for_story(story):
    fields = VERSIONONE_TYPES[story.__class__.__name__]
    data = {}

    for standard, custom in fields.items():
        data[standard] = getattr(story, custom, None)

    return standard
