from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import pyodbc
from fastapi import FastAPI
from pydantic import BaseModel
import re

# ----------------- ProductHandler Class -----------------
class ProductHandler:
    def __init__(self):
        #connection credentials to sql server database
        self.conn_str = (
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost,1433;DATABASE=SAP_Live;UID=SA;PWD=YourStrongPassw0rd;'
            'TrustServerCertificate=yes;'
        )

    def _connect(self):
        conn = pyodbc.connect(self.conn_str)
        cursor = conn.cursor()
        return conn, cursor

    # ----------------- Bottom Products -----------------
    def get_bottom_products(self, user_text: str) -> Dict:
        #extract number of products from user input, if no number given by default set to 10
        user_text = str(user_text or "")
        nums = re.findall(r'\d+', user_text)
        limit = int(nums[0]) if nums else 10

        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_ProductOperations(?, NULL, ?)}", (5, limit))
            rows = cursor.fetchall()
            if not rows:
                return {"error": "No product data found."}
            products = [{"rank": idx+1, "product": r.Name, "bal_qty": r.BalQty or 0} 
                        for idx, r in enumerate(rows)]
            return {"bottom": limit, "products": products}
        finally:
            cursor.close()
            conn.close()

    # ----------------- Product Stock Details -----------------
    def get_product_stock(self, product_name: str) -> Dict:
        #extract product name
        product_name = str(product_name or "")
        if not product_name:
            return {"error": "Please mention a product name."}

        clean_name = re.sub(r"(stock|show|of|please|current|for|qty|quantity)", "", product_name.lower()).strip()
        clean_name = clean_name.title()

        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_ProductOperations(?, NULL, NULL)}", (2,))
            products = cursor.fetchall()
            matched = next((p for p in products if clean_name in p.Name), None)
            if not matched:
                return {"error": f"No stock found for product matching '{clean_name}'."}
            
            #calculate running quantity and amount 
            running_qty = (matched.OpeningQty or 0) + (matched.InQty or 0) - (matched.OutQty or 0)
            running_amount = (matched.OpeningAmt or 0) + (matched.InAmt or 0) + (matched.InAditionalCost or 0) - ((matched.OutQty or 0) * (matched.OutCostRate or 0))
            
            # return all product stock details
            return {
                "product": matched.Name,
                "opening_qty": matched.OpeningQty or 0,
                "in_qty": matched.InQty or 0,
                "out_qty": matched.OutQty or 0,
                "balance_qty": matched.BalQty or running_qty,
                "running_qty": running_qty,
                "opening_amount": matched.OpeningAmt or 0,
                "in_amount": matched.InAmt or 0,
                "out_amount": matched.OutAmt or 0,
                "in_additional_cost": matched.InAditionalCost or 0,
                "running_amount": running_amount,
                "in_cost_rate": matched.InCostRate or 0,
                "out_cost_rate": matched.OutCostRate or 0
            }
        finally:
            cursor.close()
            conn.close()

    # ----------------- Top Products Purchased -----------------
    def get_top_products_purchased(self, user_text: str) -> Dict:
        user_text = str(user_text or "")
        nums = re.findall(r'\d+', user_text)
        limit = int(nums[0]) if nums else 10

        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_ProductOperations(?, NULL, ?)}", (3, limit))
            rows = cursor.fetchall()
            if not rows:
                return {"error": "No product data found."}
            products = [{"rank": idx+1, "product": r.Name, "in_qty": r.InQty or 0} 
                        for idx, r in enumerate(rows)]
            return {"top": limit, "products": products}
        finally:
            cursor.close()
            conn.close()

    # ----------------- Top Products by Value -----------------
    def get_top_products_value(self, user_text: str) -> Dict:
        user_text = str(user_text or "")
        nums = re.findall(r'\d+', user_text)
        limit = int(nums[0]) if nums else 10

        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_ProductOperations(?, NULL, ?)}", (4, limit))
            rows = cursor.fetchall()
            if not rows:
                return {"error": "No product stock data found."}
            products = [{"rank": idx+1, "product": r.Name, "bal_qty": r.BalQty or 0,
                         "rate": r.OutCostRate or 0, "value": r.StockValue or 0}
                        for idx, r in enumerate(rows)]
            return {"top": limit, "products": products}
        finally:
            cursor.close()
            conn.close()

    # ----------------- Product Statement -----------------
    def get_product_statement(self, product_name: str) -> Dict:
        #extract product name
        product_name = str(product_name or "")
        if not product_name:
            return {"error": "Please provide a product name."}

        clean_name = product_name.strip().title()
        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_ProductOperations(?, NULL, NULL)}", (1,))
            products = cursor.fetchall()
            matched = next((p for p in products if clean_name in p.Name), None)
            if not matched:
                return {"error": f"No product found matching '{clean_name}'."}

            cursor.execute("{CALL sp_ProductOperations(?, ?, NULL)}", (6, matched.ProductId))
            row = cursor.fetchone()
            if not row:
                return {"error": f"No stock data found for '{clean_name}'."}

            running_qty = (row.OpeningQty or 0) + (row.InQty or 0) - (row.OutQty or 0)
            running_amount = (row.OpeningAmt or 0) + (row.InAmt or 0) + (row.InAditionalCost or 0) - ((row.OutQty or 0) * (row.OutCostRate or 0))
            
            #returned statement
            return {
                "product": clean_name,
                "opening_qty": row.OpeningQty or 0,
                "in_qty": row.InQty or 0,
                "out_qty": row.OutQty or 0,
                "balance_qty": row.BalQty or running_qty,
                "running_qty": running_qty,
                "opening_amount": row.OpeningAmt or 0,
                "in_amount": row.InAmt or 0,
                "out_amount": row.OutAmt or 0,
                "in_additional_cost": row.InAditionalCost or 0,
                "running_amount": running_amount,
                "in_cost_rate": row.InCostRate or 0,
                "out_cost_rate": row.OutCostRate or 0
            }
        finally:
            cursor.close()
            conn.close()
