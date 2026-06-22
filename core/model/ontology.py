from owlready2 import (
    get_ontology, Thing, ObjectProperty, DataProperty, default_world,
    TransitiveProperty, SymmetricProperty, FunctionalProperty,
    InverseFunctionalProperty, ReflexiveProperty, IrreflexiveProperty,
    AsymmetricProperty, types, destroy_entity, sync_reasoner
)
from .elements import (
    ClassElement, ObjectPropertyElement, DataPropertyElement,
    PropertyCharacteristic, EdgeType, DataType, IndividualElement
)
from typing import Set, Dict, List
import traceback


class OntologyManager:
    def __init__(self, iri: str = "http://example.org/myontology#"):
        self.onto = get_ontology(iri)
        with self.onto:
            self.thing = Thing
        self.classes: Dict[str, ClassElement] = {}
        self.object_properties: Dict[str, ObjectPropertyElement] = {}
        self.data_properties: Dict[str, DataPropertyElement] = {}
        self.individuals: Dict[str, IndividualElement] = {}
        self.extensions: Dict[str, List[str]] = {}

    def _get_owl_entity(self, elem) -> any:
        if hasattr(elem, 'uri') and elem.uri:
            entity = self.onto.search_one(iri=elem.uri)
            if entity:
                return entity
        # getattr не работает для имён с дефисами, пробелами и спецсимволами —
        # используем self.onto[name] как надёжный fallback
        result = getattr(self.onto, elem.name, None)
        if result is not None:
            return result
        return self.onto[elem.name]

    # ====================== РАСШИРЕНИЯ ======================

    def register_extension(self, extension_name: str, class_name: str) -> None:
        if extension_name not in self.extensions:
            self.extensions[extension_name] = []
        if class_name not in self.extensions[extension_name]:
            self.extensions[extension_name].append(class_name)

    def unregister_extension(self, class_name: str) -> None:
        for ext_name, members in self.extensions.items():
            if class_name in members:
                members.remove(class_name)
        self.extensions = {k: v for k, v in self.extensions.items() if v}

    def get_extensions_for_parent(self, parent_name: str) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for name, elem in self.classes.items():
            if elem.parent and elem.parent.name == parent_name:
                key = elem.extension
                result.setdefault(key, []).append(name)
        return result

    def get_all_extension_names(self) -> List[str]:
        return sorted(self.extensions.keys())

    # ====================== РАБОТА С ФОРМУЛАМИ ======================

    def set_formula(self, name: str, formula_str: str):
        if name in self.classes:
            self.classes[name].formula = formula_str
            entity = self._get_owl_entity(self.classes[name])
        elif name in self.individuals:
            self.individuals[name].formula = formula_str
            entity = self._get_owl_entity(self.individuals[name])
        else:
            print(f"[WARNING] Элемент {name} не найден")
            return

        if entity and formula_str.strip():
            with self.onto:
                entity.comment = [formula_str]

    def get_formula(self, name: str) -> str:
        if name in self.classes:
            return self.classes[name].formula
        if name in self.individuals:
            return self.individuals[name].formula
        return ""

    # ====================== СОЗДАНИЕ ЭЛЕМЕНТОВ ======================

    def create_class(self, elem: ClassElement) -> None:
        try:
            print(f"Создание класса: {elem.name}")
            with self.onto:
                parent = self.thing if not elem.parent else self._get_owl_entity(elem.parent)
                new_class = type(elem.name, (parent,), {"__doc__": elem.description})
                if elem.uri:
                    new_class.iri = elem.uri
                if elem.label:
                    new_class.label = [elem.label]
                if elem.comment:
                    new_class.comment = [elem.comment]
                if elem.formula:
                    new_class.comment = [elem.formula]

            self.classes[elem.name] = elem

            # Связываем с родителем
            if elem.parent and elem.parent.name in self.classes:
                real_parent = self.classes[elem.parent.name]
                elem.parent = real_parent
                if elem not in real_parent.children:
                    real_parent.children.append(elem)

            # Регистрируем расширение если указано
            if elem.extension and elem.parent:
                self.register_extension(elem.extension, elem.name)

        except Exception as e:
            print(f"Ошибка в create_class: {e}")
            traceback.print_exc()
            raise

    def create_object_property(self, elem: ObjectPropertyElement) -> None:
        try:
            print(f"Создание отношения: {elem.name}")

            domain_entity = self._get_owl_entity(elem.domain)
            range_entity = self._get_owl_entity(elem.range_)

            if not domain_entity or not range_entity:
                raise ValueError("Домен или диапазон не найден")

            with self.onto:
                bases = [ObjectProperty]
                for char in elem.characteristics:
                    if char == PropertyCharacteristic.TRANSITIVE:
                        bases.append(TransitiveProperty)
                    elif char == PropertyCharacteristic.SYMMETRIC:
                        bases.append(SymmetricProperty)
                    elif char == PropertyCharacteristic.FUNCTIONAL:
                        bases.append(FunctionalProperty)
                    elif char == PropertyCharacteristic.INVERSE_FUNCTIONAL:
                        bases.append(InverseFunctionalProperty)
                    elif char == PropertyCharacteristic.REFLEXIVE:
                        bases.append(ReflexiveProperty)
                    elif char == PropertyCharacteristic.IRREFLEXIVE:
                        bases.append(IrreflexiveProperty)
                    elif char == PropertyCharacteristic.ASYMMETRIC:
                        bases.append(AsymmetricProperty)

                prop = type(elem.name, tuple(bases), {})
                prop.domain = [domain_entity]
                prop.range = [range_entity]

                if elem.label:
                    prop.label = [elem.label]
                if elem.comment:
                    prop.comment = [elem.comment]
                if elem.description:
                    prop.__doc__ = elem.description

            self.object_properties[elem.name] = elem
        except Exception as e:
            print(f"Ошибка в create_object_property: {e}")
            traceback.print_exc()
            raise

    def create_data_property(self, elem: DataPropertyElement) -> None:
        try:
            print(f"Создание свойства: {elem.name}")
            domain_entity = self._get_owl_entity(elem.domain)

            with self.onto:
                range_type = {
                    DataType.STRING: str,
                    DataType.INTEGER: int,
                    DataType.FLOAT: float,
                    DataType.BOOLEAN: bool
                }[elem.data_type]

                bases = [DataProperty]
                if PropertyCharacteristic.FUNCTIONAL in elem.characteristics:
                    bases.append(FunctionalProperty)

                prop = type(elem.name, tuple(bases), {})
                prop.domain = [domain_entity]
                prop.range = [range_type]

                if elem.label:
                    prop.label = [elem.label]
                if elem.comment:
                    prop.comment = [elem.comment]
                if elem.description:
                    prop.__doc__ = elem.description

            self.data_properties[elem.name] = elem
        except Exception as e:
            print(f"Ошибка в create_data_property: {e}")
            traceback.print_exc()
            raise

    def create_individual(self, elem: IndividualElement) -> None:
        try:
            print(f"Создание индивида: {elem.name}")
            with self.onto:
                owl_classes = []
                for cls_elem in elem.classes:
                    owl_class = self._get_owl_entity(cls_elem)
                    if owl_class and issubclass(owl_class, Thing):
                        owl_classes.append(owl_class)

                if not owl_classes:
                    owl_classes = [Thing]

                ind = owl_classes[0](elem.name)
                if len(owl_classes) > 1:
                    ind.is_a.extend(owl_classes[1:])

                if elem.label and elem.label != elem.name:
                    ind.label = [elem.label]
                if elem.comment:
                    ind.comment = [elem.comment]
                if elem.formula:
                    ind.comment = [elem.formula]

            self.individuals[elem.name] = elem
            print(f"Индивид {elem.name} создан → принадлежит к: {[c.name for c in owl_classes]}")
        except Exception as e:
            print(f"Ошибка при создании индивида {elem.name}: {e}")
            traceback.print_exc()
            raise

    # ====================== ОБНОВЛЕНИЕ И УДАЛЕНИЕ ======================

    def update_individual(self, old_name: str, new_elem: IndividualElement) -> None:
        try:
            self.delete_individual(old_name)
            self.create_individual(new_elem)
        except Exception as e:
            print(f"Ошибка в update_individual: {e}")
            traceback.print_exc()
            raise

    def delete_individual(self, name: str) -> bool:
        try:
            if name not in self.individuals:
                return False
            del self.individuals[name]
            with self.onto:
                ind = self.onto[name]
                if ind:
                    destroy_entity(ind)
            return True
        except Exception as e:
            print(f"Ошибка в delete_individual: {e}")
            traceback.print_exc()
            return False

    def update_class(self, old_name: str, new_elem: ClassElement) -> None:
        try:
            print(f"[update_class] Начало обновления {old_name} → {new_elem.name}")

            new_name = new_elem.name.strip()

            # Ищем OWL-сущность — может отсутствовать если онтология загружена из JSON
            existing_elem = self.classes.get(old_name)
            old_owl_class = None
            if existing_elem:
                old_owl_class = self._get_owl_entity(existing_elem)
            if old_owl_class is None:
                old_owl_class = self.onto[old_name]

            if old_owl_class is not None:
                # OWL-сущность найдена — обновляем её
                old_comments = list(old_owl_class.comment or [])

                with self.onto:
                    # 1. Переименование
                    if old_name != new_name:
                        print(f"  → Переименование: {old_name} → {new_name}")
                        old_owl_class.name = new_name

                    # 2. Обновление родителя в OWL
                    if new_elem.parent:
                        new_parent_owl = self._get_owl_entity(new_elem.parent)
                        if new_parent_owl:
                            old_owl_class.is_a = [new_parent_owl] + [
                                c for c in old_owl_class.is_a if c != self.thing
                            ]
                    else:
                        old_owl_class.is_a = [self.thing] + [
                            c for c in old_owl_class.is_a if c != self.thing
                        ]

                    # 3. Метаданные
                    if new_elem.label is not None:
                        old_owl_class.label = [new_elem.label] if new_elem.label else []
                    if new_elem.description is not None:
                        old_owl_class.__doc__ = new_elem.description

                    # 4. Формула
                    if new_elem.formula is not None:
                        if new_elem.formula.strip():
                            old_owl_class.comment = [new_elem.formula]
                        else:
                            old_owl_class.comment = old_comments
            else:
                # OWL-сущности нет (онтология загружена из JSON) —
                # обновляем только Python-модель
                print(f"  → OWL-сущность не найдена, обновляем только модель")

            # ── Синхронизируем Python-модель ──────────────────────────────
            if old_name in self.classes:
                elem = self.classes[old_name]

                # Убираем из старого родителя
                old_parent = elem.parent
                if old_parent and elem in old_parent.children:
                    old_parent.children.remove(elem)

                # Обновляем поля
                elem.name        = new_name
                elem.label       = new_elem.label
                elem.description = new_elem.description
                elem.uri         = new_elem.uri
                elem.formula     = new_elem.formula if new_elem.formula is not None else elem.formula
                elem.edge_type   = new_elem.edge_type   # ← ключевое исправление
                elem.prop_values = getattr(new_elem, 'prop_values', {}) or {}
                elem.overridden_properties = getattr(new_elem, 'overridden_properties', {}) or {}

                # Обновляем расширение
                old_extension = elem.extension
                elem.extension = new_elem.extension
                if old_extension != new_elem.extension:
                    self.unregister_extension(new_name)
                    if new_elem.extension and elem.parent:
                        self.register_extension(new_elem.extension, new_name)

                # Обновляем родителя и добавляем в children нового родителя
                if new_elem.parent and new_elem.parent.name in self.classes:
                    new_parent = self.classes[new_elem.parent.name]
                    elem.parent = new_parent
                    if elem not in new_parent.children:
                        new_parent.children.append(elem)
                else:
                    elem.parent = None

                # Переименовываем ключ если нужно
                if old_name != new_name:
                    self.classes[new_name] = self.classes.pop(old_name)
                    print(f"  → Ключ перемещён: {old_name} → {new_name}")

                print(f"  → Обновлён Python-объект: edge_type='{elem.edge_type}', "
                      f"formula='{elem.formula}', extension='{elem.extension}'")

            print(f"[update_class] Успешно завершено для {new_name}")

        except Exception as e:
            print(f"[update_class] Ошибка: {e}")
            traceback.print_exc()
            raise

    def delete_class(self, name: str) -> bool:
        try:
            if name not in self.classes:
                return False
            elem = self.classes[name]
            if elem.parent and elem in elem.parent.children:
                elem.parent.children.remove(elem)
            self.unregister_extension(name)
            del self.classes[name]
            with self.onto:
                cls = self.onto[name]
                if cls:
                    destroy_entity(cls)
            return True
        except Exception as e:
            print(f"Ошибка в delete_class: {e}")
            traceback.print_exc()
            return False

    def delete_object_property(self, name: str) -> bool:
        try:
            if name not in self.object_properties:
                return False
            del self.object_properties[name]
            with self.onto:
                prop = self.onto[name]
                if prop:
                    destroy_entity(prop)
            return True
        except Exception as e:
            print(f"Ошибка в delete_object_property: {e}")
            traceback.print_exc()
            return False

    def delete_data_property(self, name: str) -> bool:
        try:
            if name not in self.data_properties:
                return False
            del self.data_properties[name]
            with self.onto:
                prop = self.onto[name]
                if prop:
                    destroy_entity(prop)
            return True
        except Exception as e:
            print(f"Ошибка в delete_data_property: {e}")
            traceback.print_exc()
            return False

    def update_object_property(self, old_name: str, new_elem: ObjectPropertyElement) -> None:
        try:
            self.delete_object_property(old_name)
            self.create_object_property(new_elem)
        except Exception as e:
            print(f"Ошибка в update_object_property: {e}")
            traceback.print_exc()
            raise

    def update_data_property(self, old_name: str, new_elem: DataPropertyElement) -> None:
        try:
            self.delete_data_property(old_name)
            self.create_data_property(new_elem)
        except Exception as e:
            print(f"Ошибка в update_data_property: {e}")
            traceback.print_exc()
            raise

    def get_inherited_properties(self, class_name: str) -> Set[ObjectPropertyElement | DataPropertyElement]:
        inherited = set()
        if class_name not in self.classes:
            return inherited
        current = self.classes[class_name]
        while current:
            for prop in self.object_properties.values():
                if prop.domain == current or prop.range_ == current:
                    inherited.add(prop)
            for prop in self.data_properties.values():
                if prop.domain == current:
                    inherited.add(prop)
            current = current.parent
        return inherited

    def validate(self) -> tuple[bool, list[str]]:
        try:
            with self.onto:
                sync_reasoner()
            inconsistent = list(default_world.inconsistent_classes())
            issues = [str(c) for c in inconsistent]
            return len(issues) == 0, issues
        except Exception as e:
            return False, [f"Ошибка рассуждения: {e}"]

    def export_to_owl(self, filename: str, format_: str = "turtle") -> str:
        self.onto.save(file=filename, format=format_)
        return f"Экспортировано в {filename}"

    def get_graph_data(self) -> dict:
        nodes = {}
        edges = []
        seen = set()

        for name, elem in self.classes.items():
            nodes[name] = {
                "label":     elem.label or elem.name,
                "uri":       elem.uri,
                "formula":   elem.formula or "",
                "extension": elem.extension or ""
            }

        for ind_name, ind in self.individuals.items():
            nodes[ind_name] = {
                "label":   ind.label or ind_name,
                "type":    "individual",
                "formula": ind.formula or ""
            }

        for elem in self.classes.values():
            for child in elem.children:
                is_extends = child.edge_type == EdgeType.EXTENDS
                edges.append({
                    "from":      elem.name,
                    "to":        child.name,
                    "label":     child.edge_type.value,
                    "type":      "inheritance",
                    "style":     "double" if is_extends else "solid",
                    "color":     "#00cc44" if is_extends else "#0066ff",
                    "extension": child.extension or ""
                })

        for prop in self.object_properties.values():
            if not prop.domain or not prop.range_:
                continue
            key = (prop.domain.name, prop.range_.name, prop.name)
            if key in seen:
                continue
            seen.add(key)
            edges.append({
                "from":  prop.domain.name,
                "to":    prop.range_.name,
                "label": prop.label or prop.name,
                "type":  "related",
                "style": "dashed",
                "color": "#ff8800"
            })

        for ind in self.individuals.values():
            for cls in ind.classes:
                edges.append({
                    "from":  ind.name,
                    "to":    cls.name,
                    "label": "is a",
                    "type":  "instance_of",
                    "style": "solid",
                    "color": "#9933ff",
                    "arrow": True
                })

        return {"nodes": nodes, "edges": edges}

    def add_individual_relation(self, subject: str, obj: str, property_name: str):
        try:
            with self.onto:
                subj = self.onto[subject]
                prop = getattr(self.onto, property_name, None)
                objct = self.onto[obj]
                if subj and prop and objct:
                    getattr(subj, property_name).append(objct)
        except Exception as e:
            print(f"Ошибка добавления факта: {e}")
            traceback.print_exc()

    def get_ontology_name(self) -> str:
        if self.onto.base_iri:
            iri = self.onto.base_iri.rstrip('#/')
            return iri.split('/')[-1] or "Без названия"
        return "Без названия"
    