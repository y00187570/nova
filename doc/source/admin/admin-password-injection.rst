====================================
Injecting the administrator password
====================================

Compute can generate a random administrator (root) password and inject that
password into an instance. If this feature is enabled, users can run
:command:`ssh` to an instance without an :command:`ssh` keypair.  The random
password appears in the output of the :command:`openstack server create`
command.  You can also view and set the admin password from the dashboard.

.. rubric:: Password injection using the dashboard

For password injection display in the dashboard, please refer to the setting of
``can_set_password`` in :horizon-doc:`Horizon doc
</configuration/settings.html#openstack-hypervisor-features>`

.. rubric:: Password injection on libvirt-based hypervisors

For hypervisors that use the libvirt back end (such as KVM, QEMU, and LXC),
admin password injection is disabled by default. To enable it, set this option
in ``/etc/nova/nova.conf``:

.. code-block:: ini

   [libvirt]
   inject_password=true

When enabled, Compute will modify the password of the admin account by editing
the ``/etc/shadow`` file inside the virtual machine instance.

.. note::

   Linux distribution guest only.

.. note::

   Users can only use :command:`ssh` to access the instance by using the admin
   password if the virtual machine image is a Linux distribution, and it has
   been configured to allow users to use :command:`ssh` as the root user with
   password authorization. This is not the case for
   `Ubuntu cloud images <http://uec-images.ubuntu.com>`_
   which, by default, does not allow users to use :command:`ssh` to access the
   root account, or
   `CentOS cloud images <http://cloud.centos.org/centos/>`_ which, by default,
   does not allow :command:`ssh` access to the instance with password.

.. rubric:: Password injection and Windows images (all hypervisors)

For Windows virtual machines, configure the Windows image to retrieve the admin
password on boot by installing an agent such as `cloudbase-init
<https://cloudbase.it/cloudbase-init>`_.
