# -*- coding: utf-8 -*-
from fastapi import APIRouter

from dashboard_service import build_dashboard_summary


router = APIRouter()


@router.get("/api/dashboard/summary")
async def get_dashboard_summary():
    return await build_dashboard_summary()
