#!/usr/bin/env python

# (c) 2013, Jesse Keating <jesse.keating@rackspace.com>
# (c) 2013, Kevin Carter <kevin.carter@rackspace.com>
#
# This file is part of Ansible,
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
inventory: rax
short_description: Rackspace Public Cloud external inventory script
description:
  >
  Generates inventory that Ansible can understand by making API request to
  Rackspace Public Cloud API
  - |
    >
    When run against a specific host, this script returns the following
    variables:
        rax_os-ext-sts_task_state
        rax_addresses
        rax_links
        rax_image
        rax_os-ext-sts_vm_state
        rax_flavor
        rax_id
        rax_rax-bandwidth_bandwidth
        rax_user_id
        rax_os-dcf_diskconfig
        rax_accessipv4
        rax_accessipv6
        rax_progress
        rax_os-ext-sts_power_state
        rax_metadata
        rax_status
        rax_updated
        rax_hostid
        rax_name
        rax_created
        rax_tenant_id
        rax__loaded

    where some item can have nested structure.
  - credentials are set in a credentials file
version_added: None
options:
  creds_file:
    description:
     - File to find the Rackspace Public Cloud credentials in
    required: true
    default: null
  region_name:
    description:
      - Region name to use in request
    required: false
    default: DFW
author: Jesse Keating
notes:
  - Two environment variables can be set, RAX_CREDS and RAX_REGION.
  - If the RAX_CREDS is not set the default ANSIBLE_CONFIG will be used.
  - Look at rax.ini for an example of the available config file.
  - RAX_CREDS points to a credentials file.
  - RAX_REGION defines a Rackspace Public Cloud region (DFW, ORD, LON, ...)
requirements: [ "novaclient" ]
examples:
    - description: List server instances
      code: RAX_CREDS=~/.raxpub RAX_REGION=ORD rax.py --list
    - description: List server instance properties
      code: RAX_CREDS=~/.raxpub RAX_REGION=ORD rax.py --host <HOST_IP>
'''
import ConfigParser
try:
    import json
except ImportError:
    import simplejson as json
import os
import sys

from novaclient import client as nova_client


def get_addresses(addr):
    # Find Private addresses
    private = [x['addr'] for x in addr
               if 'OS-EXT-IPS:type' in x and x['OS-EXT-IPS:type'] == 'fixed']

    # Find Public addresses
    public = [x['addr'] for x in addr
              if 'OS-EXT-IPS:type' in x and x['OS-EXT-IPS:type'] == 'floating']

    # Find DHCP(legacy) addresses
    legacy = [x['addr'] for x in addr
              if 'version' in x and x['version'] == 4]

    return private, public, legacy


def nova_load_config_file():
    p = ConfigParser.ConfigParser()
    path1 = os.environ.get(
        'RAX_CREDS_FILE', os.environ.get('ANSIBLE_CONFIG', "~/rax.ini")
    )
    path2 = os.getcwd() + "/rax.ini"
    path3 = "/etc/ansible/rax.ini"

    for path in path1, path2, path3:
        if os.path.exists(path):
            p.read(path)
            break
    else:
        sys.exit('No Configuration File could be found in [%s, %s, %s]'
                 % (path3, path2, path1))
    return p


class auth_plugin(object):
    def __init__(self):
        """Craetes an authentication plugin for use with Rackspace."""

        self.auth_url = self.global_auth()

    def global_auth(self):
        """Return the Rackspace Cloud US Auth URL."""

        return "https://identity.api.rackspacecloud.com/v2.0/"

    def _authenticate(self, cls, auth_url):
        """Authenticate against the Rackspace auth service."""

        body = {"auth": {
            "RAX-KSKEY:apiKeyCredentials": {
                "username": cls.user,
                "apiKey": cls.password,
                "tenantName": cls.projectid}}}
        return cls._authenticate(auth_url, body)

    def authenticate(self, cls, auth_url):
        """Authenticate against the Rackspace US auth service."""

        return self._authenticate(cls, auth_url)


# Parse Configuration File
config = nova_load_config_file()
username = config.get('rackspace_cloud', 'username')
password = config.get('rackspace_cloud', 'api_key')

# Load our Authentication Plugin
plugin = auth_plugin()

client = nova_client.Client(
    version=2,
    username=username,
    api_key=password,
    auth_url=plugin.auth_url,
    region_name=config.get('rackspace_cloud', 'region'),
    project_id=username,
    auth_system='rackspace',
    auth_plugin=plugin
)


###################################################
# executed with no parameters, return the list of
# all groups and hosts
if len(sys.argv) == 2 and (sys.argv[1] == '--list'):
    groups = {}

    # Cycle on servers
    for instance in client.servers.list():
        private, public, legacy = get_addresses(
            addr=getattr(instance, 'addresses').itervalues().next()
        )
        # Define group (or set to empty string)
        group = instance.metadata.get('group', 'undefined')

        # Create group if not exist
        if group not in groups:
            groups[group] = []

        # Append group to list
        ips = [instance.accessIPv4,
               ', '.join(private),
               ', '.join(public)]
        if not instance.accessIPv4:
            ips.append(', '.join(legacy))

        for addr in ips:
            if addr:
                _instance = '%s: %s' % (instance.name, addr)
                groups[group].append(_instance)
            continue
        del ips

    # Return server list
    print(json.dumps(groups, indent=2))
    sys.exit(0)

#####################################################
# executed with a hostname as a parameter, return the
# variables for that host
elif len(sys.argv) == 3 and (sys.argv[1] == '--host'):
    results = {}
    for instance in client.servers.list():
        private, public, legacy = get_addresses(
            addr=getattr(instance, 'addresses').itervalues().next()
        )

        # Append group to list
        ips = [instance.accessIPv4,
               ', '.join(private),
               ', '.join(public)]
        if not instance.accessIPv4:
            ips.append(', '.join(legacy))

        if sys.argv[2] in ips:
            for key in [key for key in vars(instance) if key not in 'manager']:
                # Extract value
                value = getattr(instance, key)

                # Generate sanitized key
                key = 'rax_%s' % key.lower()

                #TODO(UNKNOWN): maybe use value.__class__ or similar inside
                #TODO(UNKNOWN): of key_name

                # Att value to instance result (exclude manager class)
                results[key] = value
        del ips

    print(json.dumps(results, indent=2))
    sys.exit(0)
else:
    print("usage: --list  ..OR.. --host <hostname>")
    sys.exit(1)
