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
from PyOData1C.models import OdataModel
from PyOData1C.odata import OData
from pydantic import Field, UUID1


class MeasureUnitModel(OdataModel):
    uid: UUID1 = Field(alias='Ref_Key', exclude=True)
    name: str = Field(alias='Description', max_length=6)


class NomenclatureModel(OdataModel):
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
    nomenclatures: list[OdataModel] = (NomenclatureOdata
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


### class models.OdataModel
Класс models.OdataModel наследуется от класса pydantic.Basemodel. Ваши модели данных должны наследоваться от этого 
класса. Вы можете использовать обширные возможности Pydantic для валидации данных.

models.OdataModel.nested_models

Атрибут nested_models используется для оптимизации запросов OData. Представляет собой словарь ключи которого - строки с
именами полей содержащих вложенные модели, значения - вложенные модели.

```python
class MyModel(OdataModel):
    ...
    nested_models = {
        'measure_unit': MyNestedModel
    }
```

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
__OdataModel__.

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
Запрос не выполняет. Устанавливает параметры фильтрации __$filter__. Принимает ключевые аргументы - lookups в стиле DjangoORM или 
позиционные аргументы экземпляров __Odata.Q()__. 

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

### method skip()
Запрос не выполняет. Устанавливает параметр запроса __$skip__. Принимает целое число - количество элементов которое 
будет пропущены.

### method top()
Запрос не выполняет. Устанавливает параметр запроса __$top__. Принимает целое число - количество элементов, которое 
будет получено.
