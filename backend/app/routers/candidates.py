from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Candidate, CandidateIssueTag
from app.services.issue_tagger import ISSUE_TAXONOMY

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class IssueTagOut(BaseModel):
    id: int
    issue_code: str
    issue_label: str
    ai_suggested: bool
    confirmed: bool
    rejected: bool
    confidence: Optional[float]
    supporting_text: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateOut(BaseModel):
    id: int
    fec_id: Optional[str]
    name: str
    party: Optional[str]
    state: str
    district: Optional[int]
    office: str
    incumbent_challenge: Optional[str]
    primary_date: Optional[datetime]
    primary_status: Optional[str]
    general_status: Optional[str]
    fundraising_total: Optional[float]
    cook_rating: Optional[str]
    notes: Optional[str]
    confirmed_issues: List[str] = []   # just the codes for easy filtering

    model_config = {"from_attributes": True}


class CandidateDetailOut(CandidateOut):
    issue_tags: List[IssueTagOut] = []


class TagCreateIn(BaseModel):
    issue_code: str
    confidence: Optional[float] = None
    supporting_text: Optional[str] = None


class TagUpdateIn(BaseModel):
    confirmed: Optional[bool] = None
    rejected: Optional[bool] = None
    issue_code: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enrich(c: Candidate) -> dict:
    confirmed = [t.issue_code for t in c.issue_tags if t.confirmed and not t.rejected]
    return {**c.__dict__, "confirmed_issues": confirmed}


def _tag_out(t: CandidateIssueTag) -> IssueTagOut:
    return IssueTagOut(
        id=t.id,
        issue_code=t.issue_code,
        issue_label=ISSUE_TAXONOMY.get(t.issue_code, t.issue_code),
        ai_suggested=t.ai_suggested,
        confirmed=t.confirmed,
        rejected=t.rejected,
        confidence=t.confidence,
        supporting_text=t.supporting_text,
        created_at=t.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[CandidateOut])
def list_candidates(
    office: Optional[str] = None,
    state: Optional[str] = None,
    party: Optional[str] = None,
    district: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Candidate)
    if office:
        q = q.filter(Candidate.office == office.upper())
    if state:
        q = q.filter(Candidate.state == state.upper())
    if party:
        q = q.filter(Candidate.party == party.upper())
    if district is not None:
        q = q.filter(Candidate.district == district)
    candidates = q.order_by(Candidate.state, Candidate.district, Candidate.name).all()
    return [_enrich(c) for c in candidates]


@router.get("/issues/pending", response_model=List[dict])
def pending_issue_tags(db: Session = Depends(get_db)):
    """Admin: all AI-suggested tags awaiting review."""
    tags = (
        db.query(CandidateIssueTag)
        .filter(
            CandidateIssueTag.ai_suggested == True,  # noqa
            CandidateIssueTag.confirmed == False,     # noqa
            CandidateIssueTag.rejected == False,      # noqa
        )
        .order_by(CandidateIssueTag.confidence.desc().nullslast())
        .all()
    )
    results = []
    for t in tags:
        c = t.candidate
        results.append({
            "tag_id": t.id,
            "candidate_id": c.id,
            "candidate_name": c.name,
            "candidate_office": c.office,
            "candidate_state": c.state,
            "candidate_district": c.district,
            "candidate_party": c.party,
            "issue_code": t.issue_code,
            "issue_label": ISSUE_TAXONOMY.get(t.issue_code, t.issue_code),
            "confidence": t.confidence,
            "supporting_text": t.supporting_text,
        })
    return results


@router.get("/taxonomy")
def get_taxonomy():
    return [{"code": k, "label": v} for k, v in ISSUE_TAXONOMY.items()]


@router.get("/{candidate_id}", response_model=CandidateDetailOut)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    data = _enrich(c)
    data["issue_tags"] = [_tag_out(t) for t in c.issue_tags if not t.rejected]
    return data


@router.post("/{candidate_id}/issues", response_model=IssueTagOut)
def add_issue_tag(candidate_id: int, body: TagCreateIn, db: Session = Depends(get_db)):
    """Admin: manually add a confirmed issue tag."""
    c = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if body.issue_code not in ISSUE_TAXONOMY:
        raise HTTPException(status_code=400, detail=f"Unknown issue code: {body.issue_code}")
    now = datetime.now(timezone.utc)
    tag = CandidateIssueTag(
        candidate_id=candidate_id,
        issue_code=body.issue_code,
        ai_suggested=False,
        confirmed=True,
        rejected=False,
        confidence=body.confidence,
        supporting_text=body.supporting_text,
        created_at=now,
        updated_at=now,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return _tag_out(tag)


@router.patch("/{candidate_id}/issues/{tag_id}", response_model=IssueTagOut)
def update_issue_tag(candidate_id: int, tag_id: int, body: TagUpdateIn, db: Session = Depends(get_db)):
    """Admin: confirm or reject an AI-suggested tag."""
    tag = db.query(CandidateIssueTag).filter(
        CandidateIssueTag.id == tag_id,
        CandidateIssueTag.candidate_id == candidate_id,
    ).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if body.confirmed is not None:
        tag.confirmed = body.confirmed
    if body.rejected is not None:
        tag.rejected = body.rejected
    if body.issue_code is not None:
        if body.issue_code not in ISSUE_TAXONOMY:
            raise HTTPException(status_code=400, detail=f"Unknown issue code: {body.issue_code}")
        tag.issue_code = body.issue_code
    tag.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tag)
    return _tag_out(tag)
