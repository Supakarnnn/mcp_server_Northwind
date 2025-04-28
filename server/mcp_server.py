import os
from dotenv import load_dotenv
import logging
import json

from fastmcp import FastMCP

from mysql.connector import connect, Error

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("mysql_mcp_server")

load_dotenv()
mcp = FastMCP("mysql_mcp_server")

DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST"),
    "user": os.environ.get("MYSQL_USER"),
    "password": os.environ.get("MYSQL_PASSWORD"),
    "database": os.environ.get("MYSQL_DATABASE"),
    "port": 6033
}

def get_db_connection():
    try:
        return connect(**DB_CONFIG)
    except Error as e:
        logger.error(f"Error connecting to MySQL database: {e}")
        raise Exception(f"Database connection failed: {str(e)}")

@mcp.tool("list_tables")
async def list_tables():
    """List all tables in the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        conn.close()
        return {"result": json.dumps({"tables": tables})}
    except Error as e:
        logger.error(f"Error listing tables: {e}")
        return {"result": json.dumps({"error": str(e)}), "status": "error"}
    
@mcp.tool("count_each_table")
async def count():
    """count how many data on each tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]

        result = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            result[table] = count

        conn.close()
        return {"result": json.dumps({"row_counts": result})}

    except Error as e:
        logger.error(f"Error listing tables: {e}")
        return {"result": json.dumps({"error": str(e)}), "status": "error"}
    
@mcp.tool("10_best_sell")
async def BestSellerTool():
    """Pull up the top 10 best-selling products of the period from 1996 to 1998"""

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT 
            p.ProductName,
            c.CategoryName AS Category,
            s.SupplierName AS Supplier,
            o.UnitPrice,
            SUM(o.Quantity) AS Quantity,
            SUM(o.UnitPrice * o.Quantity) AS TotalPrice
        FROM orders o
        JOIN Products p ON o.ProductID = p.ProductID
        JOIN Categories c ON p.CategoryID = c.CategoryID
        JOIN Suppliers s ON p.SupplierID = s.SupplierID
        WHERE o.OrderDate BETWEEN %s AND %s
        GROUP BY p.ProductName, c.CategoryName, s.SupplierName, o.UnitPrice
        ORDER BY TotalPrice DESC
        LIMIT 10;
        """

        cursor.execute(query, ("1996-01-01", "1998-12-31"))
        results = cursor.fetchall()

        return {
            "result": json.dumps(results, indent=2, default=str),
            "status": "success"
        }

    except Error as e:
        return {
            "result": json.dumps({"error": str(e)}),
            "status": "error"
        }

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    
####################################################################################################
@mcp.tool("list_available_tools")
async def list_available_tools():
    """List all tools available in this MCP server."""
    tools = [
        {
            "name": "list_tables",
            "description": "List all tables in the database"
        },
        {
            "name": "count_each_table",
            "description": "Count how many data on each tables",
        },
        {
            "name":"10_best_sell",
            "description": "Pull up the top 10 best-selling products of the period from 1996 to 1998"
        }
    ]
    
    return {"result": json.dumps({"tools": tools})}


if __name__ == "__main__":
    mcp.run(transport='sse')

    ##fastmcp run mcp_server.py:mcp --transport sse --port 8080 --host 0.0.0.0