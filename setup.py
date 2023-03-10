from setuptools import setup


setup(
    name="fswatcher",
    version="0.1.0",
    description="AWS File System Watcher",
    author="Damian Barrous-Dume",
    packages=["fswatcher"],
    include_package_data=True,
    install_requires=["watchdog==2.2.0", "boto3==1.26.35", "slack_sdk==3.19.5"],
    entry_points={
        "console_scripts": [
            "fswatcher = fswatcher.fswatcher:main",
        ]
    },
)
