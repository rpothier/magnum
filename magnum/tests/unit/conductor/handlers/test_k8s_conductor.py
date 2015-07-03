# Copyright 2014 NEC Corporation.  All rights reserved.
#
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

from oslo_config import cfg

from magnum.common import exception
from magnum.conductor.handlers import k8s_conductor
from magnum import objects
from magnum.tests import base

import mock
from mock import patch
from six.moves.urllib import error


cfg.CONF.import_opt('k8s_protocol', 'magnum.conductor.handlers.k8s_conductor',
                    group='kubernetes')
cfg.CONF.import_opt('k8s_port', 'magnum.conductor.handlers.k8s_conductor',
                    group='kubernetes')


class TestK8sConductor(base.TestCase):
    def setUp(self):
        super(TestK8sConductor, self).setUp()
        self.kube_handler = k8s_conductor.Handler()

    def mock_pod(self):
        return objects.Pod({})

    def mock_service(self):
        return objects.Service({})

    def mock_rc(self):
        return objects.ReplicationController({})

    def mock_bay(self):
        return objects.Bay({})

    def mock_baymodel(self):
        return objects.BayModel({})

    def test_pod_create_with_success(self):
        expected_pod = self.mock_pod()
        expected_pod.create = mock.MagicMock()
        expected_pod.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            return_value = mock.MagicMock()
            return_value.status = mock.MagicMock()
            return_value.status.phase = 'Pending'
            return_value.spec = mock.MagicMock()
            return_value.spec.host = '10.0.0.3'
            mock_kube_api.return_value.createPod.return_value = return_value

            self.kube_handler.pod_create(self.context, expected_pod)
            self.assertEqual('Pending', expected_pod.status)
            self.assertEqual('10.0.0.3', expected_pod.host)
            expected_pod.create.assert_called_once_with(self.context)

    @patch('ast.literal_eval')
    def test_pod_create_with_fail(self, mock_literal_eval):
        expected_pod = self.mock_pod()
        expected_pod.create = mock.MagicMock()
        expected_pod.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=500)
            mock_kube_api.return_value.createPod.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed, self.kube_handler.
                              pod_create, self.context, expected_pod)
            self.assertEqual('failed', expected_pod.status)
            expected_pod.create.assert_called_once_with(self.context)

    @patch('ast.literal_eval')
    def test_pod_create_fail_on_existing_pod(
            self, mock_literal_eval):
        expected_pod = self.mock_pod()
        expected_pod.create = mock.MagicMock()
        expected_pod.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=409)
            mock_kube_api.return_value.createPod.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed, self.kube_handler.
                              pod_create, self.context, expected_pod)
            self.assertEqual('failed', expected_pod.status)
            self.assertFalse(expected_pod.create.called)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.Pod.get_by_uuid')
    def test_pod_delete_with_success(self,
                                     mock_pod_get_by_uuid,
                                     mock_object_has_stack):
        mock_pod = mock.MagicMock()
        mock_pod.name = 'test-pod'
        mock_pod.uuid = 'test-uuid'
        mock_pod_get_by_uuid.return_value = mock_pod

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.pod_delete(self.context, mock_pod.uuid)

            mock_kube_api.return_value.deletePod.assert_called_once_with(
                name=mock_pod.name,
                namespaces='default')
            mock_pod.destroy.assert_called_once_with(self.context)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.Pod.get_by_uuid')
    @patch('ast.literal_eval')
    def test_pod_delete_with_failure(self, mock_literal_eval,
                                     mock_pod_get_by_uuid,
                                     mock_object_has_stack):
        mock_pod = mock.MagicMock()
        mock_pod.name = 'test-pod'
        mock_pod.uuid = 'test-uuid'
        mock_pod_get_by_uuid.return_value = mock_pod

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=500)
            mock_kube_api.return_value.deletePod.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.pod_delete,
                              self.context, mock_pod.uuid)
            mock_kube_api.return_value.deletePod.assert_called_once_with(
                name=mock_pod.name,
                namespaces='default')
            self.assertFalse(mock_pod.destroy.called)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.Pod.get_by_uuid')
    @patch('ast.literal_eval')
    def test_pod_delete_succeeds_when_not_found(
            self, mock_literal_eval,
            mock_pod_get_by_uuid,
            mock_object_has_stack):
        mock_pod = mock.MagicMock()
        mock_pod.name = 'test-pod'
        mock_pod.uuid = 'test-uuid'
        mock_pod_get_by_uuid.return_value = mock_pod

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=404)
            mock_kube_api.return_value.deletePod.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.kube_handler.pod_delete(self.context, mock_pod.uuid)

            mock_kube_api.return_value.deletePod.assert_called_once_with(
                name=mock_pod.name, namespaces='default')
            mock_pod.destroy.assert_called_once_with(self.context)

    def test_service_create_with_success(self):
        expected_service = self.mock_service()
        expected_service.create = mock.MagicMock()
        manifest = {"key": "value"}
        expected_service.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.service_create(self.context, expected_service)
            mock_kube_api.return_value.createService.assert_called_once_with(
                body=manifest, namespaces='default')
            expected_service.create.assert_called_once_with(self.context)

    @patch('ast.literal_eval')
    def test_service_create_with_failure(self, mock_literal_eval):
        expected_service = self.mock_service()
        expected_service.create = mock.MagicMock()
        manifest = {"key": "value"}
        expected_service.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=404)
            mock_kube_api.return_value.createService.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.service_create,
                              self.context, expected_service)
            mock_kube_api.return_value.createService.assert_called_once_with(
                body=manifest, namespaces='default')
            self.assertFalse(expected_service.create.called)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.Service.get_by_uuid')
    def test_service_delete_with_success(
            self,
            mock_service_get_by_uuid,
            mock_object_has_stack):
        mock_service = mock.MagicMock()
        mock_service.name = 'test-service'
        mock_service.uuid = 'test-uuid'
        mock_service_get_by_uuid.return_value = mock_service

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.service_delete(self.context, mock_service.uuid)

            mock_kube_api.return_value.deleteService.assert_called_once_with(
                name=mock_service.name, namespaces='default')
            mock_service.destroy.assert_called_once_with(self.context)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.Service.get_by_uuid')
    @patch('ast.literal_eval')
    def test_service_delete_with_failure(
            self, mock_literal_eval,
            mock_service_get_by_uuid,
            mock_object_has_stack):
        mock_service = mock.MagicMock()
        mock_service.name = 'test-service'
        mock_service.uuid = 'test-uuid'
        mock_service_get_by_uuid.return_value = mock_service

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=500)
            mock_kube_api.return_value.deleteService.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.service_delete,
                              self.context, mock_service.uuid)

            mock_kube_api.return_value.deleteService.assert_called_once_with(
                name=mock_service.name, namespaces='default')
            self.assertFalse(mock_service.destroy.called)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.Service.get_by_uuid')
    @patch('ast.literal_eval')
    def test_service_delete_succeeds_when_not_found(
            self, mock_literal_eval,
            mock_service_get_by_uuid,
            mock_object_has_stack):
        mock_service = mock.MagicMock()
        mock_service.name = 'test-service'
        mock_service.uuid = 'test-uuid'
        mock_service_get_by_uuid.return_value = mock_service

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=404)
            mock_kube_api.return_value.deleteService.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.kube_handler.service_delete(self.context, mock_service.uuid)

            mock_kube_api.return_value.deleteService.assert_called_once_with(
                name=mock_service.name, namespaces='default')
            mock_service.destroy.assert_called_once_with(self.context)

    def test_rc_create_with_success(self):
        expected_rc = self.mock_rc()
        expected_rc.create = mock.MagicMock()
        manifest = {"key": "value"}
        expected_rc.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.rc_create({}, expected_rc)
            (mock_kube_api.return_value.createReplicationController
                .assert_called_once_with(body=manifest, namespaces='default'))

    @patch('ast.literal_eval')
    def test_rc_create_with_failure(self, mock_literal_eval):
        expected_rc = self.mock_rc()
        expected_rc.create = mock.MagicMock()
        manifest = {"key": "value"}
        expected_rc.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=500)
            (mock_kube_api.return_value.createReplicationController.side_effect
             ) = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.rc_create,
                              self.context, expected_rc)
            (mock_kube_api.return_value.createReplicationController
                .assert_called_once_with(body=manifest, namespaces='default'))
            self.assertFalse(expected_rc.create.called)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.ReplicationController.get_by_uuid')
    def test_rc_delete_with_success(self,
                                    mock_rc_get_by_uuid,
                                    mock_object_has_stack):
        mock_rc = mock.MagicMock()
        mock_rc.name = 'test-rc'
        mock_rc.uuid = 'test-uuid'
        mock_rc_get_by_uuid.return_value = mock_rc

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.rc_delete(self.context, mock_rc.uuid)

            (mock_kube_api.return_value.deleteReplicationController
                .assert_called_once_with(name=mock_rc.name,
                                         namespaces='default'))
            mock_rc.destroy.assert_called_once_with(self.context)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.ReplicationController.get_by_uuid')
    @patch('ast.literal_eval')
    def test_rc_delete_with_failure(self, mock_literal_eval,
                                    mock_rc_get_by_uuid,
                                    mock_object_has_stack):
        mock_rc = mock.MagicMock()
        mock_rc.name = 'test-rc'
        mock_rc.uuid = 'test-uuid'
        mock_rc_get_by_uuid.return_value = mock_rc

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=500)
            (mock_kube_api.return_value.deleteReplicationController.side_effect
             ) = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.rc_delete,
                              self.context, mock_rc.uuid)

            (mock_kube_api.return_value.deleteReplicationController
                .assert_called_once_with(name=mock_rc.name,
                                         namespaces='default'))
            self.assertFalse(mock_rc.destroy.called)

    @patch('magnum.conductor.utils.object_has_stack')
    @patch('magnum.objects.ReplicationController.get_by_uuid')
    @patch('ast.literal_eval')
    def test_rc_delete_succeeds_when_not_found(
            self, mock_literal_eval,
            mock_rc_get_by_uuid,
            mock_object_has_stack):
        mock_rc = mock.MagicMock()
        mock_rc.name = 'test-rc'
        mock_rc.uuid = 'test-uuid'
        mock_rc_get_by_uuid.return_value = mock_rc

        mock_object_has_stack.return_value = True
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=404)
            (mock_kube_api.return_value.deleteReplicationController.side_effect
             ) = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.kube_handler.rc_delete(self.context, mock_rc.uuid)

            (mock_kube_api.return_value.deleteReplicationController
                .assert_called_once_with(name=mock_rc.name,
                                         namespaces='default'))
            self.assertTrue(mock_rc.destroy.called)

    def test_rc_update_with_success(self):
        expected_rc = self.mock_rc()
        expected_rc.uuid = 'test-uuid'
        expected_rc.name = 'test-name'
        expected_rc.refresh = mock.MagicMock()
        expected_rc.save = mock.MagicMock()
        manifest = {"key": "value"}
        expected_rc.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.rc_update(self.context, expected_rc)
            (mock_kube_api.return_value.replaceReplicationController
                .assert_called_once_with(body=manifest, name=expected_rc.name,
                                         namespaces='default'))
            expected_rc.refresh.assert_called_once_with(self.context)
            expected_rc.save.assert_called_once_with()

    @patch('ast.literal_eval')
    def test_rc_update_with_failure(self, mock_literal_eval):
        expected_rc = self.mock_rc()
        expected_rc.uuid = 'test-uuid'
        expected_rc.name = 'test-name'
        expected_rc.update = mock.MagicMock()
        manifest = {"key": "value"}
        expected_rc.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=404)
            (mock_kube_api.return_value.replaceReplicationController
                .side_effect) = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.rc_update,
                              self.context, expected_rc)
            (mock_kube_api.return_value.replaceReplicationController
                .assert_called_once_with(body=manifest, name=expected_rc.name,
                                         namespaces='default'))
            self.assertFalse(expected_rc.update.called)

    def test_service_update_with_success(self):
        expected_service = self.mock_service()
        expected_service.uuid = 'test-uuid'
        expected_service.name = 'test-name'
        expected_service.refresh = mock.MagicMock()
        expected_service.save = mock.MagicMock()
        manifest = {"key": "value"}
        expected_service.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.service_update(self.context, expected_service)
            mock_kube_api.return_value.replaceService.assert_called_once_with(
                body=manifest, name=expected_service.name,
                namespaces='default')
            expected_service.refresh.assert_called_once_with(self.context)
            expected_service.save.assert_called_once_with()

    @patch('ast.literal_eval')
    def test_service_update_with_failure(self, mock_literal_eval):
        expected_service = self.mock_service()
        expected_service.uuid = 'test-uuid'
        expected_service.name = 'test-name'
        expected_service.refresh = mock.MagicMock()
        manifest = {"key": "value"}
        expected_service.manifest = '{"key": "value"}'
        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=404)
            mock_kube_api.return_value.replaceService.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.service_update,
                              self.context, expected_service)
            mock_kube_api.return_value.replaceService.assert_called_once_with(
                body=manifest, name=expected_service.name,
                namespaces='default')
            self.assertFalse(expected_service.refresh.called)

    def test_pod_update_with_success(self):
        expected_pod = self.mock_pod()
        expected_pod.uuid = 'test-uuid'
        expected_pod.name = 'test-name'
        expected_pod.refresh = mock.MagicMock()
        expected_pod.save = mock.MagicMock()
        manifest = {"key": "value"}
        expected_pod.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            self.kube_handler.pod_update(self.context, expected_pod)
            mock_kube_api.return_value.replacePod.assert_called_once_with(
                body=manifest, name=expected_pod.name,
                namespaces='default')
            expected_pod.refresh.assert_called_once_with(self.context)
            expected_pod.save.assert_called_once_with()

    @patch('ast.literal_eval')
    def test_pod_update_with_failure(self, mock_literal_eval):
        expected_pod = self.mock_pod()
        expected_pod.uuid = 'test-uuid'
        expected_pod.name = 'test-name'
        expected_pod.refresh = mock.MagicMock()
        manifest = {"key": "value"}
        expected_pod.manifest = '{"key": "value"}'

        with patch('magnum.conductor.k8s_api.create_k8s_api') as mock_kube_api:
            err = error.HTTPError(url='fake', msg='fake', hdrs='fake',
                                  fp=mock.MagicMock(), code=404)
            mock_kube_api.return_value.replacePod.side_effect = err
            mock_literal_eval.return_value = {'message': 'error'}

            self.assertRaises(exception.KubernetesAPIFailed,
                              self.kube_handler.pod_update,
                              self.context, expected_pod)
            mock_kube_api.return_value.replacePod.assert_called_once_with(
                body=manifest, name=expected_pod.name,
                namespaces='default')
            self.assertFalse(expected_pod.refresh.called)