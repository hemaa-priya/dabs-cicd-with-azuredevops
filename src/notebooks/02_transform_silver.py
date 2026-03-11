# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Transform to Silver Layer
# MAGIC Cleans and enriches bronze data, writes to silver Delta table.

# COMMAND ----------

dbutils.widgets.text("catalog", "dev_catalog", "Catalog")
dbutils.widgets.text("schema", "dev_schema", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

spark.sql(f"USE CATALOG {catalog}")
spark.sql(f"USE SCHEMA {schema}")

# COMMAND ----------

from pyspark.sql import functions as F

df_bronze = spark.table("bronze_orders")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Apply transformations

# COMMAND ----------

df_silver = (
    df_bronze
    .withColumn("total_amount", F.col("quantity") * F.col("unit_price"))
    .withColumn("order_date", F.to_date("order_timestamp"))
    .withColumn("order_hour", F.hour("order_timestamp"))
    .withColumn("product_category", F.when(
        F.col("product_name").isin("Laptop", "Tablet"), "Computing"
    ).when(
        F.col("product_name").isin("Monitor", "Webcam"), "Peripherals"
    ).when(
        F.col("product_name").isin("Mouse", "Keyboard", "Headset"), "Accessories"
    ).otherwise("Other"))
    .withColumn("processing_timestamp", F.current_timestamp())
    .drop("ingestion_timestamp")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Silver Delta table

# COMMAND ----------

df_silver.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("silver_orders")

row_count = spark.table("silver_orders").count()
print(f"Wrote {row_count} rows to {catalog}.{schema}.silver_orders")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation

# COMMAND ----------

neg_amounts = spark.sql("SELECT COUNT(*) FROM silver_orders WHERE total_amount < 0").first()[0]
assert neg_amounts == 0, f"Found {neg_amounts} negative amounts!"
print("Silver layer validation passed.")
