import logging
import json
import os
import unittest
from glob import glob
from copy import copy

from kcapi.rest.crud import KeycloakCRUD

from kcloader.resource import ClientScopeResource, ClientScopeMappingsRealmManager, \
    ClientScopeScopeMappingsClientManager, ClientScopeScopeMappingsAllClientsManager, \
    ClientScopeMappingsClientManager, ClientScopeMappingsAllClientsManager
from kcloader.tools import read_from_json, find_in_list
from ...helper import TestBed, remove_field_id, TestCaseBase

logger = logging.getLogger(__name__)


class TestClientScopeMappingsRealmManager(TestCaseBase):
    # Test Client--ClientScope--ScopeMappings--Realm Manager
    def setUp(self):
        super().setUp()
        testbed = self.testbed

        self.client0_clientId = "ci0-client-0"
        self.clients_api = testbed.kc.build("clients", testbed.REALM)
        self.realm_roles_api = testbed.kc.build("roles", testbed.REALM)
        # self.roles_by_id_api = testbed.kc.build("roles-by-id", testbed.REALM)
        self.client_scopes_api = testbed.kc.build("client-scopes", testbed.REALM)

        # create required client
        clients_all = self.clients_api.all()
        self.assertEqual(len(clients_all), 6 + 0)
        self.clients_api.create(dict(
            clientId="ci0-client-0",
            description="ci0-client-0---CI-INJECTED",
            protocol="openid-connect",
            fullScopeAllowed=False,  # this makes client:scopes configurable
        )).isOk()
        clients_all = self.clients_api.all()
        self.assertEqual(len(clients_all), 6 + 1)
        self.client0 = find_in_list(clients_all, clientId="ci0-client-0")

        # create required realm role
        self.realm_roles_api.create({
            "name": "ci0-role-0",
            "description": "ci0-role-0-desc---CI-injected",
        }).isOk()
        self.role0 = self.realm_roles_api.findFirstByKV("name", "ci0-role-0")
        # create an extra role
        self.realm_roles_api.create({
            "name": "ci0-role-TEMP",
            "description": "ci0-role-TEMP-desc---CI-injected",
        }).isOk()
        self.role_temp = self.realm_roles_api.findFirstByKV("name", "ci0-role-TEMP")

        # create required client role

        # GET /{realm}/clients/{client_id}/scope-mappings/realm
        self.this_client_scopeMappings_realm_api = KeycloakCRUD.get_child(self.clients_api, self.client0["id"], "scope-mappings/realm")

    def test_publish(self):
        def _check_state():
            client_scopeMappings_realm_b = this_client_scopeMappings_realm_api.all()
            self.assertEqual(client_scopeMappings_realm_a[0]["id"], client_scopeMappings_realm_b[0]["id"])
            self.assertEqual(client_scopeMappings_realm_a, client_scopeMappings_realm_b)
            client_scopeMappings_realm_names = [rr["name"] for rr in client_scopeMappings_realm_b]
            self.assertEqual(
                expected_client_scopeMappings_realm_names,
                client_scopeMappings_realm_names,
            )
            # -------------------------------------------

        this_client_scopeMappings_realm_api = self.this_client_scopeMappings_realm_api
        # requested_client_scopeMappings_realm_names - needs to be computed
        # from ci0-realm/clients/client-0/scope-mappings.json
        requested_client_scopeMappings_realm_names = ["ci0-role-0"]
        expected_client_scopeMappings_realm_names = ["ci0-role-0"]

        # check initial state
        self.assertEqual([], this_client_scopeMappings_realm_api.all())

        # create/update
        manager = ClientScopeMappingsRealmManager(
            self.testbed.kc,
            self.testbed.REALM,
            self.testbed.DATADIR,
            requested_doc=requested_client_scopeMappings_realm_names,
            client_id=self.client0["id"],
        )
        creation_state = manager.publish()
        self.assertTrue(creation_state)
        client_scopeMappings_realm_a = this_client_scopeMappings_realm_api.all()
        _check_state()
        creation_state = manager.publish()
        self.assertFalse(creation_state)
        _check_state()

        # add one extra mapping, it needs to be removed
        self.assertEqual(1, len(this_client_scopeMappings_realm_api.all()))
        realm_role_extra = self.realm_roles_api.findFirstByKV("name", "ci0-role-TEMP")
        realm_role_extra.pop("attributes")
        this_client_scopeMappings_realm_api.create([realm_role_extra])
        self.assertEqual(2, len(this_client_scopeMappings_realm_api.all()))
        #
        creation_state = manager.publish()
        self.assertTrue(creation_state)
        _check_state()
        creation_state = manager.publish()
        self.assertFalse(creation_state)
        _check_state()


class TestClientScopeMappingsClientManager(TestCaseBase):
    # Test Client--ClientScope--ScopeMappings--Client Manager
    # managed client is
    def setUp(self):
        super().setUp()
        testbed = self.testbed

        # We will assign roles from src_client to dest_client scope_mappings
        self.dest_client_clientId = "ci0-client-0"
        self.src_client_clientId = "account"
        self.clients_api = testbed.kc.build("clients", testbed.REALM)
        # self.realm_roles_api = testbed.kc.build("roles", testbed.REALM)
        # self.roles_by_id_api = testbed.kc.build("roles-by-id", testbed.REALM)
        # self.client_scopes_api = testbed.kc.build("client-scopes", testbed.REALM)

        # create required client
        clients_all = self.clients_api.all()
        self.assertEqual(len(clients_all), 6 + 0)
        self.clients_api.create(dict(
            clientId="ci0-client-0",
            description="ci0-client-0---CI-INJECTED",
            protocol="openid-connect",
            fullScopeAllowed=False,  # this makes client:scopes configurable
        )).isOk()
        clients_all = self.clients_api.all()
        self.assertEqual(len(clients_all), 6 + 1)
        self.dest_client = find_in_list(clients_all, clientId=self.dest_client_clientId)

        self.src_client = find_in_list(clients_all, clientId=self.src_client_clientId)

        # find src_client roles
        src_client_roles_api = self.clients_api.roles({'key': 'id', 'value': self.src_client["id"]})
        src_client_roles = src_client_roles_api.all()
        self.src_role_0 = find_in_list(src_client_roles, name="view-consent")
        self.src_role_1 = find_in_list(src_client_roles, name="view-profile")

        # GET /{realm}/clients/{client_id}/scope-mappings/realm
        self.dest_client_scopeMappings_client_api = KeycloakCRUD.get_child(self.clients_api, self.dest_client["id"], f"scope-mappings/clients/{self.src_client['id']}")

    def test_publish(self):
        def _check_state():
            client_scopeMappings_client_b = dest_client_scopeMappings_client_api.all()
            self.assertEqual(client_scopeMappings_client_a[0]["id"], client_scopeMappings_client_b[0]["id"])
            self.assertEqual(client_scopeMappings_client_a, client_scopeMappings_client_b)
            client_scopeMappings_client_names = [rr["name"] for rr in client_scopeMappings_client_b]
            self.assertEqual(
                expected_client_scopeMappings_client_names,
                client_scopeMappings_client_names,
            )
            # -------------------------------------------

        dest_client_scopeMappings_client_api = self.dest_client_scopeMappings_client_api
        # requested_client_scopeMappings_client_names - needs to be computed
        # from ci0-realm/clients/client-0/scope-mappings.json
        requested_client_scopeMappings_client_names = ["view-consent"]
        expected_client_scopeMappings_client_names = ["view-consent"]

        # check initial state
        self.assertEqual([], dest_client_scopeMappings_client_api.all())

        # create/update
        manager = ClientScopeMappingsClientManager(
            self.testbed.kc,
            self.testbed.REALM,
            self.testbed.DATADIR,
            requested_doc=requested_client_scopeMappings_client_names,
            dest_client_id=self.dest_client["id"],
            src_client_id=self.src_client["id"],
        )
        creation_state = manager.publish()
        self.assertTrue(creation_state)
        client_scopeMappings_client_a = dest_client_scopeMappings_client_api.all()
        _check_state()
        creation_state = manager.publish()
        self.assertFalse(creation_state)
        _check_state()

        # add one extra mapping, it needs to be removed
        self.assertEqual(1, len(dest_client_scopeMappings_client_api.all()))
        dest_client_scopeMappings_client_api.create([self.src_role_1]).isOk()
        self.assertEqual(2, len(dest_client_scopeMappings_client_api.all()))
        #
        creation_state = manager.publish()
        self.assertTrue(creation_state)
        _check_state()
        creation_state = manager.publish()
        self.assertFalse(creation_state)
        _check_state()


class TestClientScopeMappingsAllClientsManager(TestCaseBase):
    # Test Client--ClientScope--ScopeMappings--* Manager
    def setUp(self):
        super().setUp()
        testbed = self.testbed

        # We will assign roles from src_client to dest_client scope_mappings
        self.dest_client_clientId = "ci0-client-0"
        self.src_client_0_clientId = "account"  # roles view-consent, view-profile
        self.src_client_1_clientId = "broker"  # roles read-token
        self.clients_api = testbed.kc.build("clients", testbed.REALM)
        # self.realm_roles_api = testbed.kc.build("roles", testbed.REALM)
        # self.roles_by_id_api = testbed.kc.build("roles-by-id", testbed.REALM)
        # self.client_scopes_api = testbed.kc.build("client-scopes", testbed.REALM)

        # create required client
        clients_all = self.clients_api.all()
        self.assertEqual(len(clients_all), 6 + 0)
        self.clients_api.create(dict(
            clientId="ci0-client-0",
            description="ci0-client-0---CI-INJECTED",
            protocol="openid-connect",
            fullScopeAllowed=False,  # this makes client:scopes configurable
        )).isOk()
        clients_all = self.clients_api.all()
        self.assertEqual(len(clients_all), 6 + 1)
        self.dest_client = find_in_list(clients_all, clientId=self.dest_client_clientId)

        # find src_client and their roles
        self.src_client_0 = find_in_list(clients_all, clientId=self.src_client_0_clientId)
        src_client_0_roles_api = self.clients_api.roles({'key': 'id', 'value': self.src_client_0["id"]})
        src_client_0_roles = src_client_0_roles_api.all()
        self.src_client_0_role_0 = find_in_list(src_client_0_roles, name="view-consent")
        self.src_client_0_role_1 = find_in_list(src_client_0_roles, name="view-profile")
        #
        self.src_client_1 = find_in_list(clients_all, clientId=self.src_client_1_clientId)
        src_client_1_roles_api = self.clients_api.roles({'key': 'id', 'value': self.src_client_1["id"]})
        src_client_1_roles = src_client_1_roles_api.all()
        self.src_client_1_role_0 = find_in_list(src_client_1_roles, name="read-token")

        # GET /{realm}/clients/{client_id}/scope-mappings/realm
        self.dest_client_scopeMappings = KeycloakCRUD.get_child(self.clients_api, self.dest_client["id"], f"scope-mappings")  # client and realm roles are included
        self.dest_client_scopeMappings_client_0_api = KeycloakCRUD.get_child(self.clients_api, self.dest_client["id"], f"scope-mappings/clients/{self.src_client_0['id']}")
        self.dest_client_scopeMappings_client_1_api = KeycloakCRUD.get_child(self.clients_api, self.dest_client["id"], f"scope-mappings/clients/{self.src_client_1['id']}")

    def test_publish(self):
        def _check_state():
            client_scopeMappings_client_b = dest_client_scopeMappings.all()
            self.assertEqual(client_scopeMappings_client_a['clientMappings']["broker"]["id"], client_scopeMappings_client_b['clientMappings']["broker"]["id"])
            self.assertEqual(client_scopeMappings_client_a, client_scopeMappings_client_b)
            client_scopeMappings_client_names = _get_assigned_client_roles_names()
            self.assertEqual(
                expected_client_scopeMappings_client_names,
                client_scopeMappings_client_names,
            )
            # -------------------------------------------

        def _get_assigned_client_roles_names():
            client_scopeMappings_client_x = dest_client_scopeMappings.all()
            client_scopeMappings_client_names = sorted([
                role["name"]
                for one_client_obj in client_scopeMappings_client_x['clientMappings'].values()
                for role in one_client_obj["mappings"]
            ])
            return client_scopeMappings_client_names

        dest_client_scopeMappings = self.dest_client_scopeMappings
        # requested_client_scopeMappings_client_names - needs to be computed
        # from ci0-realm/clients/client-0/scope-mappings.json
        requested_client_scopeMappings_client_names = ["read-token", "view-consent"]
        expected_client_scopeMappings_client_names = ["read-token", "view-consent"]

        # What we want is in file like test/data/kcfetcher-0.0.7/ci0-realm/clients/client-0/scope-mappings.json
        # But then it needs to be transformed into something closer to
        # test/data/kcfetcher-0.0.7/ci0-realm/client-scopes/ci0-client-scope.json, field clientScopeMappings
        # TODO - modify kcfetcher to output such format into ci0-realm/clients/client-0/scope-mappings.json.
        requested_doc = {
            "account": [
                "view-consent",
            ],
            "broker": [
                "read-token",
                # "no-such-role",
            ],
        }

        # check initial state
        self.assertEqual({}, dest_client_scopeMappings.all())

        # create/update
        manager = ClientScopeMappingsAllClientsManager(
            self.testbed.kc,
            self.testbed.REALM,
            self.testbed.DATADIR,
            requested_doc=requested_doc,
            client_id=self.dest_client["id"],
        )
        creation_state = manager.publish()
        self.assertTrue(creation_state)
        client_scopeMappings_client_a = dest_client_scopeMappings.all()
        _check_state()
        creation_state = manager.publish()
        self.assertFalse(creation_state)
        _check_state()

        # add one extra mapping, it needs to be removed
        client_scopeMappings_client_names = _get_assigned_client_roles_names()
        self.assertEqual(2, len(client_scopeMappings_client_names))
        self.dest_client_scopeMappings_client_0_api.create([self.src_client_0_role_1]).isOk()
        client_scopeMappings_client_names = _get_assigned_client_roles_names()
        self.assertEqual(3, len(client_scopeMappings_client_names))
        #
        creation_state = manager.publish()
        self.assertTrue(creation_state)
        _check_state()
        creation_state = manager.publish()
        self.assertFalse(creation_state)
        _check_state()
