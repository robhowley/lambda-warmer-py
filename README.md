[![PyPI version](https://badge.fury.io/py/lambda-warmer-py.svg)](https://badge.fury.io/py/lambda-warmer-py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# lambda-warmer-py: taking care of aws lambda cold starts
The `lambda-warmer-py` package contains a single decorator that makes it easy to minimize the drag of aws lambda cold 
starts. Just ...

  1. wrap your lambdas in the `@lambdawarmer.warmer` decorator and
  2. ping your lambda once every 5 minutes

and you'll cut your cold starts way down. 

Configuration options are also available that ...
* allow for keeping many *concurrent* lambdas warm
* sending [CloudWatch metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/working_with_metrics.html) 
  tracking the number of cold and warm starts by lambda function name 

The warming logic is a python adaption* of the `js` [package](https://github.com/jeremydaly/lambda-warmer), `lambda-warmer`. Read more about the background to this approach on his site [here](https://www.jeremydaly.com/lambda-warmer-optimize-aws-lambda-function-cold-starts/)
and some best practices on lambda optimization [here](https://www.jeremydaly.com/15-key-takeaways-from-the-serverless-talk-at-aws-startup-day/).

\* In addition to supporting CloudWatch Metrics, there are some small differences in parameterization. See [configuration](#configuration).
  

## Install

```bash
pip install lambda-warmer-py
```

## Using the lambda warmer

### The basics
Incorporating the lambda warmer into your existing lambdas only requires adding a single decorator.
```python
import lambdawarmer


@lambdawarmer.warmer()
def your_lambda_function(event, context):
    pass
```

### Concurrent warming
To leverage the concurrency options, the package will invoke your lambda multiple times. This means that the deployed
lambda will need the following permissions
```yaml
- Effect: Allow
  Action: lambda:InvokeFunction
  Resource: [your-lambdas-arn]
```

### Enabling ColdStart/WarmStart CloudWatch Metrics
In order for the lambda warmer to track cold and warm start metrics, the lambda execution role will need permissions
to send metric data to CloudWatch. The required policy action is 
```yaml
- Effect: Allow
  Action: cloudwatch:PutMetricData
```

## Warming your lambdas
Create a [CloudWatch Rule](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/RunLambdaSchedule.html) that 
periodically invokes your lambda directly and passes the following json as the event
```bash
{
    "warmer": true,
    "concurrency": (int, defaults to 1)
}
```
It is possible to change the `warmer` and `concurrency` names by overriding parameters in the `warmer` decorator. See
[configuration](#configuration) for details.

## Configuration
The lambda warmer is configured via the function parameters for the `@warmer` decorator. It takes the following ...

### `flag (string, default = 'warmer')`
Name of the field used to indicate that it is a warm up event.

### `concurrency (string, default = 'concurrency')`
Name of the field used to set the number of concurrent lambdas to invoke and keep warm.

### `delay (int, default = 75)`
Number of millis a concurrent warm up invocation should sleep. This helps avoid under delivering on
  the concurrency target.
  
### `send_metric (bool, default = False)`
Whether or not CloudWatch Metrics for the number of cold/warm starts will be sent at each invocation. The metrics names
are `ColdStart` and `WarmStart`, are recorded under `LambdaWarmer` namespace, and can be filtered by lambda function name.
  
#### Example of configuration overrides
Using alternative event and delay configurations is straightforward.
```bash
@lambdawarmer.warmer(flag='am_i_a_warmer', concurrency='how_many_lambdas', delay=150)
def your_lambda_function(event, context):
    pass
```
This implementation will expect events of the form
```bash
{"am_i_a_warmer": true, "how_many_lambdas": (int)}
```
and all concurrent executions will delay for 150 milliseconds.

*Note*: Configuration options that are *excluded* from this implementation but can be found in the `js` version are 
* `test`: Testing is handled in the unittests using mocks/fakes instead of flagged invocations
* `log`: Logging levels of imported python  packages should be handled via the stdlib `logging` module. 
* `correlationId`. This has been made into the snake cased `correlation_id` since we're in python and is always set to 
the current lambda's `aws_request_id` field as is recommended in the original `lambda-warmer` package.