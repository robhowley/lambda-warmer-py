
import os
import json
import time
import boto3
import logging
import functools


LAMBDA_INFO = {
    'is_warm': False,
    'name': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'FAILED_TO_RETRIEVE_LAMBDA_NAME')
}


def warmer(flag='warmer', concurrency='concurrency', delay=75, **decorator_kwargs):

    # should only really be used in unittests w fake client
    lambda_client = decorator_kwargs.pop('lambda_client', None)
    logger = decorator_kwargs.pop('logger', None)

    def decorator(f):
        @functools.wraps(f)
        def wrapped_func(event, context, *args, **kwargs):

            config = dict(
                flag=flag,                              # default event key for flag indicating a warmer invocation
                concurrency=concurrency,                # default event key for concurrency settings
                delay=delay,                            # default the delay to 75ms
                correlation_id=context.aws_request_id   # default the shared id to the request id of source lamdba
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
            _perform_fan_out_warm_up_calls(config, correlation_id, concurrency, lambda_client, logger)
        elif invoke_count > 1:
            time.sleep(config['delay'] / 1000.0)        # without delay, you might just get a reused container


def _perform_fan_out_warm_up_calls(config, correlation_id, concurrency, lambda_client, logger):
    lambda_client = lambda_client or boto3.client('lambda')

    base_payload = {
        config['flag']: True,
        '__WARMER_CONCURRENCY__': concurrency,
        '__WARMER_CORRELATION_ID__': correlation_id
    }

    for i in range(1, concurrency):
        try:
            lambda_client.invoke(
                FunctionName=LAMBDA_INFO['name'],
                InvocationType='Event' if i < concurrency - 1 else 'RequestResponse',
                Payload=json.dumps(dict(base_payload, __WARMER_INVOCATION__=(i + 1)))
            )
        except Exception as e:
            logger.info('Failed to invoke {} during warm up fan out'.format(LAMBDA_INFO['name']))
