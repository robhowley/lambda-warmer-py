[![PyPI version](https://badge.fury.io/py/lambda-warmer-py.svg)](https://badge.fury.io/py/lambda-warmer-py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# lambda-warmer-py: taking care of aws lambda cold starts
The `lambda-warmer-py` package contains a single decorator that makes it easy to minimize the drag of aws lambda cold 
starts. Just ...

  1. wrap your lambdas in the `@lambdawarmer.warmer` decorator and
  2. ping your lambda once every 5 minutes

and you'll cut your cold starts way down. Configuration options are also available that allow for keeping many *concurrent*
lambdas warm simultaneously.

This is a python adaption* of the `npm` [package](https://github.com/jeremydaly/lambda-warmer) `lambda-warmer` by 
Jeremy Daly. Read more about the background to this approach on his site [here](https://www.jeremydaly.com/lambda-warmer-optimize-aws-lambda-function-cold-starts/)
and some [best practices](https://www.jeremydaly.com/15-key-takeaways-from-the-serverless-talk-at-aws-startup-day/) on 
lambda optimization here.

\* There are definitely some differences. See [configuration](#configuration).
  

## Install

```bash
pip install lambda-warmer-py
```

## Using the lambda warmer
Incorporating the lambda warmer into your existing lambdas only requires adding a single decorator.
```python
import lambdawarmer


@lambdawarmer.warmer()
def your_lambda_function(event, context):
    pass
```

To leverage the concurrency options, the package will invoke your lambda multiple times. This means that the deployed
lambda will need the following permissions
```yaml
- Effect: Allow
  Action: lambda:InvokeFunction
  Resource: [your-lambdas-arn]
```

## Warming your lambdas
Create a [CloudWatch Rule](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/RunLambdaSchedule.html) that 
periodically invokes your lambda directly and passes the following json as the event
```bash
{
    "warmer": true,
    "concurrency": (int, defaults to 3)
}
```
It is possible to change the `warmer` and `concurrency` names by overriding parameters in the `warmer` decorator.

## Configuration
