import json
import unittest
from lambdawarmer import warmer
from collections import namedtuple


class TestWarmerFanOut(unittest.TestCase):
    def setUp(self):
        from lambdawarmer import LAMBDA_INFO

        class FakeLogger(object):
            def __init__(self):
                self.kept_logs = []

            def info(self, s):
                self.kept_logs.append(s)

        class FakeLambdaClient(object):
            def __init__(self):
                self.calls = []

            def invoke(self, FunctionName, InvocationType, Payload=None):
                assert FunctionName is not None and InvocationType in ['Event', 'RequestResponse', 'DryRun']
                self.calls.append(dict(function_name=FunctionName, invoke_type=InvocationType, payload=Payload))

        self.get_fake_logger = FakeLogger
        self.get_fake_lambda_client = FakeLambdaClient
        self.get_context = lambda req_id='123': namedtuple('Context', 'aws_request_id')(req_id)

        self.warmer_invocation_event = dict(warmer=True, concurrency=3)

        self.to_invoke_call = lambda inv_num: {
            'function_name': 'FAILED_TO_RETRIEVE_LAMBDA_NAME',
            'invoke_type': 'RequestResponse',
            'payload': {
                '__WARMER_CORRELATION_ID__': '123',
                'warmer': True,
                '__WARMER_CONCURRENCY__': self.warmer_invocation_event['concurrency'],
                '__WARMER_INVOCATION__': inv_num
            }
        }

        self.lambda_client, self.logger = self.get_fake_lambda_client(), self.get_fake_logger()

        @warmer(lambda_client=self.lambda_client, logger=self.logger)
        def dummy_lambda(event, context):
            pass

        self.decorared_dummy_lambda = dummy_lambda

        LAMBDA_INFO['is_warm'] = False

    def test_warmer_fan_out(self):
        from lambdawarmer import LAMBDA_INFO

        self.assertFalse(LAMBDA_INFO['is_warm'])

        self.decorared_dummy_lambda(self.warmer_invocation_event, self.get_context())

        self.assertTrue(LAMBDA_INFO['is_warm'])

        self.assertDictEqual(
            self.logger.kept_logs[0],
            {
                'action': 'warmer',
                'concurrency': self.warmer_invocation_event['concurrency'],
                'correlation_id': '123',
                'count': 1,
                'function': 'FAILED_TO_RETRIEVE_LAMBDA_NAME',
                'instance_id': '123',
                'is_warm': False
            }
        )

        [c.update(payload=json.loads(c['payload'])) for c in self.lambda_client.calls]

        self.assertListEqual(
            self.lambda_client.calls,
            [self.to_invoke_call(2), self.to_invoke_call(3)]
        )

    def test_if_not_warmer_do_not_bother(self):
        self.decorared_dummy_lambda({}, self.get_context())
        self.assertTrue(len(self.logger.kept_logs) == 0)
        self.assertTrue(len(self.lambda_client.calls) == 0)

    def test_fan_out_call_does_not_fan_out_more(self):
        invoke_call = self.to_invoke_call(2)
        self.decorared_dummy_lambda(invoke_call['payload'], self.get_context())
        self.assertTrue(len(self.logger.kept_logs) == 1)
        self.assertTrue(len(self.lambda_client.calls) == 0)

    def test_event_key_renaming(self):
        from lambdawarmer import LAMBDA_INFO

        @warmer(warmer='not_w', concurrency='not_c', lambda_client=self.lambda_client, logger=self.logger)
        def dummy_lambda(event, context):
            pass

        self.assertFalse(LAMBDA_INFO['is_warm'])

        dummy_lambda(dict(not_w=True, not_c=2), self.get_context())

        self.assertTrue(LAMBDA_INFO['is_warm'])

        print(self.logger.kept_logs)


if __name__ == '__main__':
    unittest.main()
