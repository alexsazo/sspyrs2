from setuptools import setup

setup(name='sspyrs2',
      version='1.0',
      description='Alternative version of sspyrs that is a lightweight interface for SSRS reports to python.',
      long_description=open('README.rst').read(),
      url='https://pypi.python.org/pypi/sspyrs2',
      author='Alex Sazo',
      author_email='alexsazo@outlook.com',
      license='MIT',
      packages=['sspyrs2'],
      install_requires=[
           'pandas>=0.18.1',
           'openpyxl>=2.4.7',
           'xmltodict>=0.10.2',
           'requests_ntlm>=1.0.0',
           'beautifulsoup4>=4.8.2',
      ],
      keywords=['ssrs report reporting sql'],
      zip_safe=False)
