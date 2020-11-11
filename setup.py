#!/usr/bin/env python3

import os
from setuptools import setup


this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='otvetmailru',
    version='0.1.2',
    description='otvet.mail.ru API wrapper',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kalinochkind/otvetmailru',
    author='Denis Kalinochkin',
    author_email='kalinochkind@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    keywords='otvet mail.ru',
    packages=['otvetmailru'],
    install_requires=[
        'requests',
        'dataclasses;python_version<"3.7"',
    ],
    python_requires=">=3.6",


)
