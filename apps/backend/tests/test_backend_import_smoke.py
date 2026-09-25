import importlib


def test_backend_application_imports_cleanly():
    module = importlib.import_module("main")
    assert module.app.title == "LoanHub API"
