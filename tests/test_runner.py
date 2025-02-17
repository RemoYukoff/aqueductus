from aqueductus.main import main


def test_runner():
    try:
        main(["tests/test_common_asserts.yml", "tests/providers.yml"])
    except SystemExit as e:
        assert e.code == 0


def test_runner_with_invalid_config():
    try:
        main(["tests/test_common_asserts.yml", "tests/invalid_providers.yml"])
    except SystemExit as e:
        assert e.code == 2
