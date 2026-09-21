from src.train import train
def test_train():
    res = train({'lr':0.01})
    assert res['validation_accuracy'] > 0
