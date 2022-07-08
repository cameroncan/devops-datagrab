from setuptools import setup, find_packages

setup(
    name="li_devops_metrics",
    extras_require=dict(tests=["pytest", "requests_mock", "pytest-mock", "freezegun"]),
    packages=find_packages(where="src"),
    package_dir={"": "src"},
)