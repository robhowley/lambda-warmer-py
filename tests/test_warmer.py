import json
import unittest
from lambdawarmer import warmer
from lambdawarmer.fakes import get_context, get_client


class TestWarmerFanOut(unittest.TestCase):
    def setUp(self):
        from lambdawarmer import LAMBDA_INFO
        from lambdawarmer.fakes import FakeLogger

        self.lambda_client, self.logger = get_client('lambda'), FakeLogger()

        self.warmer_invocation_event = dict(warmer=True, concurrency=3)

        self.to_invoke_call = lambda inv_num, inv_type='Event': {
            'function_name': 'FAILED_TO_RETRIEVE_LAMBDA_NAME',
            'invoke_type': inv_type,
            'payload': {
                '__WARMER_CORRELATION_ID__': '123',
                'warmer': True,
                '__WARMER_CONCURRENCY__': self.warmer_invocation_event['concurrency'],
                '__WARMER_INVOCATION__': inv_num
            }
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

        @warmer(get_client=get_client, logger=self.logger)
        def dummy_lambda(event, context):
            return self.lambda_return_value

        self.decorared_dummy_lambda = dummy_lambda

        LAMBDA_INFO['is_warm'] = False

    def test_warmer_fan_out(self):
        from lambdawarmer import LAMBDA_INFO

        self.assertFalse(LAMBDA_INFO['is_warm'])

        lambda_return_val = self.decorared_dummy_lambda(self.warmer_invocation_event, get_context())

        self.assertIsNone(lambda_return_val)
        self.assertTrue(LAMBDA_INFO['is_warm'])

        self.assertDictEqual(
            self.logger.kept_logs[1],
            {
                'action': 'warmer',
                'is_warmer_invocation': True,
                'concurrency': self.warmer_invocation_event['concurrency'],
                'correlation_id': '123',
                'count': 1,
                'function_name': 'FAILED_TO_RETRIEVE_LAMBDA_NAME',
                'instance_id': '123',
                'is_warm': False
            }
        )

        [c.update(payload=json.loads(c['payload'])) for c in self.lambda_client.calls]

        self.assertListEqual(
            self.lambda_client.calls,
            [self.to_invoke_call(2), self.to_invoke_call(3, inv_type='RequestResponse')]
        )

    def test_if_not_warmer_do_not_bother(self):
        lambda_return_val = self.decorared_dummy_lambda({}, get_context())
        self.assertEqual(lambda_return_val, self.lambda_return_value)
        self.assertTrue(len(self.logger.kept_logs) == 1)
        self.assertTrue(len(self.lambda_client.calls) == 0)

    def test_fan_out_call_does_not_fan_out_more(self):
        invoke_call = self.to_invoke_call(2)
        self.decorared_dummy_lambda(invoke_call['payload'], get_context())
        self.assertTrue(len(self.logger.kept_logs) == 2)
        self.assertTrue(len(self.lambda_client.calls) == 0)

    def test_event_key_renaming(self):
        from lambdawarmer import LAMBDA_INFO

        @warmer(warmer='not_w', concurrency='not_c', get_client=get_client, logger=self.logger)
        def dummy_lambda(event, context):
            pass

        self.assertFalse(LAMBDA_INFO['is_warm'])

        dummy_lambda(dict(not_w=True, not_c=2), get_context())

        self.assertTrue(LAMBDA_INFO['is_warm'])

    def test_logging_current_state(self):

        @warmer(send_metric=True, get_client=get_client, logger=self.logger)
        def dummy_lambda(event, context):
            pass

        fake_cw = get_client('cloudwatch')

        dummy_lambda({}, get_context())
        self.assertDictEqual(fake_cw.calls[0], self.to_metric('ColdStart'))
        self.assertFalse(self.logger.kept_logs[0]['is_warm'])

        dummy_lambda({}, get_context())
        self.assertDictEqual(fake_cw.calls[1], self.to_metric('WarmStart'))
        self.assertTrue(self.logger.kept_logs[1]['is_warm'])

        self.assertTrue(len(fake_cw.calls) == 2)


if __name__ == '__main__':
    unittest.main()
