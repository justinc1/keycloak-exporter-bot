import logging
import json
import os
import unittest
from glob import glob
from copy import copy

from kcloader.resource import ClientScopeResource
from kcloader.tools import read_from_json, find_in_list
from ...helper import TestBed, remove_field_id, TestCaseBase

logger = logging.getLogger(__name__)


class TestClientScopeResource(TestCaseBase):
    def setUp(self):
        super().setUp()
        testbed = self.testbed

        # self.client0_clientId = "ci0-client-0"
        # self.clients_api = testbed.kc.build("clients", testbed.REALM)
        # self.realm_roles_api = testbed.kc.build("roles", testbed.REALM)
        # self.roles_by_id_api = testbed.kc.build("roles-by-id", testbed.REALM)
        self.client_scopes_api = testbed.kc.build("client-scopes", testbed.REALM)

    def test_publish_simple(self):
        # client-scope, no roles assigned, no mappers assigned
        def _check_state():
            pass
            TODO

        client_scopes_api = self.client_scopes_api
        client_scope_filepath = os.path.join(self.testbed.DATADIR, "ci0-realm/client-scopes/ci0-client-scope-1-saml.json")
        with open(client_scope_filepath) as ff:
            expected_client_scope = json.load(ff)
            expected_client_scope_clientScopeMappings = expected_client_scope.pop("clientScopeMappings")
            expected_client_scope_scopeMappings = expected_client_scope.pop("scopeMappings")

        blacklisted_client_scopes = sorted([
            "address",
            "email",
            "microprofile-jwt",
            "offline_access",
            "phone",
            "profile",
            "role_list",
            "roles",
            "web-origins",
        ])

        client_scope_resource = ClientScopeResource({
            'path': client_scope_filepath,
            'keycloak_api': self.testbed.kc,
            'realm': self.testbed.REALM,
            'datadir': self.testbed.DATADIR,
        })

        # check initial state
        client_scopes = client_scopes_api.all()
        self.assertEqual(
            blacklisted_client_scopes,
            sorted([client_scope["name"] for client_scope in client_scopes]),
        )

        # publish data - 1st time
        creation_state = client_scope_resource.publish(include_scope_mappings=False)
        self.assertTrue(creation_state)
        # roles_a = realm_roles_api.all()
        # role_a = find_in_list(roles_a, name="ci0-role-0")
        # this_role_composites_api = roles_by_id_api.get_child(roles_by_id_api, role_a["id"], "composites")
        _check_state()

        # publish data - 2nd time, idempotence
        creation_state = client_scope_resource.publish(include_scope_mappings=False)
        self.assertFalse(creation_state)
        _check_state()
