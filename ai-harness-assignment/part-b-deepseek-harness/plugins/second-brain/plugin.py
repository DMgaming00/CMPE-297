import sqlite3
class SecondBrain:
    def __init__(self, db='notes.db'):
        self.conn = sqlite3.connect(db)
