from typing import ClassVar, Optional

from pydantic import BaseModel


class ODataModel(BaseModel):
    """
    Data model for serialization, deserialization and validation.
    The nested_models attribute is used to optimize the query.
    If nested_models is None, all fields of nested entities will
    be requested, regardless of their presence in the nested model.
    """
    nested_models: ClassVar[Optional[dict[str, BaseModel]]] = None
