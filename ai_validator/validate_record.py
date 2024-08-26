import vertexai
from vertexai.generative_models import GenerativeModel
from google.oauth2.service_account import Credentials

from dotenv import load_dotenv
import os
import json


class OCDSValidatorAI():
    model_name="gemini-1.5-flash-001"

    def __init__(self):
        load_dotenv()
        key_file = os.path.dirname(__file__) + "\\" + os.getenv('KEY_FILE')
        self.credentials = Credentials.from_service_account_file(key_file)
        self.project = os.getenv('PROJECT')
        self.region = os.getenv('REGION')
        # https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/send-chat-prompts-gemini
        vertexai.init(project=self.project, location=self.region,
                      credentials=self.credentials)

    def generate_content(self, prompt, system_instruction=[]):
        model = GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction
        )
        response = model.generate_content(prompt)
        candidate = response.to_dict()["candidates"][0]
        assert candidate["finish_reason"] == "STOP"
        # assert {sr["severity"] for sr in candidate["safety_ratings"]} \
        #     == {'HARM_SEVERITY_NEGLIGIBLE'}
        return response
    
    def check_tender_description(self, compiled_release):
        sys_inst = [
            "Data given here is OCDS (Open Contracting Data Standard) data",
            "A tender has a description and items. Each item has its own description.",
            "The relevance (True if relevant, False if not) of the tender description given the descriptions of the items must be assessed.",
            "If the tender description is not relevant, a feedback message in english and spanish must be given and a suggestion in the same language with a relevant tender description based on the items descriptions must be provided.",
            "The answer must be a **valid** json file with the following structure: {'relevant': <bool>, 'feedback': <str>, 'feedback_es': <str>, 'suggestion': <str>}.",
            "The quantity and specifications of items is not relevant to this assessment.",
            "Don't add anything besides a valid json file. Spaces, line breaks, etc. are not required."
        ]
        tender_description = compiled_release["tender"]["description"]
        tender_items_description = "\n".join(
            [i["description"] for i in compiled_release["tender"]["items"]]
        )
        prompt = (f"tender description: '{tender_description}'\n"
                  f"Tender item's descriptions (one per line):\n"
                  f"{tender_items_description}")
        response = self.generate_content(prompt, sys_inst)
        rjson = json.loads(response.text)
        return rjson

    def check_tender_items_units(self, compiled_release):
        sys_inst = [
            "Data given here comes OCDS (Open Contracting Data Standard) data",
            "The relevance (True if relevant, False if not) of the unit based on the description must be assessed.",
            "If the unit is not relevant, a feedback message in english and spanish must be given and a suggestion  with a relevant unit must be provided.",
            "The suggestion consists only of the unit using the same language of the description",
            "The answer must be a **valid** json file with the following structure: {'relevant': <bool>, 'feedback': <str>, 'feedback_es': <str>, 'suggestion': <str>}.",
            "Don't add anything besides a valid json file. Spaces, line breaks, etc. are not required."
        ]
        rjson = []
        for item in compiled_release["tender"]["items"]:
            if "unit" not in item:
                raise ValueError("Unit not found in item")
            else:
                unit = item["unit"]
                description = item["description"]
                prompt = (f"Description: '{description}'\n"
                          f"Unit: '{unit['name']}'")
                try:
                    response = self.generate_content(prompt, sys_inst)
                    rjson.append(json.loads(response.text))
                except Exception as e:
                    rjson.append(f"Error: {e}")
        return rjson

filepath = "ai_validator/sample_records/ocds-d6a7a6-IA-20-125-020000021-N-25-2023.json"

with open(filepath, "r", encoding='utf-8') as f:
    data = json.load(f)
    crel = data["records"][0]["compiledRelease"]

ai = OCDSValidatorAI()
tender_description_qa = ai.check_tender_description(crel)
print(tender_description_qa)

item_unit_qa = ai.check_tender_items_units(crel)
print(item_unit_qa)

