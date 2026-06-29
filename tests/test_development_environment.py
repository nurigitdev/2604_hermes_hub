import sys


def test_python_version_is_supported() -> None:
    assert sys.version_info >= (3, 11)


def test_core_dependencies_are_importable() -> None:
    import fastapi
    import pydantic_settings
    import sqlalchemy

    assert fastapi.__version__
    assert pydantic_settings.__version__
    assert sqlalchemy.__version__
