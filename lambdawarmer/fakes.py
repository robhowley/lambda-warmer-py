
from collections import namedtuple


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


class FakeCloudwatchClient(object):
    def __init__(self):
        self.calls = []

    def put_metric_data(self, Namespace, MetricData, **kwargs):
        assert Namespace is not None and MetricData
        self.calls.append(dict(Namespace=Namespace, MetricData=MetricData, **kwargs))


_lambda_client, _cloudwatch_client = FakeLambdaClient(), FakeCloudwatchClient()


def get_client(s):
    return {'lambda': _lambda_client, 'cloudwatch': _cloudwatch_client}.get(s)


def get_context(req_id='123'):
    return namedtuple('Context', 'aws_request_id')(req_id)
