from core.model.ontology import OntologyManager
from core.storage.owl_handler import OWLHandler


class ExportModule:
    def __init__(self, manager: OntologyManager):
        self.manager = manager

    def export(self, filename: str, format_: str = "rdfxml") -> str:
        """
        Экспорт онтологии в указанный формат.

        Поддерживаемые форматы:
          OWL / RDF:
            "rdfxml"  — RDF/XML (по умолчанию, .owl)
            "turtle"  — Turtle (.ttl)
            "ntriples" — N-Triples (.nt)
          Собственный формат редактора:
            "json"    — JSON с полным сохранением модели (.json),
                        поддерживает round-trip импорт через import_json()
        """
        if format_ == "json":
            return OWLHandler.save_json(self.manager, filename)
        return OWLHandler.save_ontology(self.manager, filename, format_)

    def import_json(self, filename: str) -> OntologyManager:
        """
        Импорт онтологии из JSON-файла, созданного этим редактором.
        Возвращает загруженный OntologyManager (тот же объект, что self.manager,
        но с обновлённым содержимым).
        """
        return OWLHandler.load_json(filename, self.manager)