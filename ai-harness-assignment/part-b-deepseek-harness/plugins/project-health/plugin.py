import os
def project_summary():
    return {'files': len(os.listdir('.'))}
