from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from database import get_db
from models.catalog import CatalogItem
from schemas.catalog import CatalogItemOut, CatalogSearchResult

router = APIRouter(prefix="/catalog", tags=["Catalog"])

# Fallback product IDs — used when search returns no results
FALLBACK_IDS = [f"PRD-F{str(i).zfill(5)}" for i in range(1, 16)]


@router.get("/search", response_model=CatalogSearchResult)
def search_catalog(
    q: str = Query(..., min_length=1, description="Product name, alias, or keyword"),
    limit: int = Query(10, ge=1, le=50),
    shipping_mode: Optional[str] = Query(None, description="Filter: air | sea | both"),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Fuzzy-ish product search using SQL LIKE on item_name, aliases, and search_keywords.
    Falls back to fallback catalog entries if nothing matches.
    """
    q_lower = q.lower().strip()

    base_q = db.query(CatalogItem).filter(CatalogItem.status == "active")

    if shipping_mode and shipping_mode in ("air", "sea"):
        base_q = base_q.filter(
            or_(CatalogItem.shipping_mode == shipping_mode, CatalogItem.shipping_mode == "both")
        )

    if category:
        base_q = base_q.filter(func.lower(CatalogItem.category) == category.lower())

    # Priority 1: exact item_name match
    exact = base_q.filter(func.lower(CatalogItem.item_name) == q_lower).all()

    # Priority 2: item_name LIKE
    like_name = base_q.filter(
        func.lower(CatalogItem.item_name).contains(q_lower)
    ).order_by(CatalogItem.detection_priority.desc()).limit(limit).all()

    # Priority 3: aliases LIKE
    like_alias = base_q.filter(
        func.lower(CatalogItem.aliases).contains(q_lower)
    ).order_by(CatalogItem.detection_priority.desc()).limit(limit).all()

    # Priority 4: keywords LIKE
    like_kw = base_q.filter(
        func.lower(CatalogItem.search_keywords).contains(q_lower)
    ).order_by(CatalogItem.detection_priority.desc()).limit(limit).all()

    # Merge, deduplicate, preserve priority order
    seen: set[int] = set()
    results: list[CatalogItem] = []
    for item in exact + like_name + like_alias + like_kw:
        if item.id not in seen:
            seen.add(item.id)
            results.append(item)
        if len(results) >= limit:
            break

    fallback_used = False
    if not results:
        fallback_used = True
        results = (
            db.query(CatalogItem)
            .filter(CatalogItem.product_id.in_(FALLBACK_IDS))
            .order_by(CatalogItem.detection_priority.desc())
            .limit(limit)
            .all()
        )

    return CatalogSearchResult(
        items=[CatalogItemOut.model_validate(i) for i in results],
        total=len(results),
        query=q,
        fallback_used=fallback_used,
    )


@router.get("/categories", response_model=List[str])
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(CatalogItem.category).distinct().order_by(CatalogItem.category).all()
    return [r[0] for r in rows]


@router.get("/items", response_model=List[CatalogItemOut])
def list_items(
    category: Optional[str] = Query(None),
    shipping_mode: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(CatalogItem).filter(CatalogItem.status == "active")
    if category:
        q = q.filter(func.lower(CatalogItem.category) == category.lower())
    if shipping_mode and shipping_mode in ("air", "sea"):
        q = q.filter(
            or_(CatalogItem.shipping_mode == shipping_mode, CatalogItem.shipping_mode == "both")
        )
    offset = (page - 1) * page_size
    items = q.order_by(CatalogItem.detection_priority.desc()).offset(offset).limit(page_size).all()
    return [CatalogItemOut.model_validate(i) for i in items]


@router.get("/items/{product_id}", response_model=CatalogItemOut)
def get_item(product_id: str, db: Session = Depends(get_db)):
    item = db.query(CatalogItem).filter(CatalogItem.product_id == product_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    return CatalogItemOut.model_validate(item)
