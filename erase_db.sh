env\Scripts\python.exe -c "
from app.connection import get_db
from app.models import Job, Message, Channel, AnalysisRun
db = get_db()
db.query(Job).delete()
db.query(AnalysisRun).delete()
db.query(Message).delete()
db.query(Channel).delete()
db.commit()
print('Database cleared.')
"