from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.models import TestTable
from app.schemas.test import TestCreate, TestRead

router = APIRouter(prefix="/test", tags=["test"])


@router.post("", response_model=TestRead, status_code=status.HTTP_201_CREATED)
def create_test_entry(
    payload: TestCreate,
    db: Session = Depends(get_db_session),
) -> TestTable:
    item = TestTable(name=payload.name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[TestRead])
def list_test_entries(db: Session = Depends(get_db_session)) -> list[TestTable]:
    result = db.scalars(select(TestTable).order_by(TestTable.id.asc()))
    return list(result)