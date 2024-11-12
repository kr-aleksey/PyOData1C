from datetime import datetime
from decimal import Decimal

from pydantic import Field, UUID1, field_serializer

from PyOData1C.http import Connection, auth
from PyOData1C.models import OdataModel
from PyOData1C.odata import OData

"""
Пример 1
"""

class NomenclatureTypeModel(OdataModel):
    uid_1c: str = Field(alias='Ref_Key', max_length=36, exclude=True)
    name: str = Field(alias='Description', max_length=200)


class MeasureUnitModel(OdataModel):
    uid_1c: UUID1 = Field(alias='Ref_Key', exclude=True)
    name: str = Field(alias='Description', max_length=15)


class NomenclatureModel(OdataModel):
    uid_1c: UUID1 = Field(alias='Ref_Key', exclude=True)
    code: str = Field(alias='Code', max_length=12)
    name: str = Field(alias='Description', max_length=200)
    nomenclature_type: NomenclatureTypeModel = Field(alias='ВидНоменклатуры')
    measure_unit: MeasureUnitModel = Field(alias='ЕдиницаИзмерения')

    nested_models = {
        'nomenclature_type': NomenclatureTypeModel,
        'measure_unit': MeasureUnitModel
    }


class NomenclatureOdata(OData):
    database = 'erp_dev'
    entity_model = NomenclatureModel
    entity_name = 'Catalog_Номенклатура'


with Connection('erp.domain.local',
                'http',
                auth.HTTPBasicAuth('user', 'pass')) as conn:
    nomenclatures: list[OdataModel] = (
        NomenclatureOdata
        .manager(conn)
        .expand('measure_unit', 'nomenclature_type')
        .filter(code__in=['00-00000150', '00-00000370'])
        .all()
    )
print(nomenclatures)


"""
Пример 2
"""

class ProductModel(OdataModel):
    uid_1c: UUID1 = Field(alias='Номенклатура_Key',
                          exclude=True)
    quantity: Decimal = Field(alias='Количество')


class StageModel(OdataModel):
    uid_1c: UUID1 = Field(alias='Ref_Key',
                          exclude=True)
    number: str = Field(alias='Number',
                        min_length=1,
                        max_length=200)
    stage_date: datetime = Field(alias='Date')
    status: str = Field(alias='Статус', )
    products: list[ProductModel] = Field(alias='ВыходныеИзделия', exclude=True)

    nested_models = {
        'products': ProductModel,
    }

    @field_serializer('stage_date')
    def serialize_stage_date(self, stage_date: datetime, _info):
        return stage_date.isoformat('T', 'seconds')


class StageOdata(OData):
    database = 'erp_dev'
    entity_model = StageModel
    entity_name = 'Document_ЭтапПроизводства2_2'


with Connection('erp.domain.local',
                'http',
                auth.HTTPBasicAuth('user', 'pass')) as conn:
    manager = StageOdata.manager(conn)
    stages = (manager
              .filter(stage_date__gt=datetime(year=2024, month=1, day=12))
              .top(5)
              .skip(2)
              .all())
    print(stages)
    stage = manager.get(guid='4ab2c2af-8a36-11ec-aa39-ac1f6bd30991')
    print(stage)
    stage.stage_date = datetime.now()
    stage = manager.update(stage.uid_1c, stage)
    print(stage)


"""
Пример 3
"""

class StageCreateModel(OdataModel):
    uid_1c: UUID1 = Field(alias='Ref_Key',
                          exclude=True)
    number: str = Field(alias='Number')
    stage_date: datetime = Field(alias='Date')


    @field_serializer('stage_date')
    def serialize_stage_date(self, stage_date: datetime, _info):
        return stage_date.isoformat('T', 'seconds')


class StageOdata(OData):
    database = 'erp_dev'
    entity_model = StageModel
    entity_name = 'Document_ЭтапПроизводства2_2'


data = StageModel.model_construct(number='st1',
                                  stage_date=datetime(2024, 11, 12))

with Connection('erp.domain.local',
                'http',
                auth.HTTPBasicAuth('user', 'pass')) as conn:

    stage = StageOdata.manager(conn).create(data)
    print(stage)
