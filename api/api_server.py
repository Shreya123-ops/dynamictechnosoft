from fastapi import FastAPI
from pydantic import BaseModel
from rasa.core.agent import Agent
import asyncio

# --- Import handlers ---
from actions.ledger_handler import LedgerHandler
from actions.product_handler import ProductHandler

app = FastAPI()

# Load your trained Rasa model using Agent
agent = Agent.load("models")  # path to your trained Rasa model

ledger_handler = LedgerHandler()
product_handler = ProductHandler()

class Query(BaseModel):
    message: str


@app.post("/query")
def handle_query(query: Query):
    msg = query.message

    # --- Parse message using Rasa Agent ---
    result = asyncio.run(agent.parse_message(msg))

    # Extract intent and entities
    intent = result.get("intent", {}).get("name")
    entities = {e['entity']: e['value'] for e in result.get("entities", [])}

    # --- ENTITY-AWARE HANDLING ---
    if intent == "check_balance" and "party_name" in entities:
        return ledger_handler.check_balance(FakeTracker(entities))

    elif intent == "action_party_statement" and "party_name" in entities:
        return ledger_handler.get_statement(FakeTracker(entities))

    elif intent == "product_stock" and "product_name" in entities:
        return product_handler.get_product_stock(entities.get("product_name"))

    elif intent == "top_products_value":
        return product_handler.get_top_products_value(entities.get("product_name"))

    elif intent == "check_bottom_products" and "product_name" in entities:
        return product_handler.get_bottom_products(entities.get("product_name"))

    elif intent == "top_products_purchased" and "product_name" in entities:
        return product_handler.get_top_products_purchased(entities.get("product_name"))
    
    elif intent == "product_statement" and "product_name" in entities:
        return product_handler.get_product_statement(entities.get("product_name"))

    elif intent == "list_top_customers":
        return ledger_handler.get_top_customers(FakeTracker(entities))

    elif intent == "action_top_party":
        return ledger_handler.get_top_vendors(FakeTracker(entities))

    elif intent == "action_bottom_credit":
        return ledger_handler.get_bottom_customers(FakeTracker(entities))

    # --- FALLBACK KEYWORD-BASED HANDLING ---
    msg_lower = msg.lower()

    if ("balance" in msg_lower or "closing" in msg_lower) and "ledger" in msg_lower:
        return ledger_handler.check_balance(FakeTracker(entities))

    elif "statement" in msg_lower and "ledger" in msg_lower:
        return ledger_handler.get_statement(FakeTracker(entities))

    elif "stock" in msg_lower and "product" in msg_lower:
        return product_handler.get_product_stock(entities.get("product_name"))

    elif "top" in msg_lower and "product" in msg_lower and ("value" in msg_lower or "val" in msg_lower):
        return product_handler.get_top_products_value(entities.get("product_name"))

    elif "bottom" in msg_lower and "product" in msg_lower:
        return product_handler.get_bottom_products(entities.get("product_name"))

    elif "top" in msg_lower and "product" in msg_lower and ("purchased" in msg_lower or "received" in msg_lower or "inqty" in msg_lower):
        return product_handler.get_top_products_purchased(entities.get("product_name"))

    elif "top" in msg_lower and "customer" in msg_lower:
        return ledger_handler.get_top_customers(FakeTracker(entities))

    elif "top" in msg_lower and ("debit" in msg_lower or "vendor" in msg_lower):
        return ledger_handler.get_top_vendors(FakeTracker(entities))

    elif "bottom" in msg_lower and "customer" in msg_lower:
        return ledger_handler.get_bottom_customers(FakeTracker(entities))

    # --- DEFAULT ERROR ---
    return {
        "error": "Could not understand query. Include party_name or product_name for specificity."
    }


# --- Helper FakeTracker class to simulate Rasa Tracker ---
class FakeTracker:
    def __init__(self, entities_dict):
        self.latest_message = {"entities": [{"entity": k, "value": v} for k, v in entities_dict.items()]}
