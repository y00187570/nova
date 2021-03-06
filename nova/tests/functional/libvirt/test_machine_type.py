# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import fixtures

from oslo_utils.fixture import uuidsentinel

from nova import context as nova_context
from nova import objects
from nova.tests.functional.libvirt import base


class LibvirtMachineTypeTest(base.ServersTestBase):

    microversion = 'latest'

    def setUp(self):
        super().setUp()
        self.context = nova_context.get_admin_context()

        # Add the q35 image to the glance fixture
        hw_machine_type_q35_image = copy.deepcopy(self.glance.image1)
        hw_machine_type_q35_image['id'] = uuidsentinel.q35_image_id
        hw_machine_type_q35_image['properties']['hw_machine_type'] = 'q35'
        self.glance.create(self.context, hw_machine_type_q35_image)

        # Create a pass-through mock around _get_guest_config to capture the
        # config of an instance so we can assert things about it later.
        # TODO(lyarwood): This seems like a useful thing to do in the libvirt
        # func tests for all computes we start?
        self.start_compute()
        self.guest_configs = {}
        orig_get_config = self.computes['compute1'].driver._get_guest_config

        def _get_guest_config(_self, *args, **kwargs):
            guest_config = orig_get_config(*args, **kwargs)
            instance = args[0]
            self.guest_configs[instance.uuid] = guest_config
            return self.guest_configs[instance.uuid]

        self.useFixture(fixtures.MonkeyPatch(
            'nova.virt.libvirt.LibvirtDriver._get_guest_config',
            _get_guest_config))

    def _create_servers(self):
        server_with = self._create_server(
            image_uuid=uuidsentinel.q35_image_id,
            networks='none',
        )
        server_without = self._create_server(
            image_uuid=self.glance.image1['id'],
            networks='none',
        )
        return (server_with, server_without)

    def _assert_machine_type(self, server_id, expected_machine_type):
        instance = objects.Instance.get_by_uuid(self.context, server_id)
        self.assertEqual(
            expected_machine_type,
            instance.image_meta.properties.hw_machine_type
        )
        self.assertEqual(
            expected_machine_type,
            instance.system_metadata['image_hw_machine_type']
        )
        self.assertEqual(
            expected_machine_type,
            self.guest_configs[server_id].os_mach_type
        )

    def test_init_host_register_machine_type(self):
        """Assert that the machine type of an instance is recorded during
           init_host if not already captured by an image prop.
        """
        self.flags(hw_machine_type='x86_64=pc', group='libvirt')

        server_with, server_without = self._create_servers()
        self._assert_machine_type(server_with['id'], 'q35')
        self._assert_machine_type(server_without['id'], 'pc')

        # Stop n-cpu and clear the recorded machine type from server_without to
        # allow init_host to register the machine type.
        self.computes['compute1'].stop()
        instance_without = objects.Instance.get_by_uuid(
            self.context,
            server_without['id'],
        )
        instance_without.system_metadata.pop('image_hw_machine_type')
        instance_without.save()

        self.flags(hw_machine_type='x86_64=pc-q35-1.2.3', group='libvirt')

        # Restart the compute
        self.computes['compute1'].start()

        # Assert the server_with remains pinned to q35
        self._assert_machine_type(server_with['id'], 'q35')

        # reboot the server so the config is rebuilt and _assert_machine_type
        # is able to pass. This just keeps the tests clean.
        self._reboot_server(server_without, hard=True)

        # Assert server_without now has a machine type of pc-q35-1.2.3 picked
        # up from [libvirt]hw_machine_type during init_host
        self._assert_machine_type(server_without['id'], 'pc-q35-1.2.3')

    def test_machine_type_after_config_change(self):
        """Assert new instances pick up a new default machine type after the
           config has been updated.
        """
        self.flags(hw_machine_type='x86_64=pc', group='libvirt')

        server_with, server_without = self._create_servers()
        self._assert_machine_type(server_with['id'], 'q35')
        self._assert_machine_type(server_without['id'], 'pc')

        self.flags(hw_machine_type='x86_64=pc-q35-1.2.3', group='libvirt')

        server_with_new, server_without_new = self._create_servers()
        self._assert_machine_type(server_with_new['id'], 'q35')
        self._assert_machine_type(server_without_new['id'], 'pc-q35-1.2.3')

    def test_machine_type_after_server_rebuild(self):
        """Assert that the machine type of an instance changes with a full
           rebuild of the instance pointing at a new image.
        """
        self.flags(hw_machine_type='x86_64=pc', group='libvirt')

        server_with, server_without = self._create_servers()
        self._assert_machine_type(server_with['id'], 'q35')
        self._assert_machine_type(server_without['id'], 'pc')

        # rebuild each server with the opposite image
        self._rebuild_server(
            server_with,
            '155d900f-4e14-4e4c-a73d-069cbf4541e6',
        )
        self._rebuild_server(
            server_without,
            uuidsentinel.q35_image_id
        )

        # Assert that the machine types were updated during the rebuild
        self._assert_machine_type(server_with['id'], 'pc')
        self._assert_machine_type(server_without['id'], 'q35')

    def _test_machine_type_after_server_reboot(self, hard=False):
        """Assert that the recorded machine types don't change with the
           reboot of a server, even when the underlying config changes.
        """
        self.flags(hw_machine_type='x86_64=pc', group='libvirt')

        server_with, server_without = self._create_servers()
        self._assert_machine_type(server_with['id'], 'q35')
        self._assert_machine_type(server_without['id'], 'pc')

        self.flags(hw_machine_type='x86_64=pc-q35-1.2.3', group='libvirt')

        self._reboot_server(server_with, hard=hard)
        self._reboot_server(server_without, hard=hard)

        # Assert that the machine types don't change after a reboot
        self._assert_machine_type(server_with['id'], 'q35')
        self._assert_machine_type(server_without['id'], 'pc')

    def test_machine_type_after_server_soft_reboot(self):
        self._test_machine_type_after_server_reboot()

    def test_machine_type_after_server_hard_reboot(self):
        self._test_machine_type_after_server_reboot(hard=True)
