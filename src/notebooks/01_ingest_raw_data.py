# Databricks notebook source
# MAGIC %md
# MAGIC # 01 - Ingest Raw Data (Bronze Layer)
# MAGIC Reads raw CSV data from a volume and writes to a Delta table.
# MAGIC This notebook is parameterized for multi-environment deployment via DABs.

# COMMAND ----------

dbutils.widgets.text("catalog", "hp_dev", "Catalog")
dbutils.widgets.text("schema", "hp_pp_schema", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

spark.sql(f"USE CATALOG {catalog}")
spark.sql(f"USE SCHEMA {schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate sample source data (for demo purposes)

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType, IntegerType
import datetime

orders_data = [
    (1, "C001", "Laptop", 1, 999.99, datetime.datetime(2025, 1, 15, 10, 30)),
    (2, "C002", "Mouse", 3, 25.50, datetime.datetime(2025, 1, 15, 11, 0)),
    (3, "C001", "Keyboard", 1, 75.00, datetime.datetime(2025, 1, 16, 9, 15)),
    (4, "C003", "Monitor", 2, 450.00, datetime.datetime(2025, 1, 16, 14, 0)),
    (5, "C004", "Headset", 1, 120.00, datetime.datetime(2025, 1, 17, 8, 45)),
    (6, "C002", "USB Hub", 2, 35.00, datetime.datetime(2025, 1, 17, 16, 30)),
    (7, "C005", "Webcam", 1, 89.99, datetime.datetime(2025, 1, 18, 10, 0)),
    (8, "C003", "Laptop", 1, 1099.99, datetime.datetime(2025, 1, 18, 11, 20)),
    (9, "C006", "Tablet", 1, 599.99, datetime.datetime(2025, 1, 19, 13, 0)),
    (10, "C004", "Charger", 3, 29.99, datetime.datetime(2025, 1, 19, 15, 45)),
]

orders_schema = StructType([
    StructField("order_id", IntegerType(), False),
    StructField("customer_id", StringType(), False),
    StructField("product_name", StringType(), False),
    StructField("quantity", IntegerType(), False),
    StructField("unit_price", DoubleType(), False),
    StructField("order_timestamp", TimestampType(), False),
])

df_orders = spark.createDataFrame(orders_data, schema=orders_schema)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Bronze Delta table

# COMMAND ----------

df_bronze = df_orders.withColumn("ingestion_timestamp", F.current_timestamp())

df_bronze.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("bronze_orders")

row_count = spark.table("bronze_orders").count()
print(f"Ingested {row_count} rows into {catalog}.{schema}.bronze_orders")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data quality check

# COMMAND ----------

assert row_count > 0, "Bronze table is empty after ingestion!"
null_check = spark.sql("SELECT COUNT(*) as null_count FROM bronze_orders WHERE order_id IS NULL").first()[0]
assert null_check == 0, f"Found {null_check} null order_ids!"
print("Data quality checks passed.")
