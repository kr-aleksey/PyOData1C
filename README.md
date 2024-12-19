# PyOData1C - ORM для обмена данными с системами учета компании "1С"
PyOData1C работает через HTTP REST сервис 1С. REST 1С использует протокол OData версии 3. REST интерфейс использует 
возможности протокола OData лишь частично. В свою очередь в PyOData1C реализована поддержка только основных возможностей 
REST OData 1C. PyOData1C использует Pydantic для сериализации, десериализации и валидации. 

## Установка
`pip install PyOData1C`

## Зависимости
- Python >= 3.11
- Pydantic >= 2.9
- Requests >= 2.32

## Использование

```python
from PyOData1C.http import auth, Connection
from PyOData1C.models import ODataModel
from PyOData1C.odata import OData
from pydantic import Field, UUID1


class MeasureUnitModel(ODataModel):
    uid: UUID1 = Field(alias='Ref_Key', exclude=True)
    name: str = Field(alias='Description', max_length=6)


class NomenclatureModel(ODataModel):
    uid: UUID1 = Field(alias='Ref_Key', exclude=True)
    code: str = Field(alias='Code', max_length=12)
    name: str = Field(alias='Description', max_length=200)
    measure_unit: MeasureUnitModel = Field(alias='ЕдиницаИзмерения')

    nested_models = {
        'measure_unit': MeasureUnitModel
    }


class NomenclatureOdata(OData):
    database = 'erp_dev'
    entity_model = NomenclatureModel
    entity_name = 'Catalog_Номенклатура'


with Connection('10.0.0.1',
                'http',
                auth.HTTPBasicAuth('user', 'pass')) as conn:
    nomenclatures: list[ODataModel] = (NomenclatureOdata
                                       .manager(conn)
                                       .expand('measure_unit')
                                       .filter(code__in=['00-123', '00-456'])
                                       .all())
```

Больше примеров найдете в PyOdata1C/sample.py

### class http.Connection
Класс http.Connection предоставляет интерфейс для отправки http запросов. Экземпляр класса может быть создан непосредственно. 
Или используя синтаксис контекстного менеджера. Конструктор класса принимает параметры: host - доменное имя или ip-адрес
сервера 1С, protocol - используемый протокол, authentication - аутентификация, connection_timeout - таймаут соединения в
секундах, read_timeout - таймаут получения данных. http.Connection использует библиотеку Requests.

```python
with Connection('my1c.domain.ru',
                'http',
                HTTPBasicAuth('user', 'pass')) as conn:
```
```python
conn = Connection('my1c.domain.ru',
                  'http',
                  HTTPBasicAuth('user', 'pass'))
```


### class models.ODataModel
Класс models.ODataModel наследуется от класса pydantic.Basemodel. Ваши модели данных должны наследоваться от этого 
класса. Вы можете использовать обширные возможности Pydantic для валидации данных.

models.ODataModel.nested_models

Атрибут nested_models используется для оптимизации запросов OData. Представляет собой словарь ключи которого - строки с
именами полей содержащих вложенные модели, значения - вложенные модели.

```python
class MyModel(ODataModel):
    ...
    nested_models = {
        'measure_unit': MyNestedModel
    }
```

Если поле имеет тип Optional, то оно не попадет в результаты запроса.

### class odata.Odata
Наследуйтесь от класса odata.Odata для описания сущности 1С.
```python
class FooOdata(OData):
    database = 'my1cdb'     # Имя БД 1С
    entity_model = MyModel  # Класс модели данных 
    entity_name='bar'       # Имя сущности в 1С
```

### method manager()
Принимает экземпляр класса __http.Connection__. Возвращает экземпляр __odata.Manager__.

### class.ODataManager
Экземпляр класса создается через метод __FooOdata.manager()__.

### method all()
Выполняет запрос, возвращает список валидных объектов сущности. Если один из объектов не валиден будет вызвано 
исключение __pydantic.ValidationError__. Это поведение можно изменить передав параметр __ignor_invalid=True__. 
В этом случае невалидные объекты будут игнорироваться, атрибут __validation_errors__ менеджера будет содержать список 
ошибок валидации. Исключение не будет вызвано.

### method create()
Выполняет запрос. Создает и возвращает новый объект. Принимает обязательный аргумент __data__ - словарь или объект 
__ODataModel__.

### method get()
Выполняет запрос. Возвращает один объект по его GUID. При ошибке валидации будет вызвано исключение
__pydantic.ValidationError__.

### method update()
Выполняет запрос patch для объекта по его GUID. Принимает аргумент __data__ - объект модели данных или словарь с 
обновляемыми данными.

### method post_document()
Выполняет запрос на проведение документа по его GUID. Принимает аргумент __operational_mode__ - оперативный режим 
проведения документа. 

### method unpost_document()
Выполняет запрос отмены проведения документа.

### method expand()
Запрос не выполняет. Устанавливает параметр запроса __$expand__. Принимает позиционные строковые аргументы - имена полей
для которых необходимо получить связанные сущности. Переданные имена полей должны быть объявлены в словаре 
__entity_model.nested_models__

### method filter()
Запрос не выполняет. Устанавливает параметры фильтрации __$filter__. Принимает ключевые аргументы - lookups в стиле
DjangoORM или позиционные аргументы экземпляров __Odata.Q()__. 

Lookup имеет формат field__operator__annotation, где:
field - имя поля модели данных;
operator - оператор eq, ne, gt, ge, lt, le или in, если не указан используется eq;
annotation - аннотация guid или datetime

Примеры:
```python
filter(foo='abc')
filter(bar__gt=100)
filter(uid_1c__in__guid=[...])
```

В качестве field может быть указано поле вложенной модели.
Для этого нужно в модель добавить описание вложенного поля в формате:

model_1__...__model_N__field: Optional<тип поля> = Field(None)

Примеры:
```python
# фильтр по полю name вложенной модели foo
filter(foo__name='name')
# в модели необходимо указать
foo__name: Optional[str] = Field(None)

# фильтр по полю uid_1c (тип поля guid) модели bar, которая вложена в модель foo
filter(foo__bar__uid_1c__in__guid=[...])
# в модели необходимо указать
foo__bar__uid_1c: Optional[UUID1] = Field(None)
```

### method skip()
Запрос не выполняет. Устанавливает параметр запроса __$skip__. Принимает целое число - количество элементов которое 
будет пропущены.

### method top()
Запрос не выполняет. Устанавливает параметр запроса __$top__. Принимает целое число - количество элементов, которое 
будет получено.

## Отладка
Объект класса __ODataManager__ имеет атрибуты __request__ и __response__. После выполнения запроса их значениями будут
объекты классов __PyOData.http.Request__ и requests.Response соответственно. Вы можете использовать это для отладки
своего кода.


```Python
from datetime import datetime
from pprint import pprint

from pydantic import Field, UUID1, field_serializer

from PyOData1C.http import Connection, auth
from PyOData1C.models import ODataModel
from PyOData1C.odata import OData


class StageModel(ODataModel):
    uid_1c: UUID1 = Field(alias='Ref_Key', exclude=True)
    number: str = Field(alias='Number')
    stage_date: datetime = Field(alias='Date')

    @field_serializer('stage_date')
    def serialize_stage_date(self, stage_date: datetime, _info):
        return stage_date.isoformat('T', 'seconds')


class StageOdata(OData):
    database = 'erp_dev'
    entity_model = StageModel
    entity_name = 'Document_ЭтапПроизводства2_2'

with Connection('10.0.0.1',
                'http',
                auth.HTTPBasicAuth('user', 'pass')) as conn:
    manager = StageOdata.manager(conn)
    stage = manager.top(3).all()
    pprint(manager.request)
    pprint(manager.response.json())
```
```python
Request(method='GET',
        relative_url='erp_dev/odata/standard.odata/Document_ЭтапПроизводства2_2',
        query_params={'$select': 'Ref_Key, Number, Date', '$top': 3},
        data=None)
{'odata.metadata': 'http://10.0.0.1/erp_dev/odata/standard.odata/$metadata#Document_ЭтапПроизводства2_2',
 'value': [{'Date': '2021-09-29T10:00:00',
            'Number': 'ПП00-5729.3.1.5',
            'Ref_Key': 'ce52f328-3f1d-11ed-aa45-ac1f6bd30990'},
           {'Date': '2022-01-03T09:47:16',
            'Number': 'ПП00-1.3.1',
            'Ref_Key': 'f75e2f51-6c60-11ec-aa38-ac1f6bd30991'},
           {'Date': '2022-01-03T11:18:44',
            'Number': 'ПП00-26.1.1',
            'Ref_Key': 'ee3c0030-6d36-11ec-aa38-ac1f6bd30991'}]}
```
