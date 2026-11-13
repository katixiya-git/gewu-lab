"""Schema 公共基类：统一 JSON 风格（camelCase）与 ORM 转换。"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Python 侧用 snake_case，序列化成 JSON 时自动转 camelCase。

    - ``alias_generator=to_camel``：``access_token`` 输出为 ``accessToken``
    - ``from_attributes=True``：可直接用 ORM 对象构造（``UserOut.model_validate(user)``）
    - ``populate_by_name=True``：构造时 snake_case / camelCase 两种写法都收

    注意：手动 ``model_dump()`` 默认仍输出 snake_case，需要 camelCase 时
    传 ``by_alias=True``；FastAPI 的 ``response_model`` 会自动用 alias。
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
