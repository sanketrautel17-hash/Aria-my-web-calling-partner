"""
Aria — Tool Manager for the Loan Assistant AI pipeline.

Provides three tools, shared by BOTH web and phone call pipelines:
  1. get_loan_information — RAG query against loan_policy.txt
  2. search_web           — Tavily web search for external rate info
  3. end_call             — Gracefully terminates the call/session
"""

import asyncio
from datetime import datetime

from pipecat.frames.frames import TextFrame, EndFrame

from core.db.database import get_database
from core.rag.knowledge_base import kb
from core.tools.web_search import web_search
from commons.logger import logger

log = logger(__name__)


class ToolManager:
    def __init__(self, task, call_sid: str, source: str = "phone"):
        """
        Args:
            task      : The active PipelineTask (set after pipeline creation).
            call_sid  : Unique call identifier (Twilio SID or WebRTC pc_id).
            source    : 'web' or 'phone' — used for DB logging.
        """
        self.task = task
        self.call_sid = call_sid
        self.source = source

    async def _log_tool_usage(self, tool_name: str, query: str, result: str):
        """Log tool calls to Aria's unified DB."""
        try:
            db = get_database()
            await db["tool_logs"].insert_one(
                {
                    "source": self.source,
                    "call_sid": self.call_sid,
                    "tool": tool_name,
                    "query": query,
                    "result": str(result),
                    "timestamp": datetime.utcnow(),
                }
            )
        except Exception as e:
            log.error(f"Failed to log tool usage: {e}")

    async def get_loan_information(self, params, query: str):
        """
        Search the bank's internal knowledge base for loan information.

        Use this function to find information about:
        - Home loans, personal loans, car loans, business loans
        - Interest rates for our bank's products
        - Loan eligibility criteria
        - Processing fees and charges
        - Loan amounts and tenure options
        - Documentation requirements
        - Loan policies and terms

        Args:
            query (str): The customer's question about loans or related information

        Returns:
            str: Relevant information from the knowledge base
        """
        try:
            log.info(f"🔍 [TOOL] get_loan_information | query='{query}'")
            result = await asyncio.to_thread(kb.query, query)

            if not result or not result.strip():
                result = (
                    "I couldn't find specific information about that in our knowledge base. "
                    "Let me connect you with a loan officer who can provide accurate details."
                )

            result_str = str(result).strip()
            log.info(f"✅ [TOOL RESULT] get_loan_information ({len(result_str)} chars)")
            await self._log_tool_usage("get_loan_information", query, result_str)
            return result_str
        except Exception as e:
            msg = (
                "I'm experiencing technical difficulties accessing our loan database. "
                "Please hold while I transfer you to a loan officer."
            )
            log.error(f"❌ [TOOL ERROR] get_loan_information: {e}")
            await self._log_tool_usage("get_loan_information", query, f"ERROR: {e}")
            return msg

    async def search_web(self, params, query: str):
        """
        Search the internet for current market rates and external information.

        Use this function to find:
        - Current market interest rates
        - RBI policy rates and guidelines
        - Competitor loan products (SBI, HDFC, ICICI, Axis, etc.)
        - General banking information
        - Industry trends and news

        Args:
            query (str): The search query for web information

        Returns:
            str: Information from web search results
        """
        try:
            log.info(f"🌐 [TOOL] search_web | query='{query}'")
            result = await asyncio.to_thread(web_search.search, query)

            if not result or not result.strip():
                result = (
                    "I couldn't find current information about that online. "
                    "Would you like to know about our internal loan products instead?"
                )

            result_str = str(result).strip()
            log.info(f"✅ [TOOL RESULT] search_web ({len(result_str)} chars)")
            await self._log_tool_usage("search_web", query, result_str)
            return result_str
        except Exception as e:
            msg = "I'm unable to search for that right now. Would you like to know about our bank's loan products instead?"
            log.error(f"❌ [TOOL ERROR] search_web: {e}")
            await self._log_tool_usage("search_web", query, f"ERROR: {e}")
            return msg

    async def end_call(self, params):
        """
        End the call gracefully after saying goodbye.

        Use this function when:
        - The customer says goodbye, thanks, or wants to end the call
        - The conversation has naturally concluded
        - The customer explicitly asks to disconnect

        Returns:
            str: Confirmation that call termination was initiated
        """
        try:
            log.info("🛑 [TOOL] end_call")
            await self._log_tool_usage("end_call", "N/A", "Call termination requested")

            if self.task:
                await self.task.queue_frames(
                    [TextFrame(text="Thank you for calling. Have a wonderful day! Goodbye.")]
                )
                await asyncio.sleep(1.5)
                await self.task.queue_frames([EndFrame()])
                log.info("✅ [TOOL RESULT] end_call — pipeline terminated")
            else:
                log.error("❌ [TOOL ERROR] end_call: task not initialized")

            return "Call ended successfully."
        except Exception as e:
            log.error(f"❌ [TOOL ERROR] end_call: {e}")
            return "Error ending call."
