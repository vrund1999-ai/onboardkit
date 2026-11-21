import re

import onboardkit
from onboardkit import datagen

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_package_exposes_version() -> None:
    assert SEMVER.match(onboardkit.__version__)


def test_datagen_exposes_generator_version() -> None:
    assert SEMVER.match(datagen.GENERATOR_VERSION)
