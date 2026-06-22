from typing import List, Optional, Dict, Any
from enum import Enum


class EdgeType(Enum):
    INHERITS = "inherits"
    EXTENDS = "extends"


class DataType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


class PropertyCharacteristic(Enum):
    TRANSITIVE = "transitive"
    SYMMETRIC = "symmetric"
    FUNCTIONAL = "functional"
    INVERSE_FUNCTIONAL = "inverse_functional"
    REFLEXIVE = "reflexive"
    IRREFLEXIVE = "irreflexive"
    ASYMMETRIC = "asymmetric"


class PropertyOverride:
    """
    Описывает переопределение унаследованного свойства.

    Поля:
      excluded   — True если свойство явно исключено (пингвин не летает)
      data_type  — переопределённый тип данных (None = берём от родителя)
      value      — значение по умолчанию для данного класса/индивида
      comment    — пояснение к переопределению
    """
    def __init__(
        self,
        excluded: bool = False,
        data_type: Optional['DataType'] = None,
        value: Any = None,
        comment: str = ""
    ):
        self.excluded  = excluded
        self.data_type = data_type
        self.value     = value
        self.comment   = comment

    def to_dict(self) -> dict:
        return {
            "excluded":  self.excluded,
            "data_type": self.data_type.value if self.data_type else None,
            "value":     self.value,
            "comment":   self.comment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'PropertyOverride':
        dt = None
        if d.get("data_type"):
            try:
                dt = DataType(d["data_type"])
            except ValueError:
                pass
        return cls(
            excluded=d.get("excluded", False),
            data_type=dt,
            value=d.get("value"),
            comment=d.get("comment", ""),
        )

    def __repr__(self):
        if self.excluded:
            return "PropertyOverride(excluded)"
        parts = []
        if self.data_type:
            parts.append(f"type={self.data_type.value}")
        if self.value is not None:
            parts.append(f"value={self.value!r}")
        if self.comment:
            parts.append(f"comment={self.comment!r}")
        return f"PropertyOverride({', '.join(parts)})"


class ClassElement:
    def __init__(
            self,
            name: str,
            uri: Optional[str] = None,
            description: str = "",
            label: Optional[str] = None,
            comment: Optional[str] = None,
            parent: Optional['ClassElement'] = None,
            edge_type: EdgeType = EdgeType.INHERITS,
            formula: str = "",
            extension: Optional[str] = None,
            symbol_context: Optional[Dict[str, Dict[str, str]]] = None,
            overridden_properties: Optional[Dict[str, 'PropertyOverride']] = None,
    ):
        self.name = name
        self.uri = uri
        self.description = description
        self.label = label
        self.comment = comment
        self.parent = parent
        self.edge_type = edge_type
        self.formula = formula
        self.extension = extension
        self.symbol_context: Dict[str, Dict[str, str]] = symbol_context or {}
        self.children: List['ClassElement'] = []
        self.own_data_properties: List[Any] = []
        self.own_object_properties: List[Any] = []
        self.overridden_properties: Dict[str, 'PropertyOverride'] = overridden_properties or {}
        self.prop_values: Dict[str, str] = {}

    def get_ancestor_chain(self) -> List['ClassElement']:
        chain: List['ClassElement'] = []
        visited: set = set()
        current = self.parent
        while current is not None:
            if current.name in visited:
                break
            visited.add(current.name)
            chain.append(current)
            current = current.parent
        return chain

    def get_inherited_data_properties(self, all_data_props: Dict[str, Any]) -> List[Any]:
        inherited: List[Any] = []
        seen: set = set()
        for ancestor in self.get_ancestor_chain():
            for dp in all_data_props.values():
                if dp.domain and dp.domain.name == ancestor.name and dp.name not in seen:
                    seen.add(dp.name)
                    inherited.append(dp)
        return inherited

    def get_inherited_object_properties(self, all_obj_props: Dict[str, Any]) -> List[Any]:
        inherited: List[Any] = []
        seen: set = set()
        for ancestor in self.get_ancestor_chain():
            for op in all_obj_props.values():
                if op.domain and op.domain.name == ancestor.name and op.name not in seen:
                    seen.add(op.name)
                    inherited.append(op)
        return inherited

    def get_all_data_properties(self, all_data_props: Dict[str, Any]) -> List[Any]:
        own = [dp for dp in all_data_props.values()
               if dp.domain and dp.domain.name == self.name]
        inherited = self.get_inherited_data_properties(all_data_props)
        own_names = {dp.name for dp in own}
        return own + [dp for dp in inherited if dp.name not in own_names]

    def get_all_object_properties(self, all_obj_props: Dict[str, Any]) -> List[Any]:
        own = [op for op in all_obj_props.values()
               if op.domain and op.domain.name == self.name]
        inherited = self.get_inherited_object_properties(all_obj_props)
        own_names = {op.name for op in own}
        return own + [op for op in inherited if op.name not in own_names]

    def get_effective_data_properties(self, all_data_props: Dict[str, Any]) -> List[Any]:
        """Все data properties с учётом исключений через overridden_properties."""
        return [
            dp for dp in self.get_all_data_properties(all_data_props)
            if not self.overridden_properties.get(dp.name, PropertyOverride()).excluded
        ]

    def get_effective_object_properties(self, all_obj_props: Dict[str, Any]) -> List[Any]:
        return [
            op for op in self.get_all_object_properties(all_obj_props)
            if not self.overridden_properties.get(op.name, PropertyOverride()).excluded
        ]

    def is_property_excluded(self, prop_name: str) -> bool:
        ov = self.overridden_properties.get(prop_name)
        return ov is not None and ov.excluded

    def is_property_overridden(self, prop_name: str) -> bool:
        return prop_name in self.overridden_properties

    def set_override(self, prop_name: str, override: 'PropertyOverride'):
        self.overridden_properties[prop_name] = override

    def remove_override(self, prop_name: str):
        self.overridden_properties.pop(prop_name, None)


class ObjectPropertyElement:
    def __init__(
            self,
            name: str,
            domain: Any,
            range_: Any,
            characteristics: List[PropertyCharacteristic] = None,
            label: Optional[str] = None,
            comment: Optional[str] = None,
            description: str = ""
    ):
        self.name = name
        self.domain = domain
        self.range_ = range_
        self.characteristics = characteristics or []
        self.label = label
        self.comment = comment
        self.description = description


class DataPropertyElement:
    def __init__(
            self,
            name: str,
            domain: Any,
            data_type: 'DataType',
            characteristics: List[PropertyCharacteristic] = None,
            label: Optional[str] = None,
            comment: Optional[str] = None,
            description: Optional[str] = None
    ):
        self.name = name
        self.domain = domain
        self.data_type = data_type
        self.characteristics = characteristics or []
        self.label = label
        self.comment = comment
        self.description = description


class IndividualElement:
    def __init__(
            self,
            name: str,
            classes: List[ClassElement],
            label: Optional[str] = None,
            comment: Optional[str] = None,
            formula: str = "",
            symbol_context: Optional[Dict[str, Dict[str, str]]] = None,
            overridden_properties: Optional[Dict[str, 'PropertyOverride']] = None,
    ):
        self.name = name
        self.classes = classes
        self.label = label or name
        self.comment = comment or ""
        self.formula = formula
        self.symbol_context: Dict[str, Dict[str, str]] = symbol_context or {}
        self.data_assertions: Dict[str, Any] = {}
        self.object_assertions: Dict[str, List[str]] = {}
        self.overridden_properties: Dict[str, 'PropertyOverride'] = overridden_properties or {}

    def get_all_data_properties(self, all_data_props: Dict[str, Any]) -> List[Any]:
        seen: set = set()
        result: List[Any] = []
        for cls in self.classes:
            for dp in cls.get_all_data_properties(all_data_props):
                if dp.name not in seen:
                    seen.add(dp.name)
                    result.append(dp)
        return result

    def get_all_object_properties(self, all_obj_props: Dict[str, Any]) -> List[Any]:
        seen: set = set()
        result: List[Any] = []
        for cls in self.classes:
            for op in cls.get_all_object_properties(all_obj_props):
                if op.name not in seen:
                    seen.add(op.name)
                    result.append(op)
        return result

    def get_effective_data_properties(self, all_data_props: Dict[str, Any]) -> List[Any]:
        return [
            dp for dp in self.get_all_data_properties(all_data_props)
            if not self.overridden_properties.get(dp.name, PropertyOverride()).excluded
        ]

    def get_effective_object_properties(self, all_obj_props: Dict[str, Any]) -> List[Any]:
        return [
            op for op in self.get_all_object_properties(all_obj_props)
            if not self.overridden_properties.get(op.name, PropertyOverride()).excluded
        ]

    def is_property_excluded(self, prop_name: str) -> bool:
        ov = self.overridden_properties.get(prop_name)
        return ov is not None and ov.excluded

    def set_override(self, prop_name: str, override: 'PropertyOverride'):
        self.overridden_properties[prop_name] = override

    def remove_override(self, prop_name: str):
        self.overridden_properties.pop(prop_name, None)