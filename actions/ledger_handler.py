from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import pyodbc
from fastapi import FastAPI
from pydantic import BaseModel
from rapidfuzz import process

# ----------------- LedgerHandler Class -----------------
class LedgerHandler:
    def __init__(self):
        self.conn_str = (
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost,1433;DATABASE=SAP_Live;UID=SA;PWD=YourStrongPassw0rd;'
            'TrustServerCertificate=yes;'
        )

    def _connect(self):
        conn = pyodbc.connect(self.conn_str)
        cursor = conn.cursor()
        return conn, cursor

    # ----------------- Helper: Fuzzy Match Ledger -----------------
    def _get_ledger_id(self, party_name: str, cursor) -> int:
        cursor.execute("{CALL sp_LedgerOperations(?, ?, ?)}", (1, None, None))  # Mode 1: Get all ledgers
        ledgers = cursor.fetchall()
        ledger_dict = {row.name: row.LedgerId for row in ledgers}
        best_match, score, _ = process.extractOne(party_name, ledger_dict.keys(), score_cutoff=70)
        if not best_match:
            return None
        return ledger_dict[best_match], best_match

    # ----------------- Check Balance -----------------
    def check_balance(self, tracker: Tracker) -> Dict:
        party_name = next((e['value'] for e in tracker.latest_message.get('entities', [])
                           if e['entity'] == 'party_name'), None)
        if not party_name:
            return {"error": "कृपया पार्टी/लेजर नाम बताउनुहोस् | Please provide the ledger/party name."}

        conn, cursor = self._connect()
        try:
            ledger = self._get_ledger_id(party_name, cursor)
            if not ledger:
                return {"error": f"No ledger found matching '{party_name}'"}
            ledger_id, best_match = ledger

            # Mode 2: Get Closing Balance
            cursor.execute("{CALL sp_LedgerOperations(?, ?, ?)}", (2, ledger_id, None))
            row = cursor.fetchone()
            balance = row[0] if row and row[0] else 0.0
            return {"ledger": best_match, "balance": balance}
        finally:
            cursor.close()
            conn.close()

    # ----------------- Ledger Statement -----------------
    def get_statement(self, tracker: Tracker) -> Dict:
        party_name = next((e['value'] for e in tracker.latest_message.get('entities', [])
                           if e['entity'] == 'party_name'), None)
        if not party_name:
            return {"error": "कृपया पार्टी/लेजर नाम बताउनुहोस् | Please provide the ledger/party name."}

        conn, cursor = self._connect()
        try:
            ledger = self._get_ledger_id(party_name, cursor)
            if not ledger:
                return {"error": f"No ledger found matching '{party_name}'"}
            ledger_id, best_match = ledger

            # Mode 3: Ledger Statement
            cursor.execute("{CALL sp_LedgerOperations(?, ?, ?)}", (3, ledger_id, None))
            rows = cursor.fetchall()
            if not rows:
                return {"error": f"No statement found for '{best_match}'"}

            result = [{
                "date": str(r.VoucherDate),
                "voucher": r.VoucherName,
                "number": r.VoucherNo,
                "debit": r.DrAmount,
                "credit": r.CrAmount,
                "narration": r.Narration,
                "branch": r.Branch,
                "running_balance": r.RunningBalance
            } for r in rows]
            return {"party": best_match, "statement": result}
        finally:
            cursor.close()
            conn.close()

    # ----------------- Top Customers -----------------
    def get_top_customers(self, tracker: Tracker) -> Dict:
        nums = [ent['value'] for ent in tracker.latest_message.get('entities', []) if ent['entity'] == 'number']
        top_n = int(nums[0]) if nums else 10

        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_LedgerOperations(?, ?, ?)}", (4, None, top_n))  # Mode 4: Top Customers
            rows = cursor.fetchall()
            result_list = [{"ledger": r.name, "credit": r.Credit if r.Credit else 0} for r in rows]
            return {"top": top_n, "customers": result_list}
        finally:
            cursor.close()
            conn.close()

    # ----------------- Bottom Customers -----------------
    def get_bottom_customers(self, tracker: Tracker) -> Dict:
        nums = [ent['value'] for ent in tracker.latest_message.get('entities', []) if ent['entity'] == 'number']
        bottom_n = int(nums[0]) if nums else 10

        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_LedgerOperations(?, ?, ?)}", (5, None, bottom_n))  # Mode 5: Bottom Customers
            rows = cursor.fetchall()
            result_list = [{"ledger": r.name, "credit": r.Credit if r.Credit else 0} for r in rows]
            return {"bottom": bottom_n, "customers": result_list}
        finally:
            cursor.close()
            conn.close()

    # ----------------- Top Vendors -----------------
    def get_top_vendors(self, tracker: Tracker) -> Dict:
        nums = [ent['value'] for ent in tracker.latest_message.get('entities', []) if ent['entity'] == 'number']
        top_n = int(nums[0]) if nums else 10

        conn, cursor = self._connect()
        try:
            cursor.execute("{CALL sp_LedgerOperations(?, ?, ?)}", (6, None, top_n))  # Mode 6: Top Vendors
            rows = cursor.fetchall()
            result_list = [{"vendor": r.name, "debit": r.Debit if r.Debit else 0} for r in rows]
            return {"top": top_n, "vendors": result_list}
        finally:
            cursor.close()
            conn.close()
