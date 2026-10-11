from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_existing_running_tasks_become_reclaimable_without_losing_budget(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/upgrade.db"
    monkeypatch.setenv("AGENTIX_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "f30efb85c0bc")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text("INSERT INTO owners (id,name,token_hash,active) VALUES ('owner','O','h',1)")
        )
        db.execute(
            text(
                "INSERT INTO accounts (id,owner_id,kind,reference,balance) "
                "VALUES ('account','owner','task','task',200)"
            )
        )
        db.execute(
            text(
                "INSERT INTO agents "
                "(id,owner_id,name,framework,endpoint,token_hash,available,capacity) "
                "VALUES ('agent','owner','A','custom','https://example.com','a',1,1)"
            )
        )
        db.execute(
            text(
                "INSERT INTO skills "
                "(id,agent_id,slug,version,description,input_schema,output_schema) "
                "VALUES ('skill','agent','review','1','Review','{}','{}')"
            )
        )
        db.execute(
            text(
                "INSERT INTO projects (id,owner_id,title,account_id) "
                "VALUES ('project','owner','P','account')"
            )
        )
        db.execute(
            text(
                "INSERT INTO tasks "
                "(id,project_id,agent_id,skill_id,provider_owner_id,account_id,"
                "instructions,acceptance_criteria,price,state) "
                "VALUES ('task','project','agent','skill','owner','account',"
                "'Review','Evidence',200,'running')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as db:
        task = db.execute(
            text(
                "SELECT state,attempts,lease_expires_at,lease_token_hash FROM tasks WHERE id='task'"
            )
        ).one()
        assert task.state == "running" and task.attempts == 0
        assert task.lease_expires_at is not None and task.lease_token_hash is None
        assert db.scalar(text("SELECT balance FROM accounts WHERE id='account'")) == 200
    command.downgrade(config, "f30efb85c0bc")
    with engine.connect() as db:
        assert db.scalar(text("SELECT state FROM tasks WHERE id='task'")) == "running"
        assert db.scalar(text("SELECT balance FROM accounts WHERE id='account'")) == 200
    engine.dispose()
