# Databricks notebook source
# MAGIC %md
# MAGIC # DLT / Lakeflow Declarative Pipeline - Orders
# MAGIC Demonstrates a medallion architecture pipeline managed by DABs.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze: Raw ingestion

# COMMAND ----------

@dlt.table(
    name="bronze_orders_stream",
    comment="Raw orders ingested from source",
    table_properties={"quality": "bronze"},
)
def bronze_orders_stream():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .load("/Volumes/${catalog}/${schema}/raw_data/orders/")
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: Cleaned and enriched

# COMMAND ----------

@dlt.table(
    name="silver_orders_cleaned",
    comment="Cleaned orders with quality constraints",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("valid_order_id", "order_id IS NOT NULL")
@dlt.expect_or_drop("valid_quantity", "quantity > 0")
@dlt.expect_or_drop("valid_price", "unit_price > 0")
def silver_orders_cleaned():
    return (
        dlt.read_stream("bronze_orders_stream")
        .withColumn("total_amount", F.col("quantity") * F.col("unit_price"))
        .withColumn("order_date", F.to_date("order_timestamp"))
        .withColumn("product_category", F.when(
            F.col("product_name").isin("Laptop", "Tablet"), "Computing"
        ).when(
            F.col("product_name").isin("Monitor", "Webcam"), "Peripherals"
        ).when(
            F.col("product_name").isin("Mouse", "Keyboard", "Headset"), "Accessories"
        ).otherwise("Other"))
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: Daily revenue aggregate

# COMMAND ----------

@dlt.table(
    name="gold_daily_revenue",
    comment="Daily revenue aggregation for reporting",
    table_properties={"quality": "gold"},
)
def gold_daily_revenue():
    return (
        dlt.read("silver_orders_cleaned")
        .groupBy("order_date")
        .agg(
            F.count("order_id").alias("total_orders"),
            F.sum("total_amount").alias("daily_revenue"),
            F.avg("total_amount").alias("avg_order_value"),
            F.countDistinct("customer_id").alias("unique_customers"),
        )
    )
