# Copyright 2015 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""Magnum test utilities."""


from magnum.db import api as db_api


def get_test_baymodel(**kw):
    return {
        'id': kw.get('id', 32),
        'uuid': kw.get('uuid', 'e74c40e0-d825-11e2-a28f-0800200c9a66'),
        'name': kw.get('name', 'baymodel1'),
        'image_id': kw.get('image_id', 'ubuntu'),
        'flavor_id': kw.get('flavor_id', 'm1.small'),
        'keypair_id': kw.get('keypair_id', 'keypair1'),
        'external_network_id': kw.get('external_network_id',
                                      'd1f02cfb-d27f-4068-9332-84d907cb0e2e'),
        'dns_nameserver': kw.get('dns_nameserver', '8.8.1.1'),
        'created_at': kw.get('created_at'),
        'updated_at': kw.get('updated_at'),
    }


def get_test_bay(**kw):
    return {
        'id': kw.get('id', 42),
        'uuid': kw.get('uuid', '5d12f6fd-a196-4bf0-ae4c-1f639a523a52'),
        'name': kw.get('name', 'bay1'),
        'baymodel_id': kw.get('baymodel_id',
                              'e74c40e0-d825-11e2-a28f-0800200c9a66'),
        'stack_id': kw.get('stack_id', '047c6319-7abd-4bd9-a033-8c6af0173cd0'),
        'master_address': kw.get('master_address', '172.17.2.3'),
        'minions_address': kw.get('minions_address', ['172.17.2.4']),
        'node_count': kw.get('node_count', 3),
        'created_at': kw.get('created_at'),
        'updated_at': kw.get('updated_at'),
    }


def create_test_bay(**kw):
    """Create test bay entry in DB and return Bay DB object.
    Function to be used to create test Bay objects in the database.
    :param kw: kwargs with overriding values for bay's attributes.
    :returns: Test Bay DB object.
    """
    bay = get_test_bay(**kw)
    # Let DB generate ID if it isn't specified explicitly
    if 'id' not in kw:
        del bay['id']
    dbapi = db_api.get_instance()
    return dbapi.create_bay(bay)


def get_test_pod(**kw):
    return {
        'id': kw.get('id', 42),
        'uuid': kw.get('uuid', '10a47dd1-4874-4298-91cf-eff046dbdb8d'),
        'name': kw.get('name', 'pod1'),
        'desc': kw.get('desc', 'test pod'),
        'bay_uuid': kw.get('bay_uuid', '5d12f6fd-a196-4bf0-ae4c-1f639a523a52'),
        'images': kw.get('images', ['MyImage']),
        'labels': kw.get('labels', {'name': 'foo'}),
        'status': kw.get('status', 'Running'),
        'created_at': kw.get('created_at'),
        'updated_at': kw.get('updated_at'),
    }


def create_test_pod(**kw):
    """Create test pod entry in DB and return Pod DB object.
    Function to be used to create test Pod objects in the database.
    :param kw: kwargs with overriding values for pod's attributes.
    :returns: Test Pod DB object.
    """
    pod = get_test_pod(**kw)
    # Let DB generate ID if it isn't specified explicitly
    if 'id' not in kw:
        del pod['id']
    dbapi = db_api.get_instance()
    return dbapi.create_pod(pod)


def get_test_service(**kw):
    return {
        'id': kw.get('id', 42),
        'uuid': kw.get('uuid', '10a47dd1-4874-4298-91cf-eff046dbdb8d'),
        'name': kw.get('name', 'service1'),
        'bay_uuid': kw.get('bay_uuid', '5d12f6fd-a196-4bf0-ae4c-1f639a523a52'),
        'labels': kw.get('labels', {'name': 'foo'}),
        'selector': kw.get('selector', {'name': 'foo'}),
        'ip': kw.get('ip', '172.17.2.2'),
        'port': kw.get('port', 80),
        'created_at': kw.get('created_at'),
        'updated_at': kw.get('updated_at'),
    }


def create_test_service(**kw):
    """Create test service entry in DB and return Service DB object.
    Function to be used to create test Service objects in the database.
    :param kw: kwargs with overriding values for service's attributes.
    :returns: Test Service DB object.
    """
    service = get_test_service(**kw)
    # Let DB generate ID if it isn't specified explicitly
    if 'id' not in kw:
        del service['id']
    dbapi = db_api.get_instance()
    return dbapi.create_service(service)