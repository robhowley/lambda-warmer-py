import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='lambda-warmer-py',
    version='1.0.0',
    author='Rob Howley',
    author_email='howley.robert@gmail.com',
    description='keep lambdas warm and monitor cold starts with a simple decorator',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/pypa/sampleproject',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 2',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],

    install_requires={
        ":python_version == '2.7'": ['futures']
    }
)
