from datetime import datetime
from http import HTTPStatus
from typing import Any, Callable, Iterable, Type, TypeVar

import requests.exceptions as r_exceptions
from pydantic import ValidationError
from requests import Response

from PyOData1C.exeptions import ODataError, ResponseError
from PyOData1C.http import Connection, Request
from PyOData1C.models import ODataModel

OM = TypeVar('OM', bound=ODataModel)

type_repr = {
    bool: lambda v: str(v).lower(),
    str: lambda v: f"'{v}'",
    datetime: lambda v: "datetime'{}'".format(v.isoformat('T', 'seconds')),
}


class Q:
    """
    Q is a node of a tree graph. A node is a connection whose child
    nodes are either leaf nodes or other instances of the node.
    This code is partially based on Django code.
    """
    AND = 'and'
    OR = 'or'
    NOT = 'not'

    _operators = ('eq', 'ne', 'gt', 'ge', 'lt', 'le', 'in')
    _default_operator = 'eq'
    _annotations = ('guid', 'datetime')
    _arg_error_msg = 'The positional argument must be a Q object. Received {}.'

    def __new__(cls, *args: 'Q', **kwargs: Any):
        """
        Creates a Q object with kwargs leaf. Combines the created
        Q object with the objects passed via positional arguments
        using &. Returns the resulting Q object.
        :param args: Q objects.
        :param kwargs: Lookups.
        """
        obj = super().__new__(cls)
        children = []
        for key, value in kwargs.items():
            key_elements = key.split('__')
            if key_elements[-1] in cls._annotations:
                lookup = key_elements[-2]
            elif key_elements[-1] in cls._operators:
                lookup = key_elements[-1]
            else:
                lookup = None
            if lookup == 'in':
                children.append(
                    cls.create(children=[(key, value)], connector=Q.OR))
            else:
                children.append((key, value))
        obj.children = children
        obj.connector = Q.AND
        obj.negated = False

        for arg in args:
            if not isinstance(arg, Q):
                raise TypeError(cls._arg_error_msg.format(type(arg)))
            obj &= arg

        return obj

    def __init__(self, *args: 'Q', **kwargs: Any):
        if not args and not kwargs:
            raise AttributeError('No arguments given')

    @classmethod
    def create(cls, children=None, connector=None, negated=False):
        obj = cls.__new__(cls)
        obj.children = children.copy() if children else []
        obj.connector = connector if connector is not None else connector
        obj.negated = negated
        return obj

    def __str__(self) -> str:
        return self.build_expression()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self}>'

    def __copy__(self):
        return self.create(children=self.children,
                           connector=self.connector,
                           negated=self.negated)

    copy = __copy__

    def __or__(self, other):
        return self.combine(other=other, connector=self.OR)

    def __and__(self, other):
        return self.combine(other=other, connector=self.AND)

    def __invert__(self):
        obj = self.copy()
        obj.negated = not self.negated
        return obj

    def add(self, other) -> None:
        if self.connector != other.connector or other.negated:
            self.children.append(other)
        else:
            self.children.extend(other.children)

    def combine(self, other, connector):
        obj = self.create(connector=connector)
        obj.add(self)
        obj.add(other)
        return obj

    def build_expression(self,
                         field_mapping: dict[str, str] | None = None) -> str:
        """
        Recursively iterates over child elements. Builds an expression
        taking into account the priorities of the operations.
        The field_mapping argument is used to map the field name
        to the OData field name.
        :param field_mapping: {field_name: alias}
        :return: Full filter expression.
        """
        child_expressions: list[str] = []
        for child in self.children:
            if isinstance(child, Q):
                child_expression: str = child.build_expression(field_mapping)
                if self.connector == Q.AND and child.connector == Q.OR:
                    child_expression: str = f'({child_expression})'
            else:
                child_expression: str = self._build_lookup(child,
                                                           field_mapping)
            child_expressions.append(child_expression)
        expression = f' {self.connector} '.join(child_expressions)
        if self.negated:
            expression = f'{self.NOT} ({expression})'
        return expression

    def _build_lookup(self,
                      lookup: tuple[str, Any],
                      field_mapping: dict[str, str] | None = None) -> str:
        """
        Builds a lookup to a filter expression.
        :param lookup: (key, value)
        :param field_mapping: {field_name: alias}
        :return: Expression. For example: "Name eq 'Ivanov'"
        """
        match lookup[0].split('__'):
            case *field_elements, operator, annotation if (
                operator in self._operators and annotation in self._annotations
            ):
                pass
            case *field_elements, operator if operator in self._operators:
                annotation = None
            case field_elements:
                operator = None
                annotation = None
        field = '__'.join(field_elements)
        if field_mapping is not None:
            if field not in field_mapping:
                raise KeyError(
                    f"Field '{field}' not found. "
                    f"Use one of {list(field_mapping.keys())}"
                )
            field = field_mapping[field]
        operator = operator or self._default_operator
        if operator not in self._operators:
            raise KeyError(
                f"Unsupported operator {operator} ({lookup[0]}). "
                f"Use one of {self._operators}."
            )
        return self._get_lookup_builder(operator)(field, lookup[1], annotation)

    def _get_lookup_builder(self, lookup: str) -> Callable:
        if lookup == 'in':
            return self._in_builder
        return lambda field, value, annotation: \
            f'{field} {lookup} {self._annotate_value(value, annotation)}'

    def _in_builder(self,
                    field: str,
                    value: Any,
                    annotation: str | None) -> str:
        """
        :param field: Field name.
        :param value: Value.
        :param annotation: Annotation.
        Converts lookup 'in' to an Odata filter parameter.
        For example: 'foo eq value or foo eq value2 ...'
        """
        items = [f'{field} eq {self._annotate_value(v, annotation)}'
                 for v in value]
        return ' or '.join(items)

    def _annotate_value(self,
                        value: Any,
                        annotation: str | None) -> str:
        """
        :param value: Value to annotate.
        :param annotation: Annotation ('guid', 'date', etc ).
        :return: Annotated value. For example: guid'123'.
        """
        if annotation is not None:
            if annotation not in self._annotations:
                raise KeyError(
                    f"Unknown annotation {annotation}. "
                    f"Use one of {self._annotations}"
                )
            return f"{annotation}'{value}'"

        if type(value) in type_repr:
            return type_repr[type(value)](value)
        return str(value)


class OData:
    database: str
    entity_model: OM
    entity_name: str

    _err_msg: str = "Required attribute not defined: {}."

    @classmethod
    def manager(cls, connection: Connection) -> 'ODataManager':
        """Returns an instance of the odata manager."""
        assert hasattr(cls, 'entity_model'), (
            cls._err_msg.format(f'{cls.__name__}.entity_model'))
        assert hasattr(cls, 'entity_name'), (
            cls._err_msg.format(f'{cls.__name__}.entity_name'))
        return ODataManager(odata_class=cls, connection=connection)


class ODataManager:
    odata_path = 'odata/standard.odata'
    odata_list_json_key = 'value'

    def __init__(self, odata_class: Type[OData], connection: Connection):
        self.odata_class = odata_class
        self.connection = connection
        self.request: Request | None = None
        self.response: Response | None = None
        self.validation_errors: list[ValidationError] = []
        self._expand: Iterable[str] | None = None
        self._filter: Q | None = None
        self._skip: int | None = None
        self._top: int | None = None

    def __str__(self):
        return f'{self.odata_class.__name__} manager'

    def _check_response(self, ok_status: int) -> None:
        """Checking response status code."""
        if self.response.status_code != ok_status:
            raise ResponseError(self.response.status_code,
                                self.response.reason,
                                self.response.text)

    def _validate(self,
                  data: list[dict[str, Any]] | dict[str, Any],
                  ignore_invalid: bool = False
                  ) -> list[OM] | OM:
        """Validation of response data."""
        self.validation_errors = []
        if isinstance(data, list):
            validated_objs = []
            for obj in data:
                validated_objs.append(self._validate_obj(obj, ignore_invalid))
            return validated_objs
        return self._validate_obj(data, ignore_invalid)

    def _validate_obj(self,
                      obj: dict[str, Any],
                      ignore_invalid: bool) -> OM:
        """Object validation."""
        try:
            return self.odata_class.entity_model.model_validate(obj)
        except ValidationError as e:
            self.validation_errors.append(e)
            if not ignore_invalid:
                raise e

    def _json(self) -> dict[str, Any]:
        """Decodes json response."""
        try:
            data = self.response.json()
        except r_exceptions.JSONDecodeError as e:
            raise ODataError(e)
        return data

    @staticmethod
    def _to_dict(data: OM | dict[str, Any]) -> dict[str, Any]:
        """Converts data to dict."""
        if isinstance(data, ODataModel):
            return data.model_dump(by_alias=True)
        return data

    def get_url(self) -> str:
        """Returns the url of the entity."""
        return (f'{self.odata_class.database}'
                f'/{self.odata_path}'
                f'/{self.odata_class.entity_name}')

    def get_canonical_url(self, guid: str) -> str:
        """Returns the canonical url of the entity."""
        return f"{self.get_url()}(guid'{guid}')"

    def all(self, ignor_invalid: bool = False) -> list[OM]:
        """
        Returns validated instances of the ODataModel class.
        If ignor_invalid = True, invalid objects will be skipped,
        errors will be accumulated in self.validation_errors.
        Otherwise, a pydantic.ValidationError exception will be raised.
        """
        self.request = Request(
            method='GET',
            relative_url=self.get_url(),
            query_params=self.prepare_query_params(
                self.qp_select,
                self.qp_expand,
                self.qp_top,
                self.qp_skip,
                self.qp_filter
            )
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        try:
            data: list[dict[str, Any]] = self._json()[self.odata_list_json_key]
        except KeyError:
            raise ODataError(
                f'Response json has no key {self.odata_list_json_key}'
            )
        return self._validate(data, ignor_invalid)

    def create(self, data: OM| dict[str, Any]) -> OM:
        """Creates a new entity."""
        self.request = Request(method='POST',
                               relative_url=self.get_url(),
                               data=self._to_dict(data))
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.CREATED)
        return self._validate(self._json())

    def get(self, guid: str) -> OM:
        """Get an entity by guid."""
        self.request = Request(method='GET',
                               relative_url=self.get_canonical_url(guid),
                               query_params=self.prepare_query_params(
                                   self.qp_select, self.qp_expand)
                               )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        return self._validate(self._json())

    def update(self,
               guid: str,
               data: OM | dict[str, Any]) -> OM:
        """Updates (patch) an entity by guid."""
        self.request = Request(
            method='PATCH',
            relative_url=self.get_canonical_url(guid),
            data=self._to_dict(data),
            query_params=self.prepare_query_params(
                self.qp_select,
                self.qp_expand
            )
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        return self._validate(self._json())

    def post_document(self,
                      guid: str,
                      operational_mode: bool = False) -> None:
        """Document posting."""
        self.request = Request(
            method='POST',
            relative_url=f'{self.get_canonical_url(guid)}/Post',
            query_params={
                'PostingModeOperational':
                    type_repr[bool](
                        operational_mode)
            }
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)

    def unpost_document(self, guid: str) -> None:
        """Cancel posting a document."""
        self.request = Request(
            method='POST',
            relative_url=f'{self.get_canonical_url(guid)}/Unpost'
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)

    """Query parameters."""

    @property
    def qp_select(self) -> tuple[str, str | None]:
        qp = '$select'
        fields = {
            field: info
            for field, info
            in self.odata_class.entity_model.model_fields.items()
            if info.is_required()
        }
        nested_models = self.odata_class.entity_model.nested_models
        aliases = []
        for field, info in fields.items():
            alias = info.alias or field
            if nested_models is not None and field in nested_models:
                for nested_field, nested_info in nested_models[
                    field].model_fields.items():
                    nested_alias = nested_info.alias or nested_field
                    aliases.append(f'{alias}/{nested_alias}')
            else:
                aliases.append(alias)
        return qp, ', '.join(aliases)

    @property
    def qp_expand(self) -> tuple[str, str | None]:
        qp = '$expand'
        if self._expand is None:
            return qp, None
        fields = self.odata_class.entity_model.model_fields
        aliases = []
        for field_name in self._expand:
            aliases.append(fields[field_name].alias or field_name)
        return '$expand', ', '.join(aliases)

    def expand(self, *args: str) -> 'ODataManager':
        nested_models = self.odata_class.entity_model.nested_models
        fields = []
        for field_name in args:
            if field_name not in nested_models:
                raise ValueError(
                    f"Nested model '{field_name}' not found. "
                    f"Use one of {list(nested_models.keys())}"
                )
            fields.append(field_name)
        self._expand = fields
        return self

    @property
    def qp_filter(self) -> tuple[str, str | None]:
        qp = '$filter'
        if self._filter is None:
            return qp, None
        fields = self.odata_class.entity_model.model_fields
        field_mapping = {}
        for f, i in fields.items():
            if '__' in f:
                field_elements = f.split('__')
                nested_field = []
                model = self.odata_class.entity_model
                for element in field_elements[:-1]:
                    if element not in model.nested_models:
                        raise ValueError(
                            f"Nested model '{element}' not found."
                        )
                    nested_field.append(model.model_fields[element].alias)
                    model = model.nested_models[element]
                nested_field.append(model.model_fields[field_elements[-1]].alias)
                field_mapping[f] = '/'.join(nested_field)
            else:
                field_mapping[f] = i.alias
        return qp, self._filter.build_expression(field_mapping)

    def filter(self, *args, **kwargs) -> 'ODataManager':
        """
        Sets filtering conditions.
        Example: filter(Q(a=1, b__gt), c__in=[1, 2])
        :param args: Q objects.
        :param kwargs: Lookups.
        :return: self
        """
        q = Q(*args, **kwargs)
        if self._filter is not None:
            self._filter &= q
        else:
            self._filter = q
        return self

    @property
    def qp_skip(self) -> tuple[str, str | None]:
        return '$skip', self._skip

    def skip(self, n: int) -> 'ODataManager':
        """Skips n number of entities."""
        self._skip = n
        return self

    @property
    def qp_top(self) -> tuple[str, str | None]:
        return '$top', self._top

    def top(self, n: int) -> 'ODataManager':
        """Getting n number of entities."""
        self._top = n
        return self

    @staticmethod
    def prepare_query_params(*args: tuple[str, str]) -> dict[str, Any]:
        qps = {}
        for qp, val in args:
            if val is not None:
                qps[qp] = val
        return qps
