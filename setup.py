from setuptools import setup, find_packages

setup(name='stratumus',
      version='0.0.10',
      description='Layered Yaml Python Configuration',
      author='James Boehmer',
      author_email='james.boehmer@gmail.com',
      url='https://github.com/jamesboehmer/stratumus',
      packages=find_packages(),
      py_modules=['stratumus'],
      include_package_data=True,
      install_requires=[
        'HiYaPyCo==0.4.8'
      ],
      entry_points={
          'console_scripts': [
              'stratumus=stratumus.stratumus:main',
          ],
      },
      classifiers=[ 
          'Development Status :: 1 - Planning',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.6'
      ],
      platforms = 'any',
      license = 'GPL',
      keywords='layered configuration yaml',
      )
