from dotenv import load_dotenv
import os

load_dotenv()
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")

class ApolloClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def org_enrich(self, domain):
        pass

    def people_search(self, filters):
        pass

    def people_enrich(self, person_id):
        pass