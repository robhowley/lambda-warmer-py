import json
import logging
import unittest
from unittest.mock import MagicMock, patch, call

from lambdawarmer import warmer


patch_boto = patch('lambdawarmer.boto3_client')
patch_info_logger = patch.object(logging.getLogger('lambdawarmer'), 'info')
inject_mocks = lambda f: patch_boto(patch_info_logger(f))


class TestWarmerFanOut(unittest.TestCase):
    def get_mock_context(self, req_id='123'):
        return MagicMock(aws_request_id=req_id)

    def setUp(self):
        from lambdawarmer import LAMBDA_INFO

        LAMBDA_INFO['is_warm'] = False

        self.warmer_invocation_event = dict(warmer=True, concurrency=3)

        self.to_invoke_call = lambda inv_num, inv_type='Event': {
            'FunctionName': 'FAILED_TO_RETRIEVE_LAMBDA_NAME:FAILED_TO_RETRIEVE_LAMBDA_VERSION',
            'InvocationType': inv_type,
            'Payload': json.dumps({
                '__WARMER_CORRELATION_ID__': '123',
                'warmer': True,
                '__WARMER_CONCURRENCY__': self.warmer_invocation_event['concurrency'],
                '__WARMER_INVOCATION__': inv_num
            }, sort_keys=True)
        }

        self.to_metric = lambda metric_name: dict(
            Namespace='LambdaWarmer',
            MetricData=[dict(
                MetricName=metric_name,
                Dimensions=[dict(Name='By Function Name', Value='FAILED_TO_RETRIEVE_LAMBDA_NAME')],
                Unit='None',
                Value=1
            )]
        )

        self.lambda_return_value = 'return-val'

        def _get_decorated_lambda(return_value=self.lambda_return_value, **warmer_kwargs):
            @warmer(**warmer_kwargs)
            def dummy_lambda(event, context):
                return return_value

            return dummy_lambda

        self.get_decorated_lambda = _get_decorated_lambda

    @inject_mocks
    def run_default_warmer_usage_tests(self, decorated_lambda, mock_logger, mock_boto3_client):
        from lambdawarmer import LAMBDA_INFO

        lambda_client = MagicMock()
        mock_boto3_client.return_value = lambda_client

        self.assertFalse(LAMBDA_INFO['is_warm'])

        lambda_return_val = decorated_lambda(self.warmer_invocation_event, self.get_mock_context())

        self.assertListEqual(mock_boto3_client.call_args_list, 2 * [call('lambda')])

        self.assertIsNone(lambda_return_val)
        self.assertTrue(LAMBDA_INFO['is_warm'])

        self.assertEqual(
            mock_logger.call_args_list[1],
            call({
                'action': 'warmer',
                'is_warmer_invocation': True,
                'concurrency': self.warmer_invocation_event['concurrency'],
                'correlation_id': '123',
                'count': 1,
                'function_name': 'FAILED_TO_RETRIEVE_LAMBDA_NAME',
                'function_version': 'FAILED_TO_RETRIEVE_LAMBDA_VERSION',
                'instance_id': '123',
                'is_warm': False
            })
        )

        self.assertEqual(
            lambda_client.invoke.call_args_list,
            [call(**self.to_invoke_call(2)), call(**self.to_invoke_call(3, inv_type='RequestResponse'))]
        )

    def test_warmer_fan_out(self):
        self.run_default_warmer_usage_tests(self.get_decorated_lambda())

    def test_no_parens_decorator(self):
        @warmer
        def dummy_lambda(event, context):
            return return_value

        self.run_default_warmer_usage_tests(dummy_lambda)

    @inject_mocks
    def test_if_not_warmer_do_not_bother(self, mock_logger, mock_boto3_client):
        lambda_return_val = self.get_decorated_lambda()({}, self.get_mock_context())
        self.assertEqual(lambda_return_val, self.lambda_return_value)
        self.assertTrue(len(mock_logger.call_args_list) == 1)
        mock_boto3_client.assert_not_called()

    @inject_mocks
    def test_fan_out_call_does_not_fan_out_more(self, mock_logger, mock_boto3_client):
        invoke_call = self.to_invoke_call(2)
        self.get_decorated_lambda()(json.loads(invoke_call['Payload']), self.get_mock_context())
        self.assertTrue(len(mock_logger.call_args_list) == 2)
        mock_boto3_client.assert_not_called()

    @inject_mocks
    def test_event_key_renaming(self, *args):
        from lambdawarmer import LAMBDA_INFO

        self.assertFalse(LAMBDA_INFO['is_warm'])

        decorated_lambda = self.get_decorated_lambda(flag='not_w', concurrency='not_c')

        with patch('lambdawarmer.warmer_fan_out') as mock_warmer_fan_out:
            decorated_lambda(dict(not_w=True, not_c=2), self.get_mock_context())
            self.assertTrue(len(mock_warmer_fan_out.call_args_list) == 1)

        self.assertTrue(LAMBDA_INFO['is_warm'])

    @inject_mocks
    def test_logging_current_state(self, mock_logger, mock_boto3_client):

        decorated_lambda = self.get_decorated_lambda(send_metric=True)

        mock_cloudwatch_client = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch_client

        decorated_lambda({}, self.get_mock_context())

        mock_boto3_client.assert_called_once_with('cloudwatch')
        mock_cloudwatch_client.put_metric_data.assert_called_once_with(**self.to_metric('ColdStart'))
        self.assertFalse(mock_logger.call_args_list[0][0][0]['is_warm'])

        decorated_lambda({}, self.get_mock_context())
        self.assertEqual(
            mock_cloudwatch_client.put_metric_data.call_args_list[1],
            call(**self.to_metric('WarmStart'))
        )
        self.assertTrue(mock_logger.call_args_list[1][0][0]['is_warm'])

        self.assertTrue(len(mock_logger.call_args_list) == 2)


if __name__ == '__main__':
    unittest.main()
