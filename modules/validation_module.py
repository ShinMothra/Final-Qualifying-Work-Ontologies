from core.validation.validator import OntologyValidator
from core.model.ontology import OntologyManager

class ValidationModule:
    def __init__(self, manager: OntologyManager):
        self.manager = manager
        self.validator = OntologyValidator()

    def run(self):
        try:
            is_valid, report = self.validator.validate_ontology(self.manager)
            return is_valid, report
        except Exception as e:
            report = f"Ошибка валидации: {e} (возможно, Java/HermiT не установлен)"
            return False, report