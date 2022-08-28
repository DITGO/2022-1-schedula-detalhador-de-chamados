from typing import List, Union

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.orm import Session

from database import engine, get_db
from models import Base, Request, has

router = APIRouter()


class UpdateHasModel(BaseModel):
    problem_id: int
    is_event: bool = False
    event_date: str | None = None
    request_status: str | None = "pending"
    priority: str | None = "normal"


class UpdateRequestModel(BaseModel):
    attendant_name: str | None = None
    applicant_name: str = None
    applicant_phone: str = None
    place: str = None
    description: str | None = None
    created_at: str | None = None
    workstation_id: int = None
    problems: List[UpdateHasModel]

    class Config:
        schema_extra = {
            "example": {
                "applicant_name": "Fulano de Tal",
                "applicant_phone": "999999999",
                "place": "Sala de Testes",
                "description": "Ta tudo dando errado nos testes.",
                "workstation_id": 2,
                "problems": [
                    {
                        "problem_id": 1,
                        "is_event": False,
                        "event_date": None,
                        "request_status": "pending",
                        "priority": "hight",
                    },
                    {
                        "problem_id": 2,
                        "is_event": True,
                        "event_date": "2020-01-01T00:00:00",
                        "request_status": "pending",
                        "priority": "urgent",
                    },
                ],
            }
        }


class hasModel(BaseModel):
    problem_id: int
    is_event: bool = False
    event_date: str | None = None
    request_status: str = "pending"
    priority: str = "normal"


class RequestModel(BaseModel):
    attendant_name: str
    applicant_name: str
    applicant_phone: str
    place: str
    description: str | None = None
    created_at: str | None = None
    workstation_id: int
    problems: List[hasModel]

    class Config:
        schema_extra = {
            "example": {
                "attendant_name": "Fulano",
                "applicant_name": "Ciclano",
                "applicant_phone": "1111111111",
                "place": "Sala de Reuniões",
                "description": "Chamado aberto para acesso a internet.",
                "workstation_id": 1,
                "problems": [
                    {
                        "problem_id": 1,
                        "is_event": False,
                        "event_date": None,
                        "request_status": "pending",
                        "priority": "normal",
                    },
                    {
                        "problem_id": 2,
                        "is_event": True,
                        "event_date": "2020-01-01T00:00:00",
                        "request_status": "pending",
                        "priority": "normal",
                    },
                ],
            }
        }


Base.metadata.create_all(bind=engine)


def get_error_response(e: Exception):
    return {
        "message": "Erro ao processar dados",
        "error": str(e),
        "data": None,
    }


@router.post("/chamado", tags=["Chamado"], response_model=RequestModel)
async def post_request(data: RequestModel, db: Session = Depends(get_db)):
    try:
        data_dict = data.dict()
        problems = data_dict.pop("problems")

        new_object = Request(**data_dict)
        db.add(new_object)
        db.commit()
        db.refresh(new_object)
        new_object = jsonable_encoder(new_object)

        for problem in problems:
            problem["request_id"] = new_object["id"]
            db.execute(insert(has).values(**problem))

        db.commit()

        response_data = jsonable_encoder(
            {
                "message": "Dado cadastrado com sucesso",
                "error": None,
                "data": new_object,
            }
        )

        return JSONResponse(
            content=response_data, status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        return JSONResponse(
            content=get_error_response(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def get_has_data(query, db: Session):
    final_list = []
    for request in query:
        request_dict = jsonable_encoder(request)
        requests = (
            db.query(has).filter(has.c.request_id == request_dict["id"]).all()
        )
        request_dict["problems"] = requests
        final_list.append(request_dict)
    return final_list


@router.get("/chamado", tags=["Chamado"])
async def get_chamado(
    problem_id: Union[int, None] = None, db: Session = Depends(get_db)
):
    try:
        if problem_id:
            query = (
                db.query(Request)
                .filter(Request.problems.any(id=problem_id))
                .all()
            )

            if query:
                final_list = get_has_data(query, db)
                query = jsonable_encoder(final_list)
                message = "Dados buscados com sucesso"
                status_code = status.HTTP_200_OK
            else:
                message = "Nenhum chamado com esse tipo de problema encontrado"
                status_code = status.HTTP_200_OK

            response_data = {"message": message, "error": None, "data": query}

            return JSONResponse(
                content=jsonable_encoder(response_data),
                status_code=status_code,
            )
        else:
            query = db.query(Request).all()
            all_data = get_has_data(query, db)
            all_data = jsonable_encoder(all_data)
            response_data = {
                "message": "Dados buscados com sucesso",
                "error": None,
                "data": all_data,
            }
            return JSONResponse(
                content=dict(response_data), status_code=status.HTTP_200_OK
            )

    except Exception as e:
        return JSONResponse(
            content=get_error_response(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.delete("/chamado", tags=["Chamado"])
async def delete_chamado(
    request_id: int, problem_id: int, db: Session = Depends(get_db)
):
    try:
        query = (
            db.query(has)
            .filter(has.c.request_id == request_id)
            .filter(has.c.problem_id == problem_id)
            .update({"request_status": "solved"})
        )

        if query:
            db.commit()
            query_data = (
                db.query(has)
                .filter(has.c.request_id == request_id)
                .filter(has.c.problem_id == problem_id)
                .first()
            )
            query_data = jsonable_encoder(query_data)
            message = "Chamado marcado como resolvido"
        else:
            message = "Chamado não encontrado"
            query_data = None

        response_data = {"message": message, "error": None, "data": query_data}

        return JSONResponse(
            content=response_data, status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content=get_error_response(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.put("/chamado/{request_id}", tags=["Chamado"])
async def update_chamado(
    data: UpdateRequestModel, request_id: int, db: Session = Depends(get_db)
):
    if data.attendant_name:
        return JSONResponse(
            content={
                "message": "Não é possível alterar o nome do atendente",
                "error": None,
                "data": None,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        data_dict = data.dict(exclude_none=True)
        problems = data_dict.pop("problems")
        to_update = (
            db.query(Request)
            .filter(Request.id == request_id)
            .update(data_dict)
        )
        if to_update:
            db.commit()
            for problem in problems:
                problem["request_id"] = request_id
                db.query(has).filter(has.c.request_id == request_id).filter(
                    has.c.problem_id == problem["problem_id"]
                ).update(problem)
            db.commit()
            query = db.query(Request).filter(Request.id == request_id).all()
            final_list = get_has_data(query, db)
            query = jsonable_encoder(final_list)
            message = "Dados atualizados com sucesso"
            status_code = status.HTTP_200_OK

            response_data = {"message": message, "error": None, "data": query}
        else:
            message = "Chamado não encontrado"
            status_code = status.HTTP_200_OK
        return JSONResponse(
            content=jsonable_encoder(response_data), status_code=status_code
        )
    except Exception as e:
        return JSONResponse(
            content=get_error_response(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )