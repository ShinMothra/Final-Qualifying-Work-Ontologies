# core/storage/owl_handler.py

import json
import os
import logging
from owlready2 import get_ontology, Thing, SymmetricProperty, TransitiveProperty, FunctionalProperty

from ..model.elements import (
    ClassElement, ObjectPropertyElement, DataPropertyElement, IndividualElement,
    PropertyCharacteristic, DataType, EdgeType
)
from ..model.ontology import OntologyManager

logger = logging.getLogger(__name__)

_EXT_PREFIX  = "__ext__:"
_EDGE_PREFIX = "__edge__:"
_CTX_PREFIX  = "__ctx__:"
_OVR_PREFIX  = "__ovr__:"   # переопределения свойств

# Версия схемы JSON — увеличивать при несовместимых изменениях структуры
_JSON_SCHEMA_VERSION = 1


_PV_PREFIX   = "__pv__:"    # значения атрибутов по умолчанию


def _encode_comments(
    formula: str,
    extension: str,
    edge_type: str = "",
    symbol_context: dict = None,
    overridden_properties: dict = None,
    prop_values: dict = None,
) -> list:
    """Упаковывает метаданные в список комментариев OWL."""
    result = []
    if formula and formula.strip():
        result.append(formula.strip())
    if extension and extension.strip():
        result.append(f"{_EXT_PREFIX}{extension.strip()}")
    if edge_type and edge_type.strip() and edge_type != EdgeType.INHERITS.value:
        result.append(f"{_EDGE_PREFIX}{edge_type.strip()}")
    if symbol_context:
        result.append(f"{_CTX_PREFIX}{json.dumps(symbol_context, ensure_ascii=False)}")
    if overridden_properties:
        serialized = {k: v.to_dict() for k, v in overridden_properties.items()}
        result.append(f"{_OVR_PREFIX}{json.dumps(serialized, ensure_ascii=False)}")
    if prop_values:
        result.append(f"{_PV_PREFIX}{json.dumps(prop_values, ensure_ascii=False)}")
    return result


def _decode_comments(comments: list) -> tuple:
    """Распаковывает метаданные из списка комментариев OWL.
    Возвращает (formula, extension, edge_type, symbol_context, overridden_properties, prop_values).
    """
    from ..model.elements import PropertyOverride
    formula = ""
    extension = ""
    edge_type = ""
    symbol_context = {}
    overridden_properties = {}
    prop_values = {}
    for c in comments:
        if c.startswith(_EXT_PREFIX):
            extension = c[len(_EXT_PREFIX):]
        elif c.startswith(_EDGE_PREFIX):
            edge_type = c[len(_EDGE_PREFIX):]
        elif c.startswith(_CTX_PREFIX):
            try:
                symbol_context = json.loads(c[len(_CTX_PREFIX):])
            except (json.JSONDecodeError, ValueError):
                symbol_context = {}
        elif c.startswith(_OVR_PREFIX):
            try:
                raw = json.loads(c[len(_OVR_PREFIX):])
                overridden_properties = {k: PropertyOverride.from_dict(v) for k, v in raw.items()}
            except (json.JSONDecodeError, ValueError):
                overridden_properties = {}
        elif c.startswith(_PV_PREFIX):
            try:
                prop_values = json.loads(c[len(_PV_PREFIX):])
            except (json.JSONDecodeError, ValueError):
                prop_values = {}
        else:
            formula = c
    return formula, extension, edge_type, symbol_context, overridden_properties, prop_values


# ══════════════════════════════════════════════════════════════════════════════
#  JSON — сериализация / десериализация
# ══════════════════════════════════════════════════════════════════════════════

def _serialize_characteristics(chars: list) -> list[str]:
    return [c.value for c in chars]


def _deserialize_characteristics(values: list[str]) -> list[PropertyCharacteristic]:
    result = []
    for v in values:
        try:
            result.append(PropertyCharacteristic(v))
        except ValueError:
            logger.warning(f"Неизвестная характеристика: '{v}', пропускается")
    return result


def _manager_to_dict(manager: OntologyManager) -> dict:
    """Полная сериализация OntologyManager в словарь."""

    # ── классы ────────────────────────────────────────────────────────────────
    classes = []
    for elem in manager.classes.values():
        classes.append({
            "name":                  elem.name,
            "uri":                   elem.uri,
            "label":                 elem.label,
            "comment":               elem.comment,
            "description":           elem.description,
            "parent":                elem.parent.name if elem.parent else None,
            "edge_type":             elem.edge_type.value,
            "formula":               elem.formula or "",
            "extension":             elem.extension,
            "symbol_context":        elem.symbol_context or {},
            "overridden_properties": {k: v.to_dict() for k, v in (elem.overridden_properties or {}).items()},
            "prop_values":           getattr(elem, 'prop_values', {}) or {},
        })

    # ── data properties ───────────────────────────────────────────────────────
    data_properties = []
    for elem in manager.data_properties.values():
        data_properties.append({
            "name":            elem.name,
            "domain":          elem.domain.name if elem.domain else None,
            "data_type":       elem.data_type.value,
            "characteristics": _serialize_characteristics(elem.characteristics),
            "label":           elem.label,
            "comment":         elem.comment,
            "description":     elem.description,
        })

    # ── object properties ─────────────────────────────────────────────────────
    object_properties = []
    for elem in manager.object_properties.values():
        object_properties.append({
            "name":            elem.name,
            "domain":          elem.domain.name if elem.domain else None,
            "range":           elem.range_.name if elem.range_ else None,
            "characteristics": _serialize_characteristics(elem.characteristics),
            "label":           elem.label,
            "comment":         elem.comment,
            "description":     elem.description,
        })

    # ── individuals ───────────────────────────────────────────────────────────
    individuals = []
    for elem in manager.individuals.values():
        individuals.append({
            "name":                  elem.name,
            "classes":               [c.name for c in elem.classes],
            "label":                 elem.label,
            "comment":               elem.comment,
            "formula":               elem.formula or "",
            "symbol_context":        elem.symbol_context or {},
            "data_assertions":       elem.data_assertions,
            "object_assertions":     elem.object_assertions,
            "overridden_properties": {k: v.to_dict() for k, v in (elem.overridden_properties or {}).items()},
        })

    return {
        "schema_version": _JSON_SCHEMA_VERSION,
        "iri":            manager.onto.base_iri if manager.onto else "http://example.org/myontology#",
        "classes":            classes,
        "data_properties":    data_properties,
        "object_properties":  object_properties,
        "individuals":        individuals,
    }


def _manager_from_dict(data: dict, manager: OntologyManager = None) -> OntologyManager:
    """Полная десериализация словаря в OntologyManager."""
    if manager is None:
        iri = data.get("iri", "http://example.org/myontology#")
        manager = OntologyManager(iri=iri)

    manager.classes.clear()
    manager.object_properties.clear()
    manager.data_properties.clear()
    manager.individuals.clear()
    manager.extensions.clear()

    schema_version = data.get("schema_version", 1)
    if schema_version > _JSON_SCHEMA_VERSION:
        logger.warning(
            f"JSON схема версии {schema_version} новее, чем поддерживаемая "
            f"({_JSON_SCHEMA_VERSION}). Возможна частичная потеря данных."
        )

    # ── первый проход: создаём ClassElement без родителей ─────────────────────
    for c in data.get("classes", []):
        try:
            edge_type = EdgeType(c.get("edge_type", EdgeType.INHERITS.value))
        except ValueError:
            edge_type = EdgeType.INHERITS

        from ..model.elements import PropertyOverride as _PO
        ovr_raw = c.get("overridden_properties", {})
        overridden = {k: _PO.from_dict(v) for k, v in ovr_raw.items()}
        elem = ClassElement(
            name=c["name"],
            uri=c.get("uri"),
            label=c.get("label"),
            comment=c.get("comment"),
            description=c.get("description", ""),
            parent=None,
            edge_type=edge_type,
            formula=c.get("formula", ""),
            extension=c.get("extension"),
            symbol_context=c.get("symbol_context", {}),
            overridden_properties=overridden,
        )
        elem.prop_values = c.get("prop_values", {})
        manager.classes[elem.name] = elem

    # ── второй проход: привязываем родителей и children ───────────────────────
    for c in data.get("classes", []):
        elem = manager.classes.get(c["name"])
        if not elem:
            continue
        parent_name = c.get("parent")
        if parent_name and parent_name in manager.classes:
            parent = manager.classes[parent_name]
            elem.parent = parent
            if elem not in parent.children:
                parent.children.append(elem)
        if elem.extension and elem.parent:
            manager.register_extension(elem.extension, elem.name)

    # ── data properties ───────────────────────────────────────────────────────
    for dp in data.get("data_properties", []):
        try:
            data_type = DataType(dp.get("data_type", DataType.STRING.value))
        except ValueError:
            data_type = DataType.STRING

        domain = manager.classes.get(dp.get("domain"))
        if domain is None:
            logger.warning(f"DataProperty '{dp['name']}': домен '{dp.get('domain')}' не найден, пропускается")
            continue

        elem = DataPropertyElement(
            name=dp["name"],
            domain=domain,
            data_type=data_type,
            characteristics=_deserialize_characteristics(dp.get("characteristics", [])),
            label=dp.get("label"),
            comment=dp.get("comment"),
            description=dp.get("description"),
        )
        manager.data_properties[elem.name] = elem

    # ── object properties ─────────────────────────────────────────────────────
    for op in data.get("object_properties", []):
        domain = manager.classes.get(op.get("domain"))
        range_ = manager.classes.get(op.get("range"))

        if domain is None:
            logger.warning(f"ObjectProperty '{op['name']}': домен '{op.get('domain')}' не найден, пропускается")
            continue
        if range_ is None:
            logger.warning(f"ObjectProperty '{op['name']}': диапазон '{op.get('range')}' не найден, пропускается")
            continue

        elem = ObjectPropertyElement(
            name=op["name"],
            domain=domain,
            range_=range_,
            characteristics=_deserialize_characteristics(op.get("characteristics", [])),
            label=op.get("label"),
            comment=op.get("comment"),
            description=op.get("description", ""),
        )
        manager.object_properties[elem.name] = elem

    # ── individuals ───────────────────────────────────────────────────────────
    for ind in data.get("individuals", []):
        classes = []
        for cls_name in ind.get("classes", []):
            cls = manager.classes.get(cls_name)
            if cls:
                classes.append(cls)
            else:
                logger.warning(f"Individual '{ind['name']}': класс '{cls_name}' не найден")

        from ..model.elements import PropertyOverride as _PO
        ovr_raw = ind.get("overridden_properties", {})
        overridden = {k: _PO.from_dict(v) for k, v in ovr_raw.items()}
        elem = IndividualElement(
            name=ind["name"],
            classes=classes,
            label=ind.get("label", ind["name"]),
            comment=ind.get("comment", ""),
            formula=ind.get("formula", ""),
            symbol_context=ind.get("symbol_context", {}),
            overridden_properties=overridden,
        )
        elem.data_assertions   = ind.get("data_assertions", {})
        elem.object_assertions = ind.get("object_assertions", {})
        manager.individuals[elem.name] = elem

    # ── создаём реальные owlready2-сущности под загруженной моделью ───────────
    # Без этого manager.onto остаётся пустым (только Thing), и save_ontology
    # сохраняет файл без классов/свойств/индивидов.
    _rebuild_owl_entities(manager)

    logger.info(
        f"JSON загружен: {len(manager.classes)} классов, "
        f"{len(manager.object_properties)} объектных свойств, "
        f"{len(manager.data_properties)} data-свойств, "
        f"{len(manager.individuals)} индивидов"
    )
    return manager


def _rebuild_owl_entities(manager: OntologyManager) -> None:
    """
    Материализует owlready2-сущности (классы, свойства, индивиды) в manager.onto
    на основе уже заполненной Python-модели (manager.classes/data_properties/
    object_properties/individuals).

    Вызывается после _manager_from_dict (загрузка из JSON), так как там
    создаются только Python-объекты модели — без этого save_ontology не
    находит сущности через _get_owl_entity и сохраняет пустой OWL-файл.
    """
    # Классы — от корня к листьям, иначе _get_owl_entity(parent) вернёт None
    classes_sorted = sorted(
        manager.classes.values(),
        key=lambda e: len(e.get_ancestor_chain())
    )
    for elem in classes_sorted:
        if manager.onto[elem.name] is not None:
            continue
        manager.create_class(elem)

    # Data properties — после классов, т.к. нужен domain
    for elem in manager.data_properties.values():
        if manager.onto[elem.name] is not None:
            continue
        manager.create_data_property(elem)

    # Object properties — после классов, т.к. нужны domain и range
    for elem in manager.object_properties.values():
        if manager.onto[elem.name] is not None:
            continue
        manager.create_object_property(elem)

    # Индивиды
    for elem in manager.individuals.values():
        if manager.onto[elem.name] is not None:
            continue
        manager.create_individual(elem)

    # Восстанавливаем значения свойств индивидов (data/object assertions)
    with manager.onto:
        for elem in manager.individuals.values():
            ind = manager.onto[elem.name]
            if ind is None:
                continue

            for prop_name, value in (elem.data_assertions or {}).items():
                if manager.onto[prop_name] is None:
                    continue
                try:
                    setattr(ind, prop_name, value)
                except Exception as e:
                    logger.warning(
                        f"Не удалось восстановить data assertion "
                        f"{elem.name}.{prop_name} = {value!r}: {e}"
                    )

            for prop_name, target_names in (elem.object_assertions or {}).items():
                if manager.onto[prop_name] is None:
                    continue
                targets = [
                    manager.onto[t] for t in (target_names or [])
                    if manager.onto[t] is not None
                ]
                if not targets:
                    continue
                try:
                    setattr(ind, prop_name, targets)
                except Exception as e:
                    logger.warning(
                        f"Не удалось восстановить object assertion "
                        f"{elem.name}.{prop_name} = {target_names!r}: {e}"
                    )


# ══════════════════════════════════════════════════════════════════════════════
#  OWLHandler
# ══════════════════════════════════════════════════════════════════════════════

class OWLHandler:

    # ── OWL load / save ───────────────────────────────────────────────────────

    @staticmethod
    def load_ontology(filename: str, manager: OntologyManager = None) -> OntologyManager:
        if manager is None:
            manager = OntologyManager()

        onto = get_ontology(f"file://{filename}").load()
        manager.onto = onto

        manager.classes.clear()
        manager.object_properties.clear()
        manager.data_properties.clear()
        manager.individuals.clear()
        manager.extensions.clear()

        with onto:
            # === Классы ===
            for owl_class in onto.classes():
                if owl_class is Thing or owl_class.name == "Thing":
                    continue

                parent = None
                if (owl_class.is_a and
                    owl_class.is_a[0] is not Thing and
                    owl_class.is_a[0] is not owl_class):
                    parent_name = owl_class.is_a[0].name
                    parent = ClassElement(name=parent_name)

                comments = list(owl_class.comment) if owl_class.comment else []
                formula, extension, edge_type_str, symbol_context, overridden_properties, prop_values = _decode_comments(comments)

                try:
                    edge_type = EdgeType(edge_type_str) if edge_type_str else EdgeType.INHERITS
                except ValueError:
                    edge_type = EdgeType.INHERITS

                elem = ClassElement(
                    name=owl_class.name,
                    uri=str(owl_class.iri),
                    description=getattr(owl_class, "__doc__", "") or "",
                    label=owl_class.label[0] if owl_class.label else None,
                    comment=None,
                    parent=parent,
                    edge_type=edge_type,
                    formula=formula,
                    extension=extension or None,
                    symbol_context=symbol_context,
                    overridden_properties=overridden_properties,
                )
                elem.prop_values = prop_values
                manager.classes[owl_class.name] = elem

            # Второй проход — связываем родителей и регистрируем расширения
            for owl_class in onto.classes():
                if owl_class.name not in manager.classes or owl_class is Thing:
                    continue
                elem = manager.classes[owl_class.name]
                if (owl_class.is_a and
                    owl_class.is_a[0] is not Thing and
                    owl_class.is_a[0].name in manager.classes):
                    parent_name = owl_class.is_a[0].name
                    elem.parent = manager.classes[parent_name]
                    if elem not in manager.classes[parent_name].children:
                        manager.classes[parent_name].children.append(elem)

                if elem.extension and elem.parent:
                    manager.register_extension(elem.extension, elem.name)

            # === Object Properties ===
            for prop in onto.object_properties():
                if not prop.domain or not prop.range:
                    continue

                domain_cls = prop.domain[0] if isinstance(prop.domain, (list, tuple)) else prop.domain
                range_cls  = prop.range[0]  if isinstance(prop.range,  (list, tuple)) else prop.range

                characteristics = []
                if isinstance(prop, TransitiveProperty) or any(
                        isinstance(base, TransitiveProperty) for base in prop.mro()):
                    characteristics.append(PropertyCharacteristic.TRANSITIVE)
                if any(isinstance(base, SymmetricProperty) for base in prop.mro()):
                    characteristics.append(PropertyCharacteristic.SYMMETRIC)
                if any(isinstance(base, FunctionalProperty) for base in prop.mro()):
                    characteristics.append(PropertyCharacteristic.FUNCTIONAL)

                elem = ObjectPropertyElement(
                    name=prop.name,
                    domain=manager.classes.get(getattr(domain_cls, 'name', None)),
                    range_=manager.classes.get(getattr(range_cls, 'name', None)),
                    characteristics=characteristics,
                    label=prop.label[0] if hasattr(prop, 'label') and prop.label else None,
                    comment=prop.comment[0] if hasattr(prop, 'comment') and prop.comment else None
                )
                manager.object_properties[prop.name] = elem

            # === Data Properties ===
            for prop in onto.data_properties():
                if not prop.domain:
                    continue

                domain_cls = prop.domain[0] if isinstance(prop.domain, (list, tuple)) else prop.domain

                range_type = DataType.STRING
                if prop.range:
                    r = prop.range[0] if isinstance(prop.range, (list, tuple)) else prop.range
                    if r == str:     range_type = DataType.STRING
                    elif r == int:   range_type = DataType.INTEGER
                    elif r == float: range_type = DataType.FLOAT
                    elif r == bool:  range_type = DataType.BOOLEAN

                characteristics = [PropertyCharacteristic.FUNCTIONAL] if any(
                    isinstance(base, FunctionalProperty) for base in prop.mro()) else []

                elem = DataPropertyElement(
                    name=prop.name,
                    domain=manager.classes.get(getattr(domain_cls, 'name', None)),
                    data_type=range_type,
                    characteristics=characteristics,
                    label=prop.label[0] if hasattr(prop, 'label') and prop.label else None,
                    comment=prop.comment[0] if hasattr(prop, 'comment') and prop.comment else None
                )
                manager.data_properties[prop.name] = elem

            # === Individuals ===
            for ind in onto.individuals():
                classes = []
                for c in ind.is_a:
                    if hasattr(c, 'name') and c.name in manager.classes:
                        classes.append(manager.classes[c.name])

                comments = list(ind.comment) if hasattr(ind, 'comment') and ind.comment else []
                formula, _, _, symbol_context, overridden_properties, _ = _decode_comments(comments)

                elem = IndividualElement(
                    name=ind.name,
                    classes=classes,
                    label=ind.label[0] if hasattr(ind, 'label') and ind.label else ind.name,
                    comment="",
                    formula=formula,
                    symbol_context=symbol_context,
                    overridden_properties=overridden_properties,
                )
                manager.individuals[ind.name] = elem

        logger.info(
            f"Успешно загружен OWL: {len(manager.classes)} классов, "
            f"{len(manager.object_properties)} объектных свойств, "
            f"{len(manager.data_properties)} data-свойств, "
            f"{len(manager.individuals)} индивидов, "
            f"{len(manager.extensions)} расширений"
        )
        return manager

    @staticmethod
    def save_ontology(manager: OntologyManager, filename: str, format_: str = "rdfxml") -> str:
        try:
            os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

            with manager.onto:
                for cls_name, elem in manager.classes.items():
                    owl_class = manager._get_owl_entity(elem)
                    if owl_class:
                        encoded = _encode_comments(
                            elem.formula or "",
                            elem.extension or "",
                            elem.edge_type.value if elem.edge_type else "",
                            elem.symbol_context or {},
                            elem.overridden_properties or {},
                            getattr(elem, 'prop_values', {}) or {},
                        )
                        owl_class.comment = encoded

                for ind_name, elem in manager.individuals.items():
                    owl_ind = manager.onto[ind_name]
                    if owl_ind:
                        encoded = _encode_comments(
                            elem.formula or "",
                            "",
                            "",
                            elem.symbol_context or {},
                            elem.overridden_properties or {},
                        )
                        owl_ind.comment = encoded

            manager.onto.save(file=filename, format=format_)

            size = os.path.getsize(filename) if os.path.exists(filename) else 0
            logger.info(f"Онтология сохранена: {filename} ({size} байт, формат: {format_})")

            if size == 0:
                logger.warning("Предупреждение: сохранённый файл пустой!")

            return f"Сохранено в {filename} ({size} байт)"

        except Exception as e:
            logger.error(f"Ошибка при сохранении онтологии в {filename}: {e}")
            raise

    # ── JSON load / save ──────────────────────────────────────────────────────

    @staticmethod
    def save_json(manager: OntologyManager, filename: str) -> str:
        """Экспорт онтологии в JSON с полным сохранением модели (round-trip)."""
        try:
            os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
            data = _manager_to_dict(manager)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            size = os.path.getsize(filename)
            logger.info(f"JSON сохранён: {filename} ({size} байт)")
            return f"Сохранено в {filename} ({size} байт)"
        except Exception as e:
            logger.error(f"Ошибка при сохранении JSON в {filename}: {e}")
            raise

    @staticmethod
    def load_json(filename: str, manager: OntologyManager = None) -> OntologyManager:
        """Импорт онтологии из JSON (полный round-trip)."""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _manager_from_dict(data, manager)
        except Exception as e:
            logger.error(f"Ошибка при загрузке JSON из {filename}: {e}")
            raise
