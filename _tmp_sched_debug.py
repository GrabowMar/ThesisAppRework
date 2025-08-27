from datetime import datetime, timezone
from flask import Flask
from app.extensions import db
from app.models import BatchSchedule, BatchAnalysis
from app.services.batch_scheduler import batch_scheduler_service
from app.services.batch_service import batch_service
print('Scheduler object:', batch_scheduler_service)
print('Batch service scheduler attr:', batch_service.scheduler)
app=Flask(__name__)
app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',SQLALCHEMY_TRACK_MODIFICATIONS=False)
db.init_app(app)
with app.app_context():
 db.create_all()
 s=BatchSchedule(cron_expression='interval:1s', batch_config_json='{ name:Demo,analysis_types:[security],models:[m1],app_range:1}')
 db.session.add(s); db.session.commit()
 print('Before:', s.id, s.next_run)
 executed = batch_scheduler_service.run_once(now=datetime.now(timezone.utc))
 print('Executed count:', executed)
 db.session.refresh(s)
 print('After:', s.id, s.last_run, s.next_run)
 print('BatchAnalysis rows:', db.session.query(BatchAnalysis).count())
 print('Jobs in batch_service memory:', len(batch_service.jobs))
