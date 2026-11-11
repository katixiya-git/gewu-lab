"""Schema 公共基类：统一 JSON 风格（camelCase）与 ORM 转换。"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Python 侧用 snake_case，序列化成 JSON 时自动转 camelCase。

    - `from_attributes=True`：可直接用 ORM 对象构造（`UserOut.model_validate(user)`）
    - `populate_by_name=True`：构造时 snake_case / camelCase 都收
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
