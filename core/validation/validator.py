from ..model.ontology import OntologyManager

class OntologyValidator:
    """Модуль валидации. Вызов manager.validate()."""

    @staticmethod
    def validate_ontology(manager: OntologyManager) -> tuple[bool, str]:
        is_valid, issues = manager.validate()
        report = "Онтология непротиворечива" if is_valid else f"Противоречия: {', '.join(issues)}"
        return is_valid, report