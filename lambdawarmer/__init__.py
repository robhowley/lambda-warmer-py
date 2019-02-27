
import os
import json
import time
import boto3
import logging
import functools
from concurrent.futures import ThreadPoolExecutor


LAMBDA_INFO = {
    'is_warm': False,
    'name': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'FAILED_TO_RETRIEVE_LAMBDA_NAME')
}


def warmer(flag='warmer', concurrency='concurrency', **decorator_kwargs):

    # should only really be used in unittests w fake client
    lambda_client = decorator_kwargs.pop('lambda_client', None)
    logger = decorator_kwargs.pop('logger', None)

    def decorator(f):
        @functools.wraps(f)
        def wrapped_func(event, context, *args, **kwargs):

            config = dict(
                flag=flag,                              # default event key for flag indicating a warmer invocation
                concurrency=concurrency,                # default event key for flag indicating a test invocation
                test='test',                            # default event key for concurrency setting
                correlation_id=context.aws_request_id,  # default the shared id to the request id of source lamdba
                delay=75                                # default the delay to 75ms
            )

            warmer_fan_out(event, config=config, lambda_client=lambda_client, logger=logger)

            return f(event, context, *args, **kwargs)
        return wrapped_func
    return decorator


def warmer_fan_out(event, config=None, lambda_client=None, logger=None):

    logger = logger or logging.getLogger(__name__)

    state_at_invocation = LAMBDA_INFO['is_warm']
    LAMBDA_INFO['is_warm'] = True

    if event.get(config['flag']):
        concurrency = max(event.get(config['concurrency']), 1)
        invoke_count = event.get('__WARMER_INVOCATION__') or 1
        invoke_total = event.get('__WARMER_CONCURRENCY__') or concurrency
        correlation_id = event.get('__WARMER_CORRELATION_ID__') or config['correlation_id']

        logger.info(dict(
            action='warmer',
            function=LAMBDA_INFO['name'],
            instance_id=config['correlation_id'],
            correlation_id=correlation_id,
            count=invoke_count,
            concurrency=invoke_total,
            is_warm=state_at_invocation
        ))

        LAMBDA_INFO['is_warm'] = True

        if concurrency > 1:
            _perform_fan_out_warm_up_calls(config, correlation_id, concurrency, lambda_client)
        elif invoke_count > 1:
            time.sleep(config['delay'] / 1000.0)        # without delay, you might just get a reused container


def _perform_fan_out_warm_up_calls(config, correlation_id, concurrency, lambda_client):
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        lambda_client = lambda_client or boto3.client('lambda')

        def invoke_lambda(parameter_tuple):
            lambda_client, function_name, payload = parameter_tuple
            lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )

        base_payload = {
            config['flag']: True,
            '__WARMER_CONCURRENCY__': concurrency,
            '__WARMER_CORRELATION_ID__': correlation_id
        }

        param_iterables = [
            (lambda_client, LAMBDA_INFO['name'], dict(base_payload, __WARMER_INVOCATION__=(i + 1)))
            for i in range(1, concurrency)
        ]

        executor.map(invoke_lambda, param_iterables)
