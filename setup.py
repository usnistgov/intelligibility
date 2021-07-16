import setuptools

with open("README.md", "r",encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name="mcvqoe-intelligibility",
    author="Jesse Frey, Peter Fink, Jaden Pieper",
    author_email="jesse.frey@nist.gov,jaden.pieper@nist.gov",
    description="Measurement code for intelligibility",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.nist.gov/gitlab/PSCR/MCV/psud",
    packages=setuptools.find_namespace_packages(include=['mcvqoe.*']),
    include_package_data=True,
    use_scm_version={'write_to' : 'mcvqoe/intelligibility/version.py'},
    setup_requires=['setuptools_scm'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Public Domain",
        "Operating System :: OS Independent",
    ],
    license='NIST software License',
    install_requires=[
        'mcvqoe-nist>=0.4',
        'abcmrt-nist>=0.1.3',
    ],
    entry_points={
        'console_scripts':[
            'intell-sim=mcvqoe.intelligibility.intelligibility_simulate:main',
            'intell-measure=mcvqoe.intelligibility.intelligibility_1way_1loc:main',
            'intell-reprocess=mcvqoe.intelligibility.intelligibility_reprocess:main',
        ],
    },
    python_requires='>=3.6',
)

