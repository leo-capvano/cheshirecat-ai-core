from typing import List, Optional, Tuple, Generic, TypeVar
from uuid import uuid4
import json

from pydantic import BaseModel, create_model

from fastapi import APIRouter
from fastapi import APIRouter, HTTPException, Depends, Body, Query

from tortoise.models import Model

from cat.looking_glass.stray_cat import StrayCat
from cat.auth.permissions import AuthPermission, AuthResource, check_permissions
from .schemas import Page

def serialize_obj(obj, related_fields: list[str]) -> dict:
    data = obj.__dict__.copy()

    for field in related_fields:
        related = getattr(obj, field, None)

        if related is None:
            data[field] = None

        # reverse FK / M2M → has .related_objects when prefetched
        elif hasattr(related, "related_objects"):
            # if related.related_objects is not None:  # prefetched
            data[field] = [r.__dict__.copy() for r in related.related_objects]

        # forward FK (single related object)
        else:
            data[field] = related.__dict__.copy()

    return data

def get_related_fields(model: Model) -> List[str]:
    related = \
        list(model._meta.fk_fields) + list(model._meta.backward_fk_fields)
    return related

def create_crud(
    db_model: Model,
    prefix: str,
    tag: str,
    auth_resource: AuthResource,
    select_schema: BaseModel,
    create_schema: BaseModel,
    update_schema: BaseModel,
    restrict_by_user_id: bool = False,
    search_fields: List[str] = [],
) -> APIRouter:

    DBModel = db_model

    related_fields = get_related_fields(DBModel)

    SelectSchema, CreateSchema, UpdateSchema = \
        select_schema, create_schema, update_schema
    
    router = APIRouter(
        prefix=prefix,
        tags=[tag]
    )

    @router.get("", description=f"List and search {tag}")
    async def get_list(
        search: Optional[str] = Query(None, description="Search query"),
        # TODOV2: pagination
        cat: StrayCat = check_permissions(auth_resource, AuthPermission.LIST),
    ) -> Page[SelectSchema]:
        
        if restrict_by_user_id:
            q = DBModel.filter(user_id=cat.user_id)
        else:
            q = DBModel.all()
        
        q = q.order_by("-updated_at")

        if search:
            # TODOV2: JSON filtering does not work in sqlite + Tortoise
            prefetched = await q.limit(1000)
            objs = []
            for p in prefetched:
                content = ""
                for sf in search_fields:
                    content += json.dumps(getattr(p, sf)).lower()
                if search.lower() in content:
                    objs.append(p)
                if len(objs) >= 10:
                    break

        else:
            objs = await q.limit(10)

        await DBModel.fetch_for_list(objs, *related_fields)

        return Page(
            items=[
                serialize_obj(obj, related_fields) for obj in objs
            ],
            cursor=""
        )


    @router.get("/{id}", description=f"Get a {tag}")
    async def get_one(
        id: str,
        cat: StrayCat = check_permissions(auth_resource, AuthPermission.READ),
    ) -> SelectSchema:
        
        if restrict_by_user_id:
            q = DBModel.get_or_none(id=id, user_id=cat.user_id)
        else:
            q = DBModel.get_or_none(id=id)
        
        q = q.prefetch_related(*related_fields)

        obj = await q.get_or_none()
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found.")
        
        return obj


    @router.post("", description=f"Create new {tag}")
    async def create(
        data: CreateSchema = Body(...),
        cat: StrayCat = check_permissions(auth_resource, AuthPermission.WRITE),
    ) -> SelectSchema:
        
        if restrict_by_user_id:
            new_obj = DBModel(user_id=cat.user_id, **data.model_dump())
        else:
            new_obj = DBModel(**data.model_dump())

        await new_obj.save()
        await DBModel.fetch_related(new_obj, *related_fields)
        return new_obj


    @router.put("/{id}", description=f"Edit a {tag}")
    async def edit(
        id: str,
        data: UpdateSchema = Body(...),
        cat: StrayCat = check_permissions(auth_resource, AuthPermission.EDIT),
    ) -> SelectSchema:

        if restrict_by_user_id:
            obj = await DBModel.get_or_none(id=id, user_id=cat.user_id)
        else:
            obj = await DBModel.get_or_none(id=id)

        if obj is None:
            raise HTTPException(status_code=404, detail=f"{tag } not found.")

        obj.update_from_dict(data.model_dump())
        await obj.save()
        await DBModel.fetch_related(obj, *related_fields)
        return obj


    @router.delete("/{id}")
    async def delete(
        id: str,
        cat: StrayCat = check_permissions(auth_resource, AuthPermission.DELETE),
    ):
        
        if restrict_by_user_id:
            obj = await DBModel.get_or_none(id=id, user_id=cat.user_id)
        else:
            obj = await DBModel.get_or_none(id=id)

        if obj is None:
            raise HTTPException(status_code=404, detail=f"{tag } not found.")
                    
        await obj.delete() # TODOV2: check effects on relationships


    return router