import getpass
import logging
import webbrowser

from html2text import html2text
import keyring
from six.moves import input
from six.moves.urllib import parse
from v1pysdk import V1Meta
from verlib import NormalizedVersion

from .exceptions import ConfigurationError, NotFound
from .jira_client import JIRA
from .util import response_was_yes
from . import __version__


DEFAULT_SETTINGS = {
    'versionone': {
        'story_types': 'Story,Defect',
    },
    'versionone_Story_fields': {
        'name': 'Name',
        'number': 'Number',
        'jira_issue': 'Custom_JiraTicketNumber2',
        'code_review_url': 'Custom_UserStoryCodeReview',
        'description': 'Description',
    },
    'versionone_Story_static': {
        'issue_type': 'User Story'
    },
    'versionone_Defect_fields': {
        'name': 'Name',
        'number': 'Number',
        'jira_issue': 'Custom_JiraTicketNumber',
        'code_review_url': 'Custom_DefectCodeReview',
        'description': 'Description',
    },
    'versionone_Defect_static': {
        'issue_type': 'Defect',
    },
    'jira': {
        'code_review_field_label': 'Code Review Url',
        'feature_branch_field_label': 'Feature Branch',
        'labels_field_label': 'Labels',
    },
}
BACKREFERENCE_NAME = 'VersionOne Story'


logger = logging.getLogger(__name__)


def ensure_default_settings(config):
    version = NormalizedVersion(__version__)
    if 'version' in config:
        config_version = NormalizedVersion(config['version'])
    else:
        config_version = NormalizedVersion('0.1')

    for section, values in DEFAULT_SETTINGS.items():
        if section not in config:
            config[section] = {}
        for key, value in values.items():
            if key not in config[section] or version > config_version:
                config[section][key] = value

    config['version'] = __version__
    return config


def reset_saved_passwords(config):
    try:
        keyring.delete_password(
            'versionone_to_jira_reflector',
            'versionone'
        )
    except keyring.errors.PasswordDeleteError:
        logger.warning(
            "Unable to delete VersionOne password.  Was one saved?"
        )
    try:
        keyring.delete_password(
            'versionone_to_jira_reflector',
            'jira'
        )
    except keyring.errors.PasswordDeleteError:
        logger.warning(
            "Unable to delete JIRA password.  Was one saved?"
        )


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
        password,
        scheme='https'
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
            '(ex: https://jira.mycompany.com/): '
        )

    parsed_address = parse.urlparse(domain)
    if parsed_address.scheme == 'http':
        logger.warning(
            "You entered an HTTP URL rather than HTTPS; if you encounter "
            "problems updating JIRA issues, you may want to edit your "
            "local configuration file and change the JIRA server settings to "
            "use HTTPS."
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


def get_jira_field_name_by_label(jira_connection, label):
    """ Returns the field name using a label assigned to a custom field.

    Custom fields are not stored in JIRA under their label name; this
    function queries the jira API for the list of fields, searching for
    one matching the supplied label; upon finding the match, the function
    returns the actual field name.  If a match is not found, this function
    returns None.

    """
    matching_fields = [
        f['id']
        for f in jira_connection.fields()
        if label.lower() in f['name'].lower()
    ]
    if matching_fields:
        return matching_fields[0]
    return None


def get_jira_issue_for_v1_issue(jira_connection, config, story):
    """ Returns a JIRA issue matching this story (or None). """
    standardized = get_standardized_versionone_data_for_story(story, config)
    if not standardized['jira_issue']:
        return None

    return jira_connection.issue(
        standardized['jira_issue']
    )


def get_versionone_story_type_dict(config):
    """ Creates a dictionary of Story-type configuration information.

    This dictionary is used for generating standardized story information
    that we can use in later interactions with JIRA.

    Here's an example (the default at the time of this writing) version
    one configuration::

        [versionone]
        story_types = Story,Defect

        [versionone_Story_fields]
        name = Name
        number = Number
        jira_issue = Custom_JIRATicketNumber
        code_review_url = Custom_UserStoryCodeReview
        description = Description

        [versionone_Story_static]
        issue_type = User Story

        [versionone_Defect_fields]
        name = Name
        number = Number
        jira_issue = Custom_JiraTicketNumber
        code_review_url = Custom_DefectCodeReview
        description = Description

        [versionone_Defect_static]
        issue_type = Defect

    Let's start with the ``versionone.story_types`` configuration key.
    This configuration key stores a comma-separated list of story types
    that will be processable.
    This key is used for determining what *other* configuration
    keys to look for, too.

    For each story type, two other configuration sections are expected:

    * ``versionone_STORYTYPE_fields``: Maps the standardized field name
      (left) with a given field name on the VersionOne object type.  In
      this example, you'll see that the column storing the jira issue
      number is named 'Custom_JIRATicketNumber' on Story objects,
      and named 'Custom_JiraTicketNumber' on Defect objects (note that
      the API *is* case-sensitive).
    * ``versionone_STORYTYPE_static``: Sets static keys to be set
      in the returned standardized story data.  In the above example,
      you'll see that the standardized information returned from
      Defects will always have 'issue_type' set to 'Defect', and the
      standardized information returned from Stories will always have
      'issue_type' set to 'User Story'.

    """
    story_types = config['versionone']['story_types'].split(',')
    type_dict = {}
    for story_type in story_types:
        type_dict[story_type] = {
            'static': config['versionone_%s_static' % story_type],
            'fields': config['versionone_%s_fields' % story_type],
        }

    return type_dict


def get_versionone_story_by_name(connection, config, story_number):
    """ Get the VersionOne story object given an identifier.

    VersionOne stories come in a variety of different types (Defects,
    Stories, and more), and each of those types is handled by a
    different endpoint.  This function checks each possible endpoint
    to see if a story matching the supplied identifier exists, and if
    it does, returns the returned object.

    """
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
    """ Get standardized information for a given story.

    VersionOne field names for various things differ per story type, so
    for example:

    +------------+--------------------------+----------------------------+
    | Story Type | JIRA Ticket Number Field | Code Review URL Field      |
    +============+==========================+============================+
    | User Story | Custom_JIRATicketNumber  | Custom_UserStoryCodeReview |
    +------------+--------------------------+----------------------------+
    | Defect     | Custom_JiraTicketNumber  | Custom_DefectCodeReview    |
    +------------+--------------------------+----------------------------+

    To minimize how much cruft this adds to other areas of the application,
    this function will return standardized information for accessing and
    utilizing these fields.

    """
    type_data = get_metadata_for_story_type(story, config)
    data = {}

    for standard, custom in type_data['fields'].items():
        data[standard] = getattr(story, custom, None)

    data.update(type_data['static'])

    return data


def update_jira_ticket_with_versionone_data(
    jira, v1, ticket, story, config, labels,
    open_url=False,
):
    standardized = get_standardized_versionone_data_for_story(story, config)
    html_description = 'No description provided'
    if standardized['description']:
        html_description = html2text(standardized['description'])

    base_params = {
        'summary': '[%s] %s' % (
            standardized['number'],
            standardized['name'],
        ),
        'description': html_description,
    }

    # Custom fields cannot be set on create!
    code_review_field_name = get_jira_field_name_by_label(
        jira, config['jira']['code_review_field_label']
    )
    feature_branch_field_name = get_jira_field_name_by_label(
        jira, config['jira']['feature_branch_field_label']
    )
    labels_field_name = get_jira_field_name_by_label(
        jira, config['jira']['labels_field_label']
    )
    update_params = {
        code_review_field_name: standardized['code_review_url'],
        feature_branch_field_name: standardized['number'],
    }
    if labels:
        update_params['fields'] = {labels_field_name: labels}

    if ticket:
        logger.debug('Updating issue %s', ticket)
        params = base_params.copy()
        params.update(update_params)
        ticket.update(**params)
    else:
        # Only set issue type, assignee when issue is being created
        base_params.update({
            'issuetype':  {
                'name': standardized['issue_type'],
            },
            'assignee': {
                'name': config['jira']['username']
            }
        })
        default_project = config['jira']['project']
        project = input('JIRA project [' + default_project + ']: ')
        if not project:
            project = default_project
        base_params['project'] = {
            'key': project
        }

        logger.debug('Creating new issue.')
        ticket = jira.create_issue(**base_params)
        ticket.update(**update_params)
        logger.debug('Created issue %s', ticket)

    # Update links
    # 1. Fetch links from JIRA
    # 2. Loop through links from V1
    #    a. If the link exists, but does not match -- delete it.
    #    b. If the link does not exist (including if we deleted it
    #       above), create it.
    jira_links = {}
    for link in jira.remote_links(ticket):
        jira_links[link.object.title] = link
        # link.object.url

    for link in story.Links:
        if (
            link.Name in jira_links
            and link.URL != jira_links[link.Name].object.url
        ):
            jira_links[link.Name].delete()
            del jira_links[link.Name]
        # Do *not* make into an elif -- we might have deleted it above
        if link.Name not in jira_links:
            jira.add_remote_link(
                issue=ticket,
                destination={
                    'url': link.URL,
                    'title': link.Name,
                }
            )

    if BACKREFERENCE_NAME not in jira_links:
        jira.add_remote_link(
            issue=ticket,
            destination={
                'url': story.url,
                'title': BACKREFERENCE_NAME
            },
        )

    # Update the VersionOne ticket to store the JIRA Ticket number
    # we just created/updated.  This will ensure that we do not
    # create a new ticket next time this story is synchronized.
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

    if open_url:
        webbrowser.open(
            ticket.permalink()
        )
