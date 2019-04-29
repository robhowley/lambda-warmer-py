
import os
import json
import time
import boto3
import logging
import functools


warmer_logger = logging.getLogger(__name__)


LAMBDA_INFO = {
    'is_warm': False,
    'function_name': os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'FAILED_TO_RETRIEVE_LAMBDA_NAME')
}


def warmer(flag='warmer', concurrency='concurrency', delay=75, send_metric=False, **decorator_kwargs):

    config = dict(flag=flag, concurrency=concurrency, delay=delay, send_metric=send_metric)

    # should only really be used in unittests w fake client
    get_client = decorator_kwargs.pop('get_client', None) or boto3.client
    logger = decorator_kwargs.pop('logger', None)

    def decorator(f):
        @functools.wraps(f)
        def wrapped_func(event, context, *args, **kwargs):

            execution_info = dict(
                instance_id=context.aws_request_id,
                is_warmer_invocation=event.get(flag) or False,
                **LAMBDA_INFO
            )

            log_current_state(
                send_metric,
                cloudwatch_client=get_client('cloudwatch'),
                logger=logger,
                **execution_info
            )

            LAMBDA_INFO['is_warm'] = True

            if execution_info['is_warmer_invocation']:
                lambda_client = get_client('lambda')
                warmer_fan_out(event, config=config, lambda_client=lambda_client, logger=logger, **execution_info)
            else:
                return f(event, context, *args, **kwargs)

        return wrapped_func
    return decorator


def log_current_state(send_metric, logger=None, cloudwatch_client=None, **execution_info):
    logger = logger or warmer_logger
    logger.info(execution_info)

    if send_metric:
        cloudwatch_client = cloudwatch_client or boto3.client('cloudwatch')
        cloudwatch_client.put_metric_data(
            Namespace='LambdaWarmer',
            MetricData=[dict(
                MetricName='WarmStart' if execution_info['is_warm'] else 'ColdStart',
                Dimensions=[dict(Name='By Function Name', Value=execution_info['function_name'])],
                Unit='None',
                Value=1
            )]
        )


def warmer_fan_out(event, config=None, lambda_client=None, logger=None, **execution_info):

    logger = logger or warmer_logger

    concurrency = max(event.get(config['concurrency']) or 1, 1)
    invoke_count = event.get('__WARMER_INVOCATION__') or 1
    invoke_total = event.get('__WARMER_CONCURRENCY__') or concurrency
    correlation_id = event.get('__WARMER_CORRELATION_ID__') or execution_info['instance_id']

    logger.info(dict(
        action='warmer',
        correlation_id=correlation_id,
        count=invoke_count,
        concurrency=invoke_total,
        **execution_info
    ))

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
                FunctionName=LAMBDA_INFO['function_name'],
                InvocationType='Event' if i < concurrency - 1 else 'RequestResponse',
                Payload=json.dumps(dict(base_payload, __WARMER_INVOCATION__=(i + 1)))
            )
        except Exception as e:
            logger.info('Failed to invoke {} during warm up fan out'.format(LAMBDA_INFO['function_name']))
