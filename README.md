[![PyPI version](https://badge.fury.io/py/lambda-warmer-py.svg)](https://badge.fury.io/py/lambda-warmer-py)

# lambda-warmer-py: taking care of aws lambda cold starts 
This is a python adaption of the excellent `npm` package `lambda-warmer` by Jeremy Daly.
  

## Install

```bash
pip install lambda-warmer-py
```

## Wiring up your lambda

```python
import lambdawarmer


@lambdawarmer.warmer()
def your_lambda_function(event, context):
    pass
```