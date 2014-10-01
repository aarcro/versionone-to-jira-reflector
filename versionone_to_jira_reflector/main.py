import getpass
import logging
import webbrowser

from jira.client import JIRA
from html2text import html2text
import keyring
from six.moves import input
from six.moves.urllib import parse
from v1pysdk import V1Meta

from .exceptions import (
    ConfigurationError,
    NotFound,
)
from .util import response_was_yes


DEFAULT_SETTINGS = {
    'versionone': {
        'story_types': 'Story,Defect',
    },
    'versionone_Story_fields': {
        'name': 'Name',
        'number': 'Number',
        'jira_issue': 'Custom_JIRATicketNumber',
        'code_review_url': 'Custom_UserStoryCodeReview',
        'description': 'Description',
    },
    'versionone_Story_static': {
        'issue_type': 'Story'
    },
    'versionone_Defect_fields': {
        'name': 'Name',
        'number': 'Number',
        'jira_issue': 'Custom_JiraTicketNumber',
        'code_review_url': 'Custom_DefectCodeReview',
        'description': 'Description',
    },
    'versionone_Defect_static': {
        'issue_type': 'Bug',
    },
    'jira': {
        'code_review_field_label': 'Code Review Url',
    },
}


logger = logging.getLogger(__name__)


def ensure_default_settings(config):
    for setting_key, values in DEFAULT_SETTINGS.items():
        if setting_key not in config:
            config[setting_key] = values

    return config


def get_versionone_connection(config):
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

    if not settings_saved:
        save = input('Save VersionOne username and instance URL? (N/y): ')
        if response_was_yes(save):
            config['versionone']['username'] = username
            config['versionone']['instance_url'] = url

    password = keyring.get_password(
        'versionone_to_jira_reflector',
        'versionone',
    )
    if not password:
        password = getpass.getpass('VersionOne Password: ')
        save = input('Save VersionOne password to system keychain? (N/y): ')
        if response_was_yes(save):
            keyring.set_password(
                'versionone_to_jira_reflector',
                'versionone',
                password,
            )

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

    if not settings_saved:
        save = input('Save JIRA username, domain, and project? (N/y): ')
        if response_was_yes(save):
            config['jira']['username'] = username
            config['jira']['domain'] = domain
            config['jira']['project'] = project

    password = keyring.get_password(
        'versionone_to_jira_reflector',
        'jira',
    )
    if not password:
        password = getpass.getpass('JIRA Password: ')
        save = input('Save JIRA password to system keychain? (N/y): ')
        if response_was_yes(save):
            keyring.set_password(
                'versionone_to_jira_reflector',
                'jira',
                password
            )

    logger.debug(
        'Connecting to JIRA with the following params: '
        'Domain: %s, Project: %s, Username: %s',
        domain,
        project,
        username
    )

    return JIRA(
        server=domain,
        basic_auth=(username, password)
    )


def get_jira_code_review_field_name(jira_connection, config):
    label = config['jira']['code_review_field_label']
    matching_fields = [
        f['id']
        for f in jira_connection.fields()
        if label.lower() in f['name'].lower()
    ]
    if matching_fields:
        return matching_fields[0]
    return None


def get_jira_issue_for_v1_issue(jira_connection, config, story):
    standardized = get_standardized_versionone_data_for_story(story, config)
    if not standardized['jira_issue']:
        return None

    return jira_connection.issue(
        standardized['jira_issue']
    )


def get_versionone_story_type_dict(config):
    story_types = config['versionone']['story_types'].split(',')
    type_dict = {}
    for story_type in story_types:
        type_dict[story_type] = {
            'static': config['versionone_%s_static' % story_type],
            'fields': config['versionone_%s_fields' % story_type],
        }

    return type_dict


def get_versionone_story_by_name(connection, config, story_number):
    type_metadata = get_versionone_story_type_dict(config)
    for type_name, type_data in type_metadata.items():
        field_data = type_data['fields']
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


def get_metadata_for_story_type(story, config):
    type_metadata = get_versionone_story_type_dict(config)
    return type_metadata[story.__class__.__name__]


def get_standardized_versionone_data_for_story(story, config):
    type_data = get_metadata_for_story_type(story, config)
    data = {}

    for standard, custom in type_data['fields'].items():
        data[standard] = getattr(story, custom, None)

    data.update(type_data['static'])

    return data


def update_jira_ticket_with_versionone_data(jira, v1, ticket, story, config):
    standardized = get_standardized_versionone_data_for_story(story, config)

    params = {
        'project': {
            'key': config['jira']['project'],
        },
        'summary': '[%s] %s' % (
            standardized['number'],
            standardized['name'],
        ),
        'description': html2text(standardized['description']),
        'issuetype': {'name': standardized['issue_type']},
        'assignee': {
            'name': config['jira']['username']
        }
    }

    if ticket:
        logger.debug('Updating issue %s', ticket)
        ticket.update(**params)
        return
    else:
        logger.debug('Creating new issue.')
        ticket = jira.create_issue(**params)
        logger.debug('Created issue %s', ticket)

    # Custom fields cannot be set on create!
    code_review_field_name = get_jira_code_review_field_name(jira, config)
    if code_review_field_name:
        ticket.update(
            **{
                code_review_field_name: standardized['code_review_url']
            }
        )

    type_metadata = get_metadata_for_story_type(story, config)
    setattr(
        story,
        type_metadata['fields']['jira_issue'],
        ticket.key,
    )
    v1.commit()

    logger.info(
        'Issue saved: See %s for results.', ticket.permalink()
    )

    webbrowser.open(
        ticket.permalink()
    )
