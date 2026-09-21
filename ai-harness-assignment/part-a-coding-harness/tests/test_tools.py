from src.tools import list_files
def test_list():
    assert type(list_files()) == list
