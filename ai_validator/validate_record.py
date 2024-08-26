import vertexai
from vertexai.generative_models import GenerativeModel
from google.oauth2.service_account import Credentials

from dotenv import load_dotenv
import os
import json


class OCDSValidatorAI():
    # Nombre del modelo generativo a utilizar
    model_name = "gemini-1.5-flash-001"

    def __init__(self):
        # Carga variables de entorno desde .env
        load_dotenv()

        # Construye la ruta al archivo de clave de servicio
        key_file = os.path.dirname(__file__) + "\\" + os.getenv('KEY_FILE')

        # Crea objeto de credenciales desde el archivo de clave
        self.credentials = Credentials.from_service_account_file(key_file)

        # Obtiene ID del proyecto y región de Google Cloud
        self.project = os.getenv('PROJECT')
        self.region = os.getenv('REGION')

        # Inicializa el SDK de Vertex AI
        vertexai.init(project=self.project, location=self.region,
                        credentials=self.credentials)

    def generate_content(self, prompt, system_instruction=[]):
        # Crea una instancia del modelo generativo
        model = GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction
        )

        # Genera contenido basado en el prompt
        response = model.generate_content(prompt)

        # Obtiene el candidato principal de la respuesta
        candidate = response.to_dict()["candidates"][0]

        # Verifica que la generación se completó correctamente
        assert candidate["finish_reason"] == "STOP"

        # Devuelve la respuesta del modelo
        return response

    def check_tender_description(self, compiled_release):
        # Instrucciones del sistema para guiar al modelo
        sys_inst = [
            "Data given here is OCDS (Open Contracting Data Standard) data",
            ("A tender has a description and items. "
             "Each item has its own description."),
            ("The relevance (True if relevant, False if not) of the tender des"
             "cription given the descriptions of the items must be assessed."),
            ("If the tender description is not relevant, a feedback message in"
             " english and spanish must be given and a suggestion in the same "
             "language with a relevant tender description based on the items "
             "descriptions must be provided."),
            ("The answer must be a **valid** json file with the following "
             "structure: {'relevant': <bool>, 'feedback': <str>, "
             "'feedback_es': <str>, 'suggestion': <str>}."),
            ("The quantity and specifications of items is not relevant to this"
             " assessment."),
            ("Don't add anything besides a valid json file. "
             "Spaces, line breaks, etc. are not required."),
        ]

        # Obtiene la descripción de la licitación
        tender_description = compiled_release["tender"]["description"]

        # Obtiene las descripciones de los ítems de la licitación
        tender_items_description = "\n".join(
            [i["description"] for i in compiled_release["tender"]["items"]]
        )

        # Construye el prompt para el modelo
        prompt = (f"tender description: '{tender_description}'\n"
                  f"Tender item's descriptions (one per line):\n"
                  f"{tender_items_description}")

        # Genera contenido utilizando el modelo
        response = self.generate_content(prompt, sys_inst)

        # Convierte la respuesta en un objeto JSON
        rjson = json.loads(response.text)

        # Devuelve el objeto JSON
        return rjson

    def check_tender_items_units(self, compiled_release):
        # Instrucciones del sistema para guiar al modelo
        sys_inst = [
            "Data given here comes OCDS (Open Contracting Data Standard) data",
            ("The relevance (True if relevant, False if not) of the unit based"
             " on the description must be assessed."),
            ("If the unit is not relevant, a feedback message in english and "
             "spanish must be given and a suggestion with a relevant unit must"
             " be provided."),
            ("The suggestion consists only of the unit using the same language"
             " of the description"),
            ("The answer must be a **valid** json file with the following "
             "structure: {'relevant': <bool>, 'feedback': <str>, "
             "'feedback_es': <str>, 'suggestion': <str>}."),
            ("Don't add anything besides a valid json file. "
             "Spaces, line breaks, etc. are not required."),
        ]

        # Lista para almacenar las respuestas JSON
        rjson = []

        # Itera sobre los ítems de la licitación
        for item in compiled_release["tender"]["items"]:
            # Verifica si el ítem tiene una unidad definida
            if "unit" not in item:
                # Lanza una excepción si no se encuentra la unidad
                raise ValueError("Unit not found in item")
            else:
                # Obtiene la unidad y descripción del ítem
                unit = item["unit"]
                description = item["description"]
                # Construye el prompt para el modelo
                prompt = (f"Description: '{description}'\n"
                          f"Unit: '{unit['name']}'")
                try:
                    # Genera contenido utilizando el modelo
                    response = self.generate_content(prompt, sys_inst)
                    # Convierte la respuesta en JSON y la agrega a la lista
                    rjson.append(json.loads(response.text))
                except Exception as e:
                    # Agrega un mensaje de error a la lista
                    rjson.append(f"Error: {e}")

        # Devuelve la lista de respuestas JSON
        return rjson

# Ruta al archivo JSON de ejemplo
filepath = "ai_validator/sample_records/ocds-d6a7a6-IA-20-125-020000021-N-25-2023.json"

with open(filepath, "r", encoding='utf-8') as f:
    # Carga el contenido del archivo JSON en un diccionario
    data = json.load(f)
    # Extrae la parte "compiledRelease" del primer registro
    crel = data["records"][0]["compiledRelease"]

# Crea una instancia de la clase OCDSValidatorAI
ai = OCDSValidatorAI()

# Verifica la descripción de la licitación
tender_description_qa = ai.check_tender_description(crel)
# Imprime el resultado de la verificación de la descripción
print(tender_description_qa)

# Verifica las unidades de los ítems
item_unit_qa = ai.check_tender_items_units(crel)
# Imprime el resultado de la verificación de las unidades
print(item_unit_qa)
